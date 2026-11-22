"""Collect news reports, keep those about automated-driving incidents, and draft simple labels."""
from __future__ import annotations

import calendar
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import requests

from .common import log, normalize_title, strip_source_suffix, word_pattern

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}


@dataclass
class Item:
    title: str            # headline without " - Source"
    norm: str             # normalised headline
    url: str              # link as found in the feed
    source: str           # publisher name
    published: datetime
    maker: str = "Tesla"
    direct_url: str | None = None   # publisher's own link, when it could be resolved
    snippet: str | None = None      # description supplied by the feed (Bing only)

    @property
    def link(self) -> str:
        return self.direct_url or self.url


# --------------------------------------------------------------------------- feeds

def google_url(query: str, window: str) -> str:
    q = urllib.parse.quote(f"{query} {window}".strip())
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def feed_urls(cfg: dict, windows: list[str] | None = None) -> list[tuple[str, str]]:
    """Return (maker, url) pairs. `windows` are Google News date filters such as 'when:7d'
    or 'after:2026-09-01 before:2026-09-15'."""
    windows = windows or [f"when:{int(cfg.get('lookback_days', 7))}d"]
    out = []
    for maker in cfg["makers"]:
        for q in maker.get("queries", []):
            for w in windows:
                out.append((maker["name"], google_url(q, w)))
        if windows == [f"when:{int(cfg.get('lookback_days', 7))}d"]:
            for q in maker.get("bing_queries", []):
                out.append((maker["name"], "https://www.bing.com/news/search?format=rss&q="
                            + urllib.parse.quote(q)))
    return out


def _bing_target(link: str) -> str:
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    return qs.get("url", [link])[0]


def fetch_feeds(urls: list[tuple[str, str]]) -> tuple[list[Item], list[str]]:
    items: dict[str, Item] = {}
    failures: list[str] = []
    for maker, url in urls:
        try:
            resp = requests.get(url, headers=UA, timeout=30)
            for wait in (8, 20):  # news searches sometimes answer "too many requests"; wait and retry
                if resp.status_code not in (429, 503):
                    break
                time.sleep(wait)
                resp = requests.get(url, headers=UA, timeout=30)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(f"unreadable feed: {parsed.bozo_exception}")
        except Exception as exc:  # log and keep going
            log.warning("Feed failed (%s): %s", url[:100], exc)
            failures.append(url)
            continue
        bing = "bing.com" in url
        n = 0
        for e in parsed.entries:
            link = e.get("link")
            if not link:
                continue
            src = e.get("news_source") if bing else (e.get("source") or {}).get("title")
            src = (src or "").strip()
            direct = _bing_target(link) if bing else None
            key = direct or link
            if key in items:
                continue
            if e.get("published_parsed"):
                pub = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
            else:
                pub = datetime.now(timezone.utc)
            raw = e.get("title", "")
            items[key] = Item(
                title=strip_source_suffix(raw, src or None),
                norm=normalize_title(raw, src or None),
                url=key, source=src or "News source", published=pub, maker=maker,
                direct_url=direct,
                snippet=(e.get("summary") or None) if bing else None,
            )
            n += 1
        log.info("Feed ok: %d entries (%s)", n, urllib.parse.unquote(url)[:110])
        time.sleep(1.0)  # be polite to the news searches
    return list(items.values()), failures


# --------------------------------------------------------------------------- filter

def relevant(items: list[Item], cfg: dict) -> list[Item]:
    """Keep headlines that name an automated-driving feature (in the headline or the feed's own
    description) and point to something that happened. Every search already names the maker, so a
    headline that omits it ("self-driving car hits construction equipment") is still kept; the
    coding step later records the make and screens out other makers."""
    kw = cfg["keywords"]
    auto, incident, excl = (word_pattern(kw["automation"]), word_pattern(kw["incident"]),
                            word_pattern(kw["exclude"]))
    out = []
    for it in items:
        text = it.title + " " + (it.snippet or "")
        if excl.search(it.title) or not auto.search(text) or not incident.search(it.title):
            continue
        out.append(it)
    return out


