"""Draft the coded record for a case with a language model, then check every answer.

The model sees only the reports attached to the case. Its answers are treated as proposals:
a value is kept only when the quotation offered for it is found, word for word, in the report.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta

from . import codebook as cb
from .common import log, norm_for_match, word_pattern
from .store import last_reported, now_iso


class RateLimited(Exception):
    """The free daily or per-minute allowance is used up; stop coding until the next run."""


class CoderUnavailable(Exception):
    """No token, or the service refused every model."""


SYSTEM = """You code news reports for an academic dataset of incidents in which a vehicle's \
automated-driving feature (Autopilot, Full Self-Driving, Summon, a robotaxi, "self-driving mode" and \
the like) is claimed, questioned or confirmed to be involved.

Rules:
1. Use ONLY the reports supplied. No outside knowledge. If the reports do not state something, leave \
that variable out. Never guess.
2. Every variable you code needs "quote": words copied exactly, character for character, from one \
supplied report (at most 30 words, a single continuous passage), and "source": that report's number.
3. A mention of an automated-driving feature is NOT evidence it was in use. Follow the definitions of \
engagement_status exactly. Use confirmed_by_official_source only when an official finding or the \
manufacturer's own data report says so.
4. Never judge fault or cause yourself. Record who says what.
5. Do not name private individuals (drivers, victims, witnesses, relatives) in "narrative", \
"paraphrase" or text values; write "the driver", "a passenger". Companies, agencies and officials \
acting in their role may be named. Prefer quotes that contain no private individual's name.
6. Neutral, plain wording. No judgemental adjectives.

Screening:
- is_specific_incident: true when the reports are mainly about ONE identifiable event at a particular \
place and time, including later investigation or court coverage of that event. False for statistics \
or round-ups of several incidents, product or software news, policy, opinion, reviews, or business news.
- multiple_incidents: true when the reports describe two or more separate incidents and none is \
clearly the main subject.
- automation_in_question: true when any report says, alleges, denies or asks whether an \
automated-driving feature was in use or involved in the event.
- same_incident_as: if this is the same real-world event as one of the EARLIER CASES listed, give that \
case's ref; otherwise null. Same event means same place, same date and same circumstances.

Answer with one JSON object and nothing else:
{"screen": {"is_specific_incident": true|false, "multiple_incidents": true|false, \
"automation_in_question": true|false, "reason": "one short sentence"},
 "same_incident_as": null or "ref",
 "variables": {"<name>": {"value": <value>, "quote": "...", "source": <number>}, ...},
 "claims": [{"claimant": "<who>", "topic": "<topic>", "paraphrase": "...", "quote": "...", "source": <number>}],
 "narrative": "2 to 4 neutral sentences on what the reports say happened and who says what."}
