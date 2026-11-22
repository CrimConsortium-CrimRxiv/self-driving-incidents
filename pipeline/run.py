"""Collect new reports, attach them to cases, code what needs coding, and rebuild the site files.

    python -m pipeline.run                      regular run (last few days of news)
    python -m pipeline.run --backfill 2026-01-01   also search week by week back to that date
    python -m pipeline.run --no-collect         code and export only
    python -m pipeline.run --no-code            collect and export only
    python -m pipeline.run --export-only        rebuild site and download files from the store
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from . import cluster, coder, collect, enrich, export, store as st
from .common import load_config, log, setup_logging


# --------------------------------------------------------------------------- collect

def backfill_windows(start: str, step_days: int = 7) -> list[str]:
    out, d, today = [], date.fromisoformat(start), date.today()
    while d < today:
        e = min(d + timedelta(days=step_days), today + timedelta(days=1))
        out.append(f"after:{d.isoformat()} before:{e.isoformat()}")
        d = e
    return out


def _source(it: collect.Item) -> dict:
    return {"publisher": it.source, "title": it.title, "url": it.url,
            "published": it.published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolved": bool(it.direct_url), "summary": None, "snippet": it.snippet}


def refresh_auto(case: dict, cfg: dict) -> None:
    """Headline, word-match model/location/labels, and the publisher summary shown on the site."""
    srcs = case["sources"]
    best = max(srcs, key=lambda s: (bool(collect.extract_location(s["title"])), len(s["title"])))
    case["headline"], case["headline_publisher"] = best["title"], best["publisher"]
    titles = [best["title"]] + [s["title"] for s in srcs]
    case["auto"]["model"] = next((m for m in map(collect.extract_model, titles) if m), None)
    case["auto"]["location"] = next((p for p in map(collect.extract_location, titles) if p), None)
    with_sum = [s for s in srcs if s.get("summary")]
    if with_sum:
        pick = max(with_sum, key=lambda s: len(s["summary"]))
        case["source_summary"], case["source_summary_publisher"] = pick["summary"], pick["publisher"]
    text = " ".join(titles + [s.get("summary") or "" for s in srcs])
    case["auto"]["tags"] = collect.tag_story(text, cfg)


def add_reports(store: dict, items: list[collect.Item], cfg: dict) -> int:
    """Attach each new report to the case it belongs to, or open a pending case for it."""
    urls, reports = st.known_urls(store), st.known_reports(store)
    fresh = [i for i in items if i.url not in urls and (i.source.lower(), i.title.lower()) not in reports]
    seen, unique = set(), []
    for it in sorted(fresh, key=lambda i: i.published):
        k = (it.source.lower(), it.title.lower())
        if k not in seen:
            seen.add(k)
            unique.append(it)
    touched = []
    for group in cluster.group_items(unique, int(cfg.get("similarity_threshold", 75))):
        probe = {"sources": [_source(i) for i in group], "headline": "", "auto": {}}
        home = next((c for c in store["cases"] if cluster.same_incident(probe, c, cfg)), None)
        if home is None:
            home = st.new_case(store, group[0].maker)
        elif home["status"] == "published" or (home["status"] == "excluded" and home["code_attempts"] < 2):
            home["needs_coding"] = True
        home["sources"].extend(probe["sources"])
        home["updated"] = st.now_iso()
        touched.append(home)
    todo = [s for c in touched for s in c["sources"] if s.get("summary") is None][:400]
    max_chars = int(cfg.get("max_summary_chars", 240))

    def work(src):
        if src.get("snippet") and not src.get("summary"):
            src["summary"] = enrich.clean_summary(src["snippet"], src["title"], max_chars) or None
        enrich.resolve_source(src, max_chars)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, todo))
    for c in store["cases"]:
        for s in c["sources"]:
            s.pop("snippet", None)
    for c in touched:
        refresh_auto(c, cfg)
    merge_pending(store, cfg)
    return len(unique)


def absorb(target: dict, other: dict, store: dict, cfg: dict) -> None:
    have = {s["url"] for s in target["sources"]}
    target["sources"].extend(s for s in other["sources"] if s["url"] not in have)
    target["updated"] = st.now_iso()
    if target["status"] != "pending":
        target["needs_coding"] = True
    store["cases"].remove(other)
    refresh_auto(target, cfg)


def merge_pending(store: dict, cfg: dict) -> None:
    """Once summaries are known, pending cases about the same event can be recognised and joined."""
    changed = True
    while changed:
        changed = False
        pending = [c for c in store["cases"] if c["status"] == "pending"]
        for p in pending:
            other = next((c for c in store["cases"] if c is not p and c["status"] != "excluded"
                          and cluster.same_incident(p, c, cfg)), None)
            if other is not None:
                target, gone = (other, p) if other["status"] != "pending" or len(other["sources"]) >= len(p["sources"]) else (p, other)
                absorb(target, gone, store, cfg)
                changed = True
                break


# --------------------------------------------------------------------------- code

def reports_for(case: dict, cfg: dict) -> list[dict]:
    """Pick the reports the coder will read: the fullest texts, always including the newest report."""
    limit = int(cfg["coder"].get("max_sources_per_case", 5))
    srcs = sorted(case["sources"], key=lambda s: s["published"], reverse=True)
    pool_ = srcs[:6] + [s for s in srcs[6:] if s.get("summary")][:4]
    with ThreadPoolExecutor(max_workers=6) as pool:
        texts = list(pool.map(enrich.article_text, pool_))
    ranked = sorted(zip(pool_, texts), key=lambda p: (-len(p[1]), -len(p[0].get("summary") or "")))
    chosen = ranked[:limit]
    if srcs[0]["url"] not in {s["url"] for s, _ in chosen}:
        chosen[-1] = (srcs[0], texts[0])
    chosen.sort(key=lambda p: p[0]["published"])
    return [{"n": i + 1, "url": s["url"], "publisher": s["publisher"], "published": s["published"],
             "title": s["title"], "summary": s.get("summary") or "", "text": t}
            for i, (s, t) in enumerate(chosen)]


def settle(store: dict, case: dict, raw: dict, reports: list[dict], earlier: list[dict], cfg: dict,
           model: str, tally: dict) -> str:
    """Check one drafted answer and act on it: publish, screen out, or join an earlier case."""
    case["code_attempts"] = case.get("code_attempts", 0) + 1
    result = coder.check(raw, case, reports, earlier, cfg, model)
    was = case["status"]
    if result["decision"] == "merge" and was != "published":
        target = next(e["case"] for e in earlier if e["ref"] == result["target"])
        log.info("Same incident as %s: %s", target["case_id"], case["headline"][:80])
        absorb(target, case, store, cfg)
        tally["merged"] += 1
        return "merged"
    if result["decision"] in ("exclude", "merge"):
        if was == "published":
            # A published case is never withdrawn automatically; keep the earlier coding.
            log.info("Recode suggested exclusion, kept as is: %s", case["case_id"])
        else:
            case["status"], case["exclusion_reason"] = "excluded", result["reason"].strip()
            tally["excluded"] += 1
        case["needs_coding"] = False
    else:
        case["coding"], case["needs_coding"], case["exclusion_reason"] = result["coding"], False, None
        case["status"] = "published"
        st.assign_id(store, case)
        tally["recoded" if was == "published" else "published"] += 1
    case["updated"] = st.now_iso()
    return result["decision"]


def code_cases(store: dict, cfg: dict, limit: int | None = None) -> dict:
    tally = {"published": 0, "recoded": 0, "excluded": 0, "merged": 0, "stopped": ""}
    limit = int(cfg["coder"]["max_cases_per_run"]) if limit is None else limit
    pause = float(cfg["coder"].get("seconds_between_requests", 4.5))
    queue = [c for c in store["cases"] if c.get("needs_coding")]
    # New cases first (newest reports first), then published cases that gained reports.
    queue.sort(key=st.last_reported, reverse=True)
    queue.sort(key=lambda c: 0 if c["status"] == "pending" else 1)   # stable: keeps newest-first within each
    done = 0
    for case in queue:
        if done >= limit:
            tally["stopped"] = f"reached the per-run limit of {limit}"
            break
        if case not in store["cases"]:
            continue  # merged away earlier in this loop
        others = [c for c in store["cases"] if c["status"] == "published" and c is not case]
        earlier = [{"ref": c["case_id"], "first_reported": st.first_reported(c), "headline": c["headline"],
                    "summary": (c.get("coding") or {}).get("narrative") or c.get("source_summary") or "",
                    "case": c} for c in cluster.candidates(case, others)]
        reports = reports_for(case, cfg)
        messages = coder.build_messages(case, reports, earlier, cfg)
        try:
            raw, model = coder.call_model(messages, cfg)
        except coder.RateLimited as exc:
            tally["stopped"] = f"allowance used up ({str(exc)[:80]})"
            log.warning("Coding paused: %s", exc)
            break
        except coder.CoderUnavailable as exc:
            tally["stopped"] = str(exc)[:120]
            log.warning("Coding did not run: %s", exc)
            break
        done += 1
        settle(store, case, raw, reports, earlier, cfg, model, tally)
        st.save(store)  # keep progress even if a later request fails
        time.sleep(pause)
    return tally


# --------------------------------------------------------------------------- main

def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", metavar="YYYY-MM-DD")
    ap.add_argument("--no-collect", action="store_true")
    ap.add_argument("--no-code", action="store_true")
    ap.add_argument("--export-only", action="store_true")
    ap.add_argument("--max-code", type=int)
    args = ap.parse_args()
    cfg = load_config()
    store = st.load()
    notes = []

    if not (args.no_collect or args.export_only):
        urls = collect.feed_urls(cfg)
        if args.backfill:
            urls += collect.feed_urls(cfg, backfill_windows(args.backfill))
        items, failures = collect.fetch_feeds(urls)
        kept = collect.relevant(items, cfg)
        added = add_reports(store, kept, cfg)
        log.info("Reports: %d found, %d relevant, %d new", len(items), len(kept), added)
        notes.append(f"{added} new reports")
        if failures and len(failures) == len(urls):
            raise SystemExit("Every news search failed; nothing was changed.")
        st.save(store)

    if not (args.no_code or args.export_only):
        tally = code_cases(store, cfg, args.max_code)
        notes.append(f"{tally['published']} new cases, {tally['recoded']} recoded, "
                     f"{tally['excluded']} screened out, {tally['merged']} merged")
        if tally["stopped"]:
            notes.append(f"coding paused: {tally['stopped']}")
        st.save(store)

    stats = export.export_all(store, cfg)
    waiting = sum(1 for c in store["cases"] if c.get("needs_coding"))
    summary = (f"Data refresh: {stats['cases']} cases, {stats['sources']} reports"
               + (f"; {'; '.join(notes)}" if notes else "") + (f"; {waiting} awaiting coding" if waiting else ""))
    log.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
