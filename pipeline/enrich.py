"""Find each report's own link, its publisher-written summary and, at coding time, its text.

Nothing here is generated. Summaries shown on the site are the publisher's own words (the page's
summary line, or Bing News' snippet of the same article). Article text is read only to code the
case and to check quotations; it is never saved.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse
from html.parser import HTMLParser

import feedparser
import requests
from rapidfuzz import fuzz

from .collect import UA
from .common import log, normalize_title, word_pattern

JUNK = re.compile(r"captcha|cookie|javascript|subscribe|sign up|log in|404|access denied|"
                  r"latest news|breaking news, weather|newsletter|all rights reserved", re.I)


# --------------------------------------------------------------------------- Google News link -> publisher link

def decode_google_link(url: str) -> str | None:
    if "news.google.com" not in url:
        return url
    gid = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    page = requests.get(f"https://news.google.com/rss/articles/{gid}", headers=UA, timeout=12).text
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sg and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None,
                             None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             gid, int(ts.group(1)), sg.group(1)]
    payload = [[["Fbv4je", json.dumps(inner), None, "generic"]]]
    resp = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                         headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                         data="f.req=" + urllib.parse.quote(json.dumps(payload)), timeout=12)
    body = json.loads(resp.text.split("\n\n", 1)[1])[:-2]
    real = json.loads(body[0][2])[1]
    return real if isinstance(real, str) and real.startswith("http") else None


# --------------------------------------------------------------------------- publisher page

_SKIP = {"script", "style", "nav", "footer", "aside", "form", "figure", "figcaption", "noscript",
         "header", "button", "svg", "iframe", "select"}


class _Page(HTMLParser):
    """Collects <meta> summaries and the text of paragraphs outside navigation and page furniture."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.paras: list[str] = []
        self._skip = 0
        self._in_p = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag in _SKIP:
            self._skip += 1
        elif tag == "p" and not self._skip:
            self._in_p, self._buf = True, []

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag == "p" and self._in_p:
            self._in_p = False
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(text) >= 60 and not JUNK.search(text[:160]):
                self.paras.append(text)

    def handle_data(self, data):
        if self._in_p and not self._skip:
            self._buf.append(data)


def read_page(url: str, want_text: bool = False, limit: int = 1_500_000) -> dict:
    """Return {'summary': publisher's summary line or None, 'text': article paragraphs or ''}."""
    out = {"summary": None, "text": ""}
    with requests.get(url, headers=UA, timeout=10, stream=True) as r:
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
            return out
        raw = b""
        for chunk in r.iter_content(65536):
            raw += chunk
            if len(raw) > limit or (not want_text and b"</head>" in raw.lower()):
                break
        enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
    p = _Page()
    try:
        p.feed(raw.decode(enc, errors="replace"))
    except Exception:
        pass
    m = p.meta
    out["summary"] = m.get("og:description") or m.get("description") or m.get("twitter:description")
    if want_text:
        out["text"] = "\n".join(p.paras)
    return out


# --------------------------------------------------------------------------- Bing fallback

def bing_snippet(headline: str) -> str | None:
    r = requests.get("https://www.bing.com/news/search",
                     params={"q": headline, "format": "rss"}, headers=UA, timeout=12)
    want = normalize_title(headline)
    best, score = None, 0
    for e in feedparser.parse(r.content).entries:
        s = fuzz.token_sort_ratio(want, normalize_title(e.get("title", "")))
        if s > score:
            best, score = e, s
    if best is not None and score >= 85:
        return best.get("description") or best.get("summary")
    return None


# --------------------------------------------------------------------------- cleaning

_TOPIC = word_pattern(["tesla", "cybertruck", "cybercab", "robotaxi", "autopilot", "self-driving", "fsd",
                       "crash", "crashed", "collision", "collided", "struck", "hit", "driver", "police",
                       "lawsuit", "vehicle", "car", "killed", "died", "injured", "injuries"])


def clean_text(text: str | None) -> str:
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()


def clean_summary(text: str | None, headline: str, max_chars: int) -> str | None:
    """Tidy a publisher's summary line; return None when it is boilerplate or just repeats the headline."""
    t = clean_text(text)
    if not t:
        return None
    # Drop datelines like "TAMPA, Fla. (WFLA) - "
    t = re.sub(r"^[A-Z][A-Z .'-]{1,30},\s*[A-Z][A-Za-z.]{1,12}\s*(?:\([^)]{1,25}\))?\s*[\u2014\u2013-]+\s*", "", t)
    if len(t) < 40 or len(t.split()) < 7 or JUNK.search(t) or not _TOPIC.search(t):
        return None
    if fuzz.token_sort_ratio(normalize_title(t), normalize_title(headline)) >= 85:
        return None
    if len(t) > max_chars:
        cut = t[:max_chars]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        t = cut[: end + 1] if end > max_chars * 0.5 else cut.rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"
    elif t[-1] not in ".!?\"'\u201d\u2026":
        t += "\u2026"
    return t


# --------------------------------------------------------------------------- per source

def resolve_source(src: dict, max_chars: int) -> None:
    """Fill in the publisher's own link and summary line for one stored source (best effort)."""
    if not src.get("resolved"):
        try:
            real = decode_google_link(src["url"])
        except Exception as exc:
            log.info("Link decode failed (%s): %s", src["publisher"], exc)
            real = None
        if real and real != src["url"]:
            src["feed_url"], src["url"] = src["url"], real
        src["resolved"] = bool(real)
    if src.get("summary") is None and src.get("resolved"):
        try:
            desc = read_page(src["url"])["summary"]
        except Exception:
            desc = None
        src["summary"] = clean_summary(desc, src["title"], max_chars) or ""
    if not src.get("summary"):
        try:
            src["summary"] = clean_summary(bing_snippet(src["title"]), src["title"], max_chars) or ""
        except Exception as exc:
            log.info("Bing lookup failed: %s", exc)
            src["summary"] = src.get("summary") or ""


def article_text(src: dict, max_chars: int = 9000) -> str:
    """Article text for coding. Returned to the caller only; never written to disk."""
    if not src.get("resolved"):
        return ""
    try:
        text = read_page(src["url"], want_text=True)["text"]
    except Exception:
        return ""
    return text[:max_chars] if len(text) >= 400 else ""
