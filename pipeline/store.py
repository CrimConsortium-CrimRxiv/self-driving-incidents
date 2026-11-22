"""The case store: one JSON file that is only ever added to or revised, never wiped."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .common import ROOT

STORE = ROOT / "store" / "cases.json"
SCHEMA = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path=STORE) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"schema": SCHEMA, "next_id": 1, "next_key": 1, "cases": []}


def save(store: dict, path=STORE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(store, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def known_urls(store: dict) -> set[str]:
    out = set()
    for c in store["cases"]:
        for s in c["sources"]:
            out.add(s["url"])
            if s.get("feed_url"):
                out.add(s["feed_url"])
    return out


def known_reports(store: dict) -> set[tuple[str, str]]:
    return {(s["publisher"].lower(), s["title"].lower()) for c in store["cases"] for s in c["sources"]}


def new_case(store: dict, maker: str) -> dict:
    case = {
        "key": f"k{store['next_key']}", "case_id": None, "status": "pending", "maker": maker,
        "added": now_iso(), "updated": now_iso(), "headline": "", "headline_publisher": "",
        "source_summary": None, "source_summary_publisher": None,
        "auto": {"model": None, "location": None, "tags": []},
        "sources": [], "coding": None, "needs_coding": True, "code_attempts": 0,
        "exclusion_reason": None,
    }
    store["next_key"] += 1
    store["cases"].append(case)
    return case


def assign_id(store: dict, case: dict) -> None:
    if not case.get("case_id"):
        case["case_id"] = f"SDI-{store['next_id']:05d}"
        store["next_id"] += 1


def first_reported(case: dict) -> str:
    return min((s["published"] for s in case["sources"] if s.get("published")), default="")[:10]


def last_reported(case: dict) -> str:
    return max((s["published"] for s in case["sources"] if s.get("published")), default="")[:10]
