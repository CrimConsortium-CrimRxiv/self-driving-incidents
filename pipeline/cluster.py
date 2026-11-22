"""Decide which reports describe the same incident."""
from __future__ import annotations

import re
from datetime import datetime

from rapidfuzz import fuzz

from .collect import US_STATES, _STATE_NAMES, Item
from .common import normalize_title

_COMMON = {
    "tesla", "crash", "crashes", "crashed", "accident", "collision", "fire", "model", "driver", "car",
    "vehicle", "cybertruck", "cybercab", "robotaxi", "killed", "fatal", "injured", "after", "with",
    "into", "from", "that", "this", "says", "police", "the", "and", "for", "on", "in", "of", "a", "to",
    "at", "is", "was", "by", "an", "autopilot", "fsd", "self", "driving", "full", "new", "report",
    "kills", "dies", "died", "dead", "deadly", "fires", "injures", "injuring", "killing", "mode",
    "engaged", "autonomous", "driverless", "lawsuit", "while", "during", "hits", "hit",
}
_GENERIC = set("""a an the and or of to in on at by for with from as is was were be been has have had her his
their its it this that after before during while when who what which near into over under than then there
they she he we you our your are not but about also says said say state officials mode year old highway
county road street monday tuesday wednesday thursday friday saturday sunday night
morning afternoon evening week weeks one two three people man woman driver drivers
allegedly alleged following follow found just late along scene directed arrived reportedly according
early new latest video watch photos update
january february march april may june july august september october november december
four five six seven eight nine ten dozen first second third more most
report reports reported data file files filed filing record records list nhtsa ntsb federal
involv includ additional investigation investigat identifi happen show shows""".split())
_GENERIC |= {str(y) for y in range(2015, 2036)}

# Different outlets word the same detail differently; map those to one shared word before comparing.
_CANON = [
    (re.compile(r"\b(?:i|interstate)[\s-]*(\d{1,3})\b", re.I), r"interstate i\1"),
    (re.compile(r"\b(?:dui|dwi|owi|ovi|drunk|drunken|intoxicated|intoxication|impaired|under the influence|"
                r"alcohol|blood alcohol)\b", re.I), "impaired"),
    (re.compile(r"\b(?:arrested|arrest|arrests|charged|charges|charge|booked|faces|facing)\b", re.I), "charged"),
]
_AGENCIES = re.compile(r"\b(?:[a-z]+ )?(?:highway patrol|state police|state patrol|police department|"
                       r"sheriff s office|sheriffs office|sheriff)\b")


def _canon(text: str) -> str:
    for rx, rep in _CANON:
        text = rx.sub(rep, text)
    return text


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _distinct_tokens(norm: str) -> set[str]:
    return {w for w in norm.split() if len(w) > 2 and w not in _COMMON}


def same_story(a: str, b: str, threshold: int) -> bool:
    """Headlines are the same report if they're >= threshold similar, or if they share 3+
    distinctive words (not 'Tesla', 'crash', etc.) and one is mostly contained in the other."""
    if fuzz.token_sort_ratio(a, b) >= threshold:
        return True
    return len(_distinct_tokens(a) & _distinct_tokens(b)) >= 3 and fuzz.token_set_ratio(a, b) >= 80


def group_items(items: list[Item], threshold: int) -> list[list[Item]]:
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if same_story(items[i].norm, items[j].norm, threshold):
                parent[find(i)] = find(j)
    groups: dict[int, list[Item]] = {}
    for i, it in enumerate(items):
        groups.setdefault(find(i), []).append(it)
    return list(groups.values())


# --------------------------------------------------------------------------- case-level comparison

def case_text(case: dict) -> str:
    parts = [case.get("headline") or "", case.get("source_summary") or ""]
    parts += [s.get("title") or "" for s in case.get("sources", [])]
    return " ".join(parts)


def case_tokens(case: dict) -> set[str]:
    t = _AGENCIES.sub(" ", normalize_title(_canon(case_text(case))))
    publishers = {w for s in case.get("sources", []) for w in normalize_title(s.get("publisher") or "").split()}
    return {_stem(w) for w in t.split()
            if len(w) > 2 and w not in _COMMON and w not in _GENERIC and w not in publishers}


def case_states(case: dict) -> set[str]:
    """US states named in full (to avoid 'IN', 'OR') anywhere in the case's headlines or summary."""
    text = " ".join([(case.get("auto") or {}).get("location") or "", case_text(case)])
    found = {n for n in _STATE_NAMES if re.search(rf"\b{re.escape(n)}\b", text)}
    return found


def _day(s: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def days_apart(a: dict, b: dict) -> float:
    """Smallest gap in days between any report in case a and any report in case b."""
    da = [d for d in (_day(s.get("published")) for s in a.get("sources", [])) if d]
    db = [d for d in (_day(s.get("published")) for s in b.get("sources", [])) if d]
    if not da or not db:
        return 9999.0
    return min(abs((x - y).days) for x in da for y in db)


def same_incident(a: dict, b: dict, cfg: dict) -> bool:
    """Rule-based match between two cases. Deliberately cautious: when unsure it says no, and the
    coding step gets a second look with the candidate list."""
    threshold = int(cfg.get("similarity_threshold", 75))
    need = int(cfg.get("merge_min_shared_words", 4))
    gap = days_apart(a, b)
    sa, sb = case_states(a), case_states(b)
    if sa and sb and not (sa & sb):
        return False  # clearly different places
    if gap <= 45:
        ta = [normalize_title(s["title"]) for s in a.get("sources", [])]
        tb = [normalize_title(s["title"]) for s in b.get("sources", [])]
        if any(same_story(x, y, threshold) for x in ta for y in tb):
            return True
    if gap <= 5:
        ka, kb = case_tokens(a), case_tokens(b)
        shared, small = len(ka & kb), min(len(ka), len(kb))
        if shared >= need or (small and shared >= 3 and shared == small):
            return True
    return False


def candidates(case: dict, others: list[dict], limit: int = 6) -> list[dict]:
    """Earlier cases that share specific words with this one, for the coder to compare against."""
    toks = case_tokens(case)
    scored = []
    for o in others:
        if o is case:
            continue
        n = len(toks & case_tokens(o))
        if n >= 2:
            scored.append((n, o))
    scored.sort(key=lambda p: (-p[0], p[1].get("first_reported") or ""))
    return [o for _, o in scored[:limit]]
