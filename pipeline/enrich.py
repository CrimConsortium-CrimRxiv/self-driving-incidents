"""Find each report's own link, its publisher-written summary and, at coding time, its text.

Nothing here is generated. Summaries shown on the site are the publisher's own words (the page's
summary line, or Bing News' snippet of the same article). Article text is read to code the case
and to check quotations. It is never saved in this repository; `archive.py` keeps a copy in a
separate private repository when one is connected.
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
_HEADINGS = {"h1", "h2", "h3", "h4"}


class _Page(HTMLParser):
    """Collects <meta> summaries and the text of paragraphs outside navigation and page furniture."""

    def __init__(self, complete: bool = False):
        super().__init__(convert_charrefs=True)
        self.complete = complete      # keep short paragraphs and headings too (private archive only)
        self.meta: dict[str, str] = {}
        self.paras: list[str] = []
        self.solid = 0                # characters in full-length paragraphs: how much real article there is
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
        elif self._block(tag) and not self._skip:
            self._in_p, self._buf = True, []

    def _block(self, tag) -> bool:
        return tag == "p" or (self.complete and tag in _HEADINGS)

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif self._block(tag) and self._in_p:
            self._in_p = False
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            body = len(text) >= 60 and not JUNK.search(text[:160])
            if body and text not in self.paras:
                self.solid += len(text)
            if self.complete:
                if text and text not in self.paras:   # page furniture is often repeated; keep it once
                    self.paras.append(text)
            elif body:
                self.paras.append(text)

    def handle_data(self, data):
        if self._in_p and not self._skip:
            self._buf.append(data)


_LD = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)


def article_body(page: str) -> str:
    """The article text some publishers place in the page's structured data ("articleBody")."""
    best = ""

    def walk(node):
        nonlocal best
        if isinstance(node, dict):
            body = node.get("articleBody")
            if isinstance(body, str) and len(body) > len(best):
                best = body
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for block in _LD.findall(page):
        try:
            walk(json.loads(block.strip(), strict=False))
        except Exception:
            continue
    best = htmllib.unescape(re.sub(r"<[^>]+>", " ", best))
    return "\n\n".join(t for t in (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in best.split("\n")) if t)


def read_page(url: str, want_text: bool = False, limit: int = 1_500_000, complete: bool = False) -> dict:
    """Return {'summary': publisher's summary line or None, 'text': article paragraphs or ''}.

    `complete` is for the private archive: every paragraph and heading, however short, separated by
    blank lines, or the publisher's own structured copy of the article when that is longer."""
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
    p = _Page(complete=complete)
    page = raw.decode(enc, errors="replace")
    try:
        p.feed(page)
    except Exception:
        pass
    m = p.meta
    out["summary"] = m.get("og:description") or m.get("description") or m.get("twitter:description")
    if want_text and complete:
        body = article_body(page)
        out["text"] = max("\n\n".join(p.paras), body, key=len)
        out["solid"] = max(p.solid, len(body))
    elif want_text:
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


_TEASER = re.compile(r"\s*(?:\.{3}|\u2026)?\s*(?:read more|continue reading|read the full (?:story|article)|see more)"
                     r"\s*(?:\.{3}|\u2026|\u00bb|>)*\s*$", re.I)


def strip_teaser(text: str) -> str:
    """Remove a trailing "Read more..." link label; the summary then ends with an ellipsis."""
    cut = _TEASER.sub("", text or "")
    return cut if cut == (text or "") else cut.rstrip(" .\u2026") + "\u2026"


def clean_summary(text: str | None, headline: str, max_chars: int) -> str | None:
    """Tidy a publisher's summary line; return None when it is boilerplate or just repeats the headline."""
    t = strip_teaser(clean_text(text))
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


def complete_text(src: dict, min_chars: int = 400) -> str:
    """The whole text of a report, as the publisher serves it to a reader who is not signed in.
    For the private archive only; never written inside this repository."""
    if not src.get("resolved"):
        return ""
    try:
        page = read_page(src["url"], want_text=True, complete=True)
    except Exception:
        return ""
    # Same test the coder uses for "article text was read": enough full-length paragraphs.
    # A video page or a block notice has only headings and teasers and is not an article.
    return page["text"] if page.get("solid", 0) >= min_chars else ""


def wayback_text(src: dict, min_chars: int = 400) -> tuple[str, str]:
    """Fallback for the private archive when the publisher's page cannot be read: the Internet
    Archive's saved copy of the same link, if it has one. Returns (text, snapshot date) or ("", "")."""
    if not src.get("resolved"):
        return "", ""
    try:
        found = requests.get("https://archive.org/wayback/available", params={"url": src["url"]},
                             headers=UA, timeout=15).json()
        snap = (found.get("archived_snapshots") or {}).get("closest") or {}
        stamp = snap.get("timestamp") or ""
        if not (snap.get("available") and stamp):
            return "", ""
        # "id_" asks for the page as it was saved, without the Internet Archive's own banner.
        page = read_page(f"https://web.archive.org/web/{stamp}id_/{src['url']}", want_text=True, complete=True)
    except Exception:
        return "", ""
    return (page["text"], stamp) if page.get("solid", 0) >= min_chars else ("", "")


def article_text(src: dict, max_chars: int = 9000) -> str:
    """Article text for coding. Returned to the caller only; never written to disk."""
    if not src.get("resolved"):
        return ""
    try:
        text = read_page(src["url"], want_text=True)["text"]
    except Exception:
        return ""
    return text[:max_chars] if len(text) >= 400 else ""