If is_specific_incident or automation_in_question is false, or multiple_incidents is true, return \
empty "variables" and "claims" and an empty "narrative". Give at most 6 claims."""


# --------------------------------------------------------------------------- prompt

def _weekday(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso[:10]).strftime("%A")
    except ValueError:
        return ""


def build_messages(case: dict, reports: list[dict], earlier: list[dict], cfg: dict) -> list[dict]:
    """`reports` = [{'n': 1, 'publisher', 'published', 'title', 'summary', 'text'}]."""
    opts = cfg["coder"]
    head = ["CODEBOOK (variable: definition)", cb.prompt_codebook(), "",
            "Claim \"claimant\" options: " + ", ".join(cb.CLAIMANTS),
            "Claim \"topic\" options: " + "; ".join(f"{k} = {d}" for k, d in cb.CLAIM_TOPICS.items()), ""]
    if earlier:
        head.append("EARLIER CASES")
        for e in earlier:
            head.append(f"- ref {e['ref']}: first reported {e['first_reported']}; {e['headline'][:140]}"
                        + (f" | {e['summary'][:160]}" if e.get("summary") else ""))
        head.append("")
    fixed = len(SYSTEM) + sum(len(x) + 1 for x in head)
    basics = [f"REPORT {r['n']}: {r['publisher']}, published {r['published'][:10]} "
              f"({_weekday(r['published'])})\nHeadline: {r['title']}\n"
              + (f"Publisher's summary: {r['summary']}\n" if r.get("summary") else "") for r in reports]
    room = int(opts.get("max_prompt_chars", 25000)) - fixed - sum(len(b) for b in basics) - 200
    with_text = [r for r in reports if r.get("text")]
    share = max(0, room // max(1, len(with_text)))
    body = []
    for r, b in zip(reports, basics):
        text = (r.get("text") or "")[:share]
        r["given"] = " \n ".join(x for x in (r["title"], r.get("summary") or "", text) if x)
        body.append(b + (f"Text: {text}\n" if text else ""))
    user = "\n".join(head) + "REPORTS\n\n" + "\n".join(body)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


# --------------------------------------------------------------------------- model call

def call_model(messages: list[dict], cfg: dict) -> tuple[dict, str]:
    """Send one case to the language model. Returns (its answer, the name recorded as the coder)."""
    opts = cfg["coder"]
    key = os.environ.get(opts.get("key_env", "OPENAI_API_KEY"), "").strip()
    if not key:
        raise CoderUnavailable(f"no API key ({opts.get('key_env', 'OPENAI_API_KEY')} is not set)")
    import openai  # imported here so collecting and rebuilding work without it

    client = openai.OpenAI(api_key=key, base_url=opts.get("base_url") or None, timeout=300, max_retries=2)
    system = next(m["content"] for m in messages if m["role"] == "system")
    user = next(m["content"] for m in messages if m["role"] == "user")
    last = "no model configured"
    for model in opts["models"]:
        request = {"model": model, "instructions": system, "input": user,
                   "max_output_tokens": int(opts.get("max_output_tokens", 12000)),
                   "text": {"format": {"type": "json_object"}}}
        if opts.get("effort"):
            request["reasoning"] = {"effort": opts["effort"]}
        for attempt in (1, 2):
            try:
                resp = client.responses.create(**request)
            except openai.RateLimitError as exc:
                raise RateLimited(f"{model}: {str(exc)[:200]}") from exc
            except openai.AuthenticationError as exc:
                raise CoderUnavailable(f"the API key was refused ({str(exc)[:120]})") from exc
            except openai.APIError as exc:
                last = f"{model}: {str(exc)[:200]}"
                log.warning("Coder refused: %s", last)
                break  # try the next model
            try:
                if resp.status != "completed":
                    raise ValueError(f"reply {resp.status}")
                return json.loads(_strip_fence(resp.output_text)), f"{opts.get('provider', 'OpenAI')} {model}"
            except (ValueError, TypeError) as exc:
                last = f"{model}: unreadable answer ({exc})"
                log.warning("Coder answer unreadable (attempt %d): %s", attempt, exc)
    raise CoderUnavailable(last)


def _strip_fence(text: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())


# --------------------------------------------------------------------------- checks

def find_quote(quote: str, reports: list[dict], source, max_chars: int = 300) -> tuple[str, int] | None:
    """Return (quote, report number) when the quotation is found word for word in a supplied report.
    The cited report is tried first; a quotation found in a different supplied report is re-attributed."""
    q = re.sub(r"\s+", " ", str(quote or "")).strip().strip("\"\u201c\u201d")
    if len(q) < 8 or len(q) > max_chars:
        return None
    parts = [p.strip() for p in re.split(r"\s*(?:\.\.\.|\u2026)\s*", q) if len(p.strip()) >= 8]
    if not parts:
        return None
    needles = [norm_for_match(p) for p in parts]
    order = sorted(reports, key=lambda r: 0 if str(r["n"]) == str(source) else 1)
    for r in order:
        hay = norm_for_match(r.get("given", ""))
        if all(n in hay for n in needles):
            return q, r["n"]
    return None


_NAME = r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-zA-Z'\-]+){1,2}"
_NAME_PATTERNS = [re.compile(p) for p in (
    rf"\b({_NAME}),? (?:age |aged )?\d{{1,2}}\b",                      # Jane Doe, 37
    rf"\b({_NAME}),? (?:a|an) \d{{1,2}}-year-old\b",                   # Jane Doe, a 25-year-old
    rf"\b({_NAME}), who (?:was|is) \d{{1,2}}\b",                       # Jane Doe, who was 71
    rf"\b\d{{1,2}}-year-old ({_NAME})",                                 # 57-year-old Jane Doe
    rf"\bidentified (?:as|by \w+ as|the (?:driver|operator|owner|victim|man|woman|passenger|pedestrian"
    rf"|motorist|suspect|deceased|occupant) as) ({_NAME})",
    rf"\b(?:driven by|operated by|owned by|home of|named|driver|motorist|passenger|pedestrian|victim"
    rf"|(?:daughter|son|wife|husband|mother|father|brother|sister|widow|family|estate) of"
    rf"|(?:boyfriend|girlfriend|fianc\u00e9|fianc\u00e9e|wife|husband|daughter|son|friend),) ({_NAME})",
)]
_NOT_NAMES = word_pattern([
    "tesla", "model", "police", "county", "state", "highway", "patrol", "interstate", "route", "sheriff",
    "department", "autopilot", "cybertruck", "cybercab", "full", "self-driving", "robotaxi", "waymo", "zoox",
    "nhtsa", "ntsb", "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "the", "a", "an", "on", "in", "at", "of", "by", "for", "from", "to", "and", "after", "before",
    "has", "have", "had", "was", "is", "are", "were", "already", "about", "around", "near", "over", "under",
    "township", "city", "town", "village", "borough", "parkway", "road", "street", "avenue", "boulevard",
    "drive", "lane", "bridge", "hills", "heights", "beach", "springs", "lake", "park", "valley", "grove",
    "north", "south", "east", "west", "new", "company", "number", "fire", "court", "district", "office",
    "university", "hospital", "school", "news", "times", "post"])


def private_names(reports: list[dict]) -> list[str]:
    """Names of people that reports introduce with an age, a family tie or a role such as
    'driven by'. Officials quoted with a title are not matched. Best effort."""
    found = set()
    for r in reports:
        text = r.get("given", "")
        for rx in _NAME_PATTERNS:
            for m in rx.finditer(text):
                name = m.group(1).strip()
                if not _NOT_NAMES.search(name):
                    found.add(name)
                    found.add(name.split()[-1])  # later mentions use the surname alone
                    if len(name.split()) == 3:   # "Benavides Leon" after "Naibel Benavides Leon"
                        found.add(" ".join(name.split()[1:]))
    return sorted((n for n in found if len(n) >= 2), key=len, reverse=True)


def scrub(text: str, names: list[str], mark: str) -> str:
    for n in names:
        text = re.sub(rf"\b{re.escape(n)}(?:'s|\u2019s)?\b", mark, text)
    if mark and mark in text:   # collapse "[name] [name]" left by a first name + surname
        text = re.sub(rf"(?:{re.escape(mark)}\s*)+", mark + " ", text)
        text = re.sub(r"\s+([,.;:])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _clean_value(var: dict, value):
    kind = var["kind"]
    if kind == "enum":
        v = str(value).strip().lower()
        return v if v in var["values"] else None
    if kind == "multi":
        vals = value if isinstance(value, list) else [value]
        keep = [str(v).strip().lower() for v in vals if str(v).strip().lower() in var["values"]]
        return sorted(set(keep), key=list(var["values"]).index) or None
    if kind == "int":
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return n if 0 <= n <= 3000 else None
    if kind == "date":
        v = str(value).strip()
        return v if re.fullmatch(r"(19|20)\d{2}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?", v) else None
    v = re.sub(r"\s+", " ", str(value)).strip()
    return v[:120] if v and v.lower() not in ("unknown", "n/a", "none", "not stated", "not_stated", "null") else None


def check(raw: dict, case: dict, reports: list[dict], earlier: list[dict], cfg: dict, model: str) -> dict:
    """Turn the model's answer into a decision: publish / exclude / merge."""
    max_q = int(cfg["coder"].get("max_quote_chars", 300))
    screen = raw.get("screen") or {}
    reason = re.sub(r"\s+", " ", str(screen.get("reason") or "")).strip()[:200]
    if screen.get("multiple_incidents") is True:
        return {"decision": "exclude", "reason": "Covers several incidents; not split into cases. " + reason}
    if screen.get("is_specific_incident") is not True:
        return {"decision": "exclude", "reason": "Not about one identifiable incident. " + reason}
    if screen.get("automation_in_question") is not True:
        return {"decision": "exclude", "reason": "No automated-driving feature in question. " + reason}

    same = raw.get("same_incident_as")
    refs = {e["ref"] for e in earlier}
    if same and str(same) in refs:
        return {"decision": "merge", "target": str(same), "reason": reason}

    names = private_names(reports)
    url_of = {r["n"]: r["url"] for r in reports}
    values, evidence, removed = {}, {}, 0
    for name, ans in (raw.get("variables") or {}).items():
        var = cb.BY_NAME.get(name)
        if not var or not isinstance(ans, dict):
            continue
        value = _clean_value(var, ans.get("value"))
        if value is None:
            continue
        hit = find_quote(ans.get("quote"), reports, ans.get("source"), max_q)
        if not hit:
            removed += 1
            continue
        if var["kind"] == "text":
            value = scrub(value, names, "").strip(" ,;") or None
            if value is None:
                continue
        values[name] = value
        evidence[name] = {"quote": scrub(hit[0], names, "[name]"), "source_url": url_of[hit[1]]}

    # Dates cannot be later than the coverage itself.
    d = values.get("incident_date")
    latest = last_reported(case)
    if d and latest:
        limit = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
        if d > limit[: len(d)]:
            values.pop("incident_date"), evidence.pop("incident_date")
            removed += 1

    make = (values.get("vehicle_make") or "").lower()
    makers = {m["name"].lower(): word_pattern(m["terms"]) for m in cfg["makers"]}
    everything = " ".join(r.get("given", "") for r in reports)
    if make and not any(make == k or p.search(make) for k, p in makers.items()):
        return {"decision": "exclude", "reason": f"Other maker ({values['vehicle_make']})."}
    if not make and not any(p.search(everything) for p in makers.values()):
        return {"decision": "exclude", "reason": "Vehicle maker not identified in the reports read."}

    claims = []
    for c in (raw.get("claims") or [])[:6]:
        if not isinstance(c, dict):
            continue
        who, topic = str(c.get("claimant") or "").lower(), str(c.get("topic") or "").lower()
        para = re.sub(r"\s+", " ", str(c.get("paraphrase") or "")).strip()
        hit = find_quote(c.get("quote"), reports, c.get("source"), max_q)
        if who not in cb.CLAIMANTS or topic not in cb.CLAIM_TOPICS or not para or not hit:
            removed += 1
            continue
        claims.append({"claimant": who, "topic": topic, "paraphrase": scrub(para, names, "[name withheld]")[:400],
                       "quote": scrub(hit[0], names, "[name]"), "source_url": url_of[hit[1]]})

    narrative = scrub(re.sub(r"\s+", " ", str(raw.get("narrative") or "")).strip(), names, "[name withheld]")[:900]
    basis = "full_text" if any(r.get("text") for r in reports) else (
        "summary" if any(r.get("summary") for r in reports) else "headline")
    coding = {
        "review_status": cb.REVIEW_STATUS, "coder": model, "coded_at": now_iso(),
        "codebook_version": cb.VERSION, "text_basis": basis,
        "sources_read": [{"url": r["url"], "basis": "full_text" if r.get("text") else
                          ("summary" if r.get("summary") else "headline")} for r in reports],
        "values": values, "evidence": evidence, "claims": claims, "narrative": narrative,
        "unsupported_values_removed": removed,
    }
    return {"decision": "publish", "coding": coding, "reason": reason}