# --------------------------------------------------------------------------- extraction
_MODEL_RX = [
    (re.compile(r"\bmodel\s?(s|3|x|y)\b", re.I), lambda m: f"Tesla Model {m.group(1).upper()}"),
    (re.compile(r"\bcybertrucks?\b", re.I), lambda m: "Tesla Cybertruck"),
    (re.compile(r"\bcybercabs?\b", re.I), lambda m: "Tesla Cybercab"),
    (re.compile(r"\btesla\s+semi\b", re.I), lambda m: "Tesla Semi"),
    (re.compile(r"\btesla\s+roadster\b", re.I), lambda m: "Tesla Roadster"),
    (re.compile(r"\btesla\s+robotaxis?\b", re.I), lambda m: "Tesla Robotaxi"),
]

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "Washington, D.C.",
}
OTHER_PLACES = [
    "Ontario", "Quebec", "British Columbia", "Alberta", "Manitoba", "Nova Scotia", "Saskatchewan",
    "Canada", "Mexico", "China", "Shanghai", "Beijing", "Hong Kong", "Taiwan", "Japan", "South Korea",
    "Korea", "India", "Australia", "New Zealand", "Germany", "Berlin", "France", "Paris", "Italy",
    "Spain", "Norway", "Oslo", "Sweden", "Denmark", "Finland", "Netherlands", "Belgium",
    "Switzerland", "Austria", "Poland", "Ireland", "Scotland", "England", "London", "UK",
    "United Kingdom", "Israel", "Turkey", "Dubai", "UAE", "Saudi Arabia", "Singapore", "Thailand",
    "Malaysia", "Philippines", "Chile", "South Africa",
    # Frequently named U.S. cities (headlines often omit the state)
    "Austin", "Dallas", "Houston", "San Antonio", "Los Angeles", "San Francisco", "San Diego",
    "San Jose", "Oakland", "Sacramento", "Las Vegas", "Phoenix", "Scottsdale", "Denver", "Seattle",
    "Portland", "Chicago", "Detroit", "Atlanta", "Miami", "Orlando", "Tampa", "Jacksonville",
    "New York City", "Brooklyn", "Queens", "Manhattan", "the Bronx", "Boston", "Philadelphia",
    "Pittsburgh", "Baltimore", "Charlotte", "Nashville", "Memphis", "New Orleans", "Minneapolis",
    "St. Louis", "Kansas City", "Salt Lake City", "Albuquerque", "Fremont", "Palo Alto",
    "Bay Area", "Silicon Valley", "Long Island", "Cleveland", "Columbus", "Cincinnati",
    "Indianapolis", "Milwaukee", "Raleigh", "Richmond", "Honolulu", "Anchorage", "Fort Worth",
    "El Paso", "Tucson", "Fresno", "Bakersfield", "Irvine", "Long Beach", "Santa Monica",
    "Pasadena", "Berkeley", "Boulder", "Spokane", "Tacoma", "Omaha", "Tulsa", "Oklahoma City",
    "Louisville", "Lexington", "Birmingham", "Savannah", "Charleston", "Buffalo", "Rochester",
    "Newark", "Jersey City", "Hartford", "Providence",
]
_STATE_NAMES = sorted(set(US_STATES.values()) - {"Washington, D.C."}, key=len, reverse=True)
_NOT_PLACES = {
    "tesla", "autopilot", "full", "self", "fsd", "mode", "model", "cybertruck", "cybercab", "robotaxi",
    "crash", "the", "a", "an", "front", "traffic", "court", "custody", "jail", "flames", "fire",
    "critical", "serious", "stable", "condition", "lawsuit", "video", "photos", "pictures", "garage",
    "parking", "driveway", "lane", "lanes", "neighborhood", "wrong", "way", "snow", "rain", "test",
}
_PLACE_SUFFIX = r"(?:County|Parish|Township|City|Borough|Village)"
_CAP = r"[A-Z][a-zA-Z.'\-]+"


def _title_case_heavy(text: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text) if len(w) > 3]
    if len(words) < 4:
        return False
    return sum(w[0].isupper() for w in words) / len(words) > 0.6


def extract_model(text: str) -> str | None:
    for rx, fmt in _MODEL_RX:
        m = rx.search(text)
        if m:
            return fmt(m)
    return None


def extract_location(text: str) -> str | None:
    """Best-effort place name from a headline. Returns None rather than guessing."""
    # 1) "City, ST" or "City, State"
    states_alt = "|".join(re.escape(s) for s in _STATE_NAMES)
    m = re.search(rf"\b((?:{_CAP}\s){{0,2}}{_CAP}),\s+({states_alt}|[A-Z]{{2}})\b", text)
    if m and (m.group(2) in US_STATES or m.group(2) in _STATE_NAMES):
        city = m.group(1).split()
        city = " ".join(w for w in city if w.lower() not in _NOT_PLACES)
        state = US_STATES.get(m.group(2), m.group(2))
        if city:
            return f"{city}, {state}"
    # 2) "... X County" etc.
    m = re.search(rf"\b((?:{_CAP}\s){{0,2}}{_PLACE_SUFFIX})\b", text)
    county = None
    if m:
        words = [w for w in m.group(1).split() if w.lower() not in _NOT_PLACES]
        if len(words) >= 2:
            county = " ".join(words)
    # 3) Known places (state names, countries, big cities)
    known = None
    for place in sorted(_STATE_NAMES + OTHER_PLACES, key=len, reverse=True):
        if re.search(rf"(?<![A-Za-z]){re.escape(place)}(?![A-Za-z])", text):
            known = place
            break
    if known == "Washington" and re.search(r"Washington,? D\.?C\.?", text):
        known = "Washington, D.C."
    if county and known and known not in county:
        return f"{county}, {known}" if known in _STATE_NAMES else county
    if county:
        return county
    if known:
        return known
    # 4) "in <Place>" -- only for sentence-case headlines, where capitals are meaningful
    if not _title_case_heavy(text):
        m = re.search(rf"\b(?:in|near|outside)\s+((?:{_CAP}\s){{0,2}}{_CAP})", text)
        if m:
            words = m.group(1).split()
            if words and all(w.lower() not in _NOT_PLACES for w in words):
                return " ".join(words).rstrip(".,:;")
    return None


def tag_story(text: str, cfg: dict) -> list[dict]:
    """Word-match labels. They only ever say a term was mentioned in coverage."""
    tags = []
    for t in cfg["tags"]:
        if word_pattern(t["words"]).search(text or ""):
            tags.append({"key": t["key"], "label": t["label"]})
    return tags
