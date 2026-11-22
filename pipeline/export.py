"""Write everything the public sees: download files, the codebook, and the web pages."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date
from html import escape as esc
from urllib.parse import quote

from . import codebook as cb, pages
from .common import ROOT
from .store import first_reported, last_reported, merged_ids

DATA = ROOT / "data"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
ACRONYMS = {"nhtsa": "NHTSA", "ntsb": "NTSB", "non_us_regulator": "Regulator outside the U.S.",
            "autopilot": "Autopilot", "full_self_driving": "Full Self-Driving",
            "summon_or_autopark": "Summon or Autopark", "robotaxi_or_driverless_service": "Robotaxi or driverless service",
            "unspecified": "Self-driving feature (product not named)"}
STATUS_BADGE = {
    "confirmed_by_official_source": "In use, per an official source or the maker's data",
    "claimed": "Said to be in use; not officially confirmed",
    "alleged_in_legal_filing": "Alleged in use in a legal filing",
    "under_investigation": "Use under investigation",
    "disputed": "Use disputed",
    "reported_not_engaged": "Reported not in use",
    "mentioned_only": "Mentioned in coverage only",
}
FEATURE_BADGE = {
    "autopilot": "Autopilot mentioned in coverage",
    "full_self_driving": "Full Self-Driving mentioned in coverage",
    "robotaxi_or_driverless_service": "Robotaxi mentioned in coverage",
    "summon_or_autopark": "Summon mentioned in coverage",
    "unspecified": "Self-driving mode mentioned in coverage",
}


# --------------------------------------------------------------------------- small helpers

def write_if_changed(path, text: str | bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8") if isinstance(text, str) else text
    if path.exists() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def _var_order(name: str) -> tuple:
    names = [v["name"] for v in cb.VARIABLES]
    return (names.index(name) if name in names else len(names), name)


def human(value) -> str:
    """Readable form of a coded value."""
    if isinstance(value, list):
        return "; ".join(human(v) for v in value)
    if isinstance(value, int):
        return str(value)
    v = str(value)
    if v in ACRONYMS:
        return ACRONYMS[v]
    return v.replace("_", " ").capitalize() if "_" in v or v.islower() else v


def nice_date(iso: str, short: bool = False) -> str:
    """'2026-11-19' -> 'November 19, 2026'; partial dates stay partial."""
    parts = (iso or "").split("-")
    if not parts or not parts[0].isdigit():
        return ""
    y = parts[0]
    if len(parts) == 1:
        return y
    m = MONTHS[int(parts[1]) - 1]
    m = m[:3] if short else m
    return f"{m} {y}" if len(parts) == 2 else f"{m} {int(parts[2][:2])}, {y}"


def sort_date(case: dict) -> str:
    d = ((case.get("coding") or {}).get("values") or {}).get("incident_date")
    if d:
        return (d + "-01-01")[:10] if len(d) == 4 else (d + "-01")[:10] if len(d) == 7 else d
    return first_reported(case)


def view(case: dict, cfg: dict, merged: list[str] | None = None) -> dict:
    """Everything the pages need to show one case, worked out once."""
    vals = (case.get("coding") or {}).get("values") or {}
    make = vals.get("vehicle_make") or case["maker"]
    model = vals.get("vehicle_model")
    if model:
        vehicle = model if model.lower().startswith(make.lower()) else f"{make} {model}"
    else:
        vehicle = case["auto"].get("model") or make
    place = ", ".join(p for p in (vals.get("location_city"), vals.get("location_state_region")) if p)
    country = vals.get("location_country")
    if country and country.lower() not in ("united states", "usa", "us", "u.s.", "united states of america"):
        place = ", ".join(p for p in (place, country) if p)
    place = place or case["auto"].get("location") or ""
    lead = " \u00b7 ".join(p for p in (vehicle, place) if p)

    inc = vals.get("incident_date")
    date_label = nice_date(inc) if inc else f"First reported {nice_date(first_reported(case))}"

    tags = []
    if vals.get("system_named"):
        tags += [{"label": FEATURE_BADGE[s], "kind": ""} for s in vals["system_named"]]
    else:
        tags += [{"label": t["label"], "kind": ""} for t in case["auto"]["tags"] if t["key"] != "fatality"]
    if vals.get("engagement_status"):
        tags.append({"label": STATUS_BADGE[vals["engagement_status"]], "kind": "status"})
    if vals.get("fatalities"):
        n = vals["fatalities"]
        tags.append({"label": f"{n} death{'s' if n != 1 else ''} reported", "kind": ""})
    elif not vals and any(t["key"] == "fatality" for t in case["auto"]["tags"]):
        tags.append({"label": "Fatality mentioned in coverage", "kind": ""})
    if vals.get("injuries"):
        n = vals["injuries"]
        tags.append({"label": f"{n} injur{'ies' if n != 1 else 'y'} reported", "kind": ""})

    narrative = (case.get("coding") or {}).get("narrative") or ""
    if case.get("source_summary"):
        summary, by, kind = case["source_summary"], case["source_summary_publisher"], "publisher"
    else:
        summary, by, kind = narrative, "Machine-drafted summary", "machine"
    srcs = sorted(case["sources"], key=lambda s: s["published"])
    return {"id": case["case_id"], "url": f"cases/{case['case_id']}.html", "lead": lead,
            "vehicle": vehicle, "place": place, "date_label": date_label, "sort": sort_date(case),
            "title": case["headline"], "publisher": case["headline_publisher"],
            "summary": summary, "summary_by": by, "summary_kind": kind, "tags": tags,
            "sources": srcs, "narrative": narrative, "vals": vals, "merged": list(merged or []),
            "first": first_reported(case), "last": last_reported(case)}


# --------------------------------------------------------------------------- download files

def _csv(rows: list[list], header: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _cell(v):
    if v is None:
        return ""
    return "; ".join(str(x) for x in v) if isinstance(v, list) else v


def public_record(case: dict, v: dict, site_url: str) -> dict:
    coding = case.get("coding") or {}
    return {
        "case_id": case["case_id"], "maker": case["maker"], "url": site_url + v["url"],
        "first_reported": v["first"], "last_reported": v["last"], "sort_date": v["sort"],
        "headline": case["headline"], "headline_publisher": case["headline_publisher"],
        "source_summary": case.get("source_summary"),
        "source_summary_publisher": case.get("source_summary_publisher"),
        "auto": case["auto"],
        "narrative": coding.get("narrative") or "",
        "review_status": coding.get("review_status"), "coder": coding.get("coder"),
        "coded_at": coding.get("coded_at"), "codebook_version": coding.get("codebook_version"),
        "text_basis": coding.get("text_basis"),
        "unsupported_values_removed": coding.get("unsupported_values_removed"),
        "merged_ids": v["merged"],
        "variables": {var["name"]: coding.get("values", {}).get(var["name"]) for var in cb.VARIABLES},
        # Fixed key order, so the file reads the same whether the case was coded in this run or loaded from disk.
        "evidence": {n: e for n, e in sorted(coding.get("evidence", {}).items(), key=lambda p: _var_order(p[0]))},
        "claims": [dict(sorted(c.items())) for c in coding.get("claims", [])],
        "sources": [{"publisher": s["publisher"], "title": s["title"], "url": s["url"],
                     "published": s["published"][:10],
                     "read_by_coder": next((r["basis"] for r in coding.get("sources_read", [])
                                            if r["url"] == s["url"]), "not_read")}
                    for s in v["sources"]],
    }


def retired_rows(retired: list[dict]) -> list[dict]:
    return [{"retired_id": r["case_id"], "merged_into": r["merged_into"], "retired_on": r["retired_on"],
             "n_reports_moved": r.get("n_reports", ""), "reason": r["reason"]}
            for r in sorted(retired, key=lambda r: r["case_id"])]


def write_downloads(published: list[tuple[dict, dict]], excluded: list[dict], cfg: dict, updated: str,
                    retired: list[dict] | None = None) -> None:
    gone = retired_rows(retired or [])
    site_url = cfg["site"]["url"]
    recs = [public_record(c, v, site_url) for c, v in published]
    names = [v["name"] for v in cb.VARIABLES]
    head = [n for n, _ in cb.CASE_FIELDS]
    cases_rows = []
    for r in recs:
        flat = {**r, "n_sources": len(r["sources"]), "auto_model": r["auto"]["model"],
                "auto_location": r["auto"]["location"],
                "auto_tags": [t["label"] for t in r["auto"]["tags"]]}
        cases_rows.append([_cell(flat.get(h)) for h in head if h != "url"]
                          + [_cell(r["variables"][n]) for n in names] + [r["url"]])
    files = {
        "cases.csv": _csv(cases_rows, [h for h in head if h != "url"] + names + ["url"]),
        "evidence.csv": _csv([[r["case_id"], n, _cell(r["variables"][n]), e["quote"], e["source_url"]]
                              for r in recs for n, e in sorted(r["evidence"].items(), key=lambda p: names.index(p[0]))],
                             ["case_id", "variable", "value", "quote", "source_url"]),
        "claims.csv": _csv([[r["case_id"], i + 1, c["claimant"], c["topic"], c["paraphrase"], c["quote"], c["source_url"]]
                            for r in recs for i, c in enumerate(r["claims"])],
                           ["case_id", "claim_no", "claimant", "topic", "paraphrase", "quote", "source_url"]),
        "sources.csv": _csv([[r["case_id"], s["publisher"], s["title"], s["url"], s["published"], s["read_by_coder"]]
                             for r in recs for s in r["sources"]],
                            ["case_id", "publisher", "title", "url", "published", "read_by_coder"]),
        "screened_out.csv": _csv([[first_reported(c), c["headline"], c["headline_publisher"],
                                   min(c["sources"], key=lambda s: s["published"])["url"], len(c["sources"]),
                                   c.get("exclusion_reason") or ""]
                                  for c in sorted(excluded, key=first_reported, reverse=True)],
                                 ["first_reported", "headline", "publisher", "url", "n_reports", "reason"]),
        "retired_ids.csv": _csv([list(g.values()) for g in gone],
                                ["retired_id", "merged_into", "retired_on", "n_reports_moved", "reason"]),
        "cases.json": json.dumps({"dataset": cfg["site"]["name"], "url": site_url, "updated": updated,
                                  "codebook_version": cb.VERSION, "license": cfg["license"]["data"],
                                  "cases": recs, "retired_ids": gone}, ensure_ascii=False, indent=1) + "\n",
        "codebook.json": json.dumps({"version": cb.VERSION, "review_status": cb.REVIEW_STATUS,
                                     "case_fields": dict(cb.CASE_FIELDS), "variables": cb.VARIABLES,
                                     "claimants": cb.CLAIMANTS, "claim_topics": cb.CLAIM_TOPICS},
                                    ensure_ascii=False, indent=1) + "\n",
    }
    readme = (f"{cfg['site']['name']}\n{site_url}\nData as of {updated}. Codebook version {cb.VERSION}.\n\n"
              "Coded values are machine-drafted and not yet reviewed by a person. See CODEBOOK.md.\n"
              f"Corrections and suggestions: {cfg['site']['contact_email']}\n\n"
              f"Data licence: {cfg['license']['data']} (https://creativecommons.org/licenses/by/4.0/).\n"
              f"Cite as: CrimConsortium. {cfg['site']['name']} [dataset]. {site_url} (data as of {updated}).\n")
    for name, text in files.items():
        write_if_changed(DATA / name, text)
    write_if_changed(ROOT / "CODEBOOK.md", cb.markdown() + "\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in {**files, "CODEBOOK.md": cb.markdown() + "\n", "README.txt": readme}.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))  # fixed stamp: same data, same file
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text)
    write_if_changed(DATA / "self-driving-incidents.zip", buf.getvalue())


def write_site_data(published: list[tuple[dict, dict]], updated: str) -> None:
    """Compact index used by the search page."""
    rows = []
    for c, v in published:
        vals = v["vals"]
        blob = " ".join([v["id"], " ".join(v["merged"]), v["lead"], v["title"], v["summary"] or "", v["narrative"],
                         " ".join(s["publisher"] for s in v["sources"]),
                         # Codebook order, so the file is the same whether a case was coded in this run or loaded from disk.
                         " ".join(human(vals[var["name"]]) for var in cb.VARIABLES if var["name"] in vals)]).lower()
        rows.append({
            "id": v["id"], "url": v["url"], "lead": v["lead"], "date": v["date_label"], "sort": v["sort"],
            "title": v["title"], "summary": v["summary"], "by": v["summary_by"], "kind": v["summary_kind"],
            "tags": v["tags"], "n": len(v["sources"]),
            "src": [{"p": s["publisher"], "u": s["url"]} for s in v["sources"][:3]],
            "f": {"system": vals.get("system_named") or [], "status": vals.get("engagement_status") or "",
                  "type": vals.get("incident_type") or "", "deaths": 1 if vals.get("fatalities") else 0,
                  "state": vals.get("location_state_region") or "", "year": v["sort"][:4]},
            "q": blob})
    labels = {"system": {k: human(k) for k in cb.BY_NAME["system_named"]["values"]},
              "status": STATUS_BADGE,
              "type": {k: human(k) for k in cb.BY_NAME["incident_type"]["values"]}}
    js = "window.SDI = " + json.dumps({"updated": updated, "labels": labels, "cases": rows},
                                      ensure_ascii=False, separators=(",", ":")) + ";\n"
    write_if_changed(DATA / "site-data.js", js)


# --------------------------------------------------------------------------- everything

def export_all(store: dict, cfg: dict) -> dict:
    published = [c for c in store["cases"] if c["status"] == "published"]
    excluded = [c for c in store["cases"] if c["status"] == "excluded"]
    retired = store.get("retired", [])
    merged = merged_ids(store)
    pairs = [(c, view(c, cfg, merged.get(c["case_id"]))) for c in published]
    pairs.sort(key=lambda p: (p[1]["sort"], p[1]["first"], p[1]["id"]), reverse=True)
    updated = max((c["updated"][:10] for c in published), default=date.today().isoformat())
    write_downloads(pairs, excluded, cfg, updated, retired)
    write_site_data(pairs, updated)
    pages.write_pages(pairs, cfg, updated, n_reports=sum(len(c["sources"]) for c in published),
                      stats=pages.sampling_stats(store, cfg), retired=retired)
    return {"cases": len(published), "sources": sum(len(c["sources"]) for c in published),
            "excluded": len(excluded), "retired_ids": len(retired)}
