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
    # stock headline phrases ("What owners need to know") that say nothing about which event it is
    "what", "owners", "owner", "need", "know", "should", "means", "mean", "matter", "details", "really",
    "here", "why", "how", "watch", "video", "now",
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
involv includ additional investigation investigat identifi happen show shows
national traffic safety administration transportation board agency department public
system technology feature software assistance assist automated summon smart supervised unsupervised
month months since through time using used use operating operated behind wheel being via whilst back""".split())
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


# --------------------------------------------------------------------------- report-level comparison

WINDOW_DAYS = 45   # two reports further apart than this are never matched by rule
CLOSE_DAYS = 5     # shared specific words only count between reports this close together
_STATE_RX = [(n, re.compile(rf"\b{re.escape(n)}\b")) for n in _STATE_NAMES]
_GENERIC_STEMS = {_stem(w) for w in _GENERIC | _COMMON} | {"interstate"}  # a road counts once, by its number
_ROAD = re.compile(r"i\d{1,3}")
_SIGS: dict[tuple, dict] = {}
_CASE_STATES: dict[str, set[str]] = {}


def _specific(text: str, publisher: str = "") -> set[str]:
    """Words that say which event this is (places, road numbers, charges), in a common form."""
    skip = set(normalize_title(publisher or "").split())
    out = set()
    for w in _AGENCIES.sub(" ", normalize_title(_canon(text))).split():
        if (len(w) <= 2 and not _ROAD.fullmatch(w)) or w in _COMMON or w in _GENERIC or w in skip:
            continue
        stem = _stem(w)
        if stem not in _GENERIC_STEMS:
            out.add(stem)
    return out


def _states(text: str) -> set[str]:
    """US states named in full (to avoid 'IN', 'OR')."""
    return {n for n, rx in _STATE_RX if rx.search(text)}


def _day(s) -> datetime | None:
    if isinstance(s, datetime):
        return datetime(s.year, s.month, s.day)
    try:
        return datetime.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def signature(title: str, publisher: str, published, summary: str | None = None) -> dict:
    """What the matching rules need to know about one report. Cached, since each is compared often."""
    key = (title, publisher, str(published)[:10], summary or "")
    sig = _SIGS.get(key)
    if sig is None:
        norm = normalize_title(title, publisher or None)
        text = f"{title} {summary or ''}"
        sig = _SIGS[key] = {"norm": norm, "words": _distinct_tokens(norm), "specific": _specific(text, publisher),
                            "states": _states(text), "day": _day(published)}
    return sig


def _source_sig(s: dict) -> dict:
    return signature(s.get("title") or "", s.get("publisher") or "", s.get("published"),
                     s.get("summary") or s.get("snippet"))


def same_report_event(x: dict, y: dict, threshold: int, need: int) -> bool:
    """Do two reports (as signatures) describe the same event? The dates compared are those of the two
    reports themselves, so a case that has gathered months of coverage does not attract unrelated news."""
    if not x["day"] or not y["day"]:
        return False
    gap = abs((x["day"] - y["day"]).days)
    if gap > WINDOW_DAYS:
        return False
    if x["states"] and y["states"] and not (x["states"] & y["states"]):
        return False  # clearly different places
    alike = fuzz.token_sort_ratio(x["norm"], y["norm"])
    shared = len(x["words"] & y["words"])
    # Near-identical headlines, or similar headlines that share at least two distinctive words.
    # Similar wording alone is not enough: "Tesla in self-driving mode involved in crash" fits many events.
    if alike >= max(90, threshold) or (alike >= threshold and shared >= 2):
        return True
    if shared >= 3 and fuzz.token_set_ratio(x["norm"], y["norm"]) >= 80:
        return True
    if gap <= CLOSE_DAYS:
        common, small = len(x["specific"] & y["specific"]), min(len(x["specific"]), len(y["specific"]))
        if common >= need or (small and common >= 3 and common == small):
            return True
    return False


def group_items(items: list[Item], cfg: dict) -> list[list[Item]]:
    threshold = int(cfg.get("similarity_threshold", 75))
    need = int(cfg.get("merge_min_shared_words", 4))
    sigs = [signature(i.title, i.source, i.published, i.snippet) for i in items]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if same_report_event(sigs[i], sigs[j], threshold, need):
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
    out = _specific(" ".join([case.get("headline") or "", case.get("source_summary") or ""]))
    for src in case.get("sources", []):
        out |= _source_sig(src)["specific"]
    return out


def case_states(case: dict) -> set[str]:
    """US states named in full anywhere in the case's headlines or summary."""
    text = " ".join([(case.get("auto") or {}).get("location") or "", case_text(case)])
    found = _CASE_STATES.get(text)
    if found is None:
        found = _CASE_STATES[text] = _states(text)
    return found


def same_incident(a: dict, b: dict, cfg: dict) -> bool:
    """Rule-based match between two cases: true when any report in one matches any report in the
    other. Deliberately cautious: when unsure it says no, and the coding step gets a second look
    with the candidate list."""
    threshold = int(cfg.get("similarity_threshold", 75))
    need = int(cfg.get("merge_min_shared_words", 4))
    sa, sb = case_states(a), case_states(b)
    if sa and sb and not (sa & sb):
        return False  # clearly different places
    xs = [_source_sig(s) for s in a.get("sources", [])]
    ys = [_source_sig(s) for s in b.get("sources", [])]
    return any(same_report_event(x, y, threshold, need) for x in xs for y in ys)


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
