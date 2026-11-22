"""The private full-text archive.

This repository is public and never holds article text. The complete text of every report linked
to a published case is kept in a separate private repository: one plain-text file per report, in a
folder named for the case, plus `index.csv`, which ties each file to its case ID and report link.

The daily job here does not run this file. The private repository runs it, on its own schedule:
it downloads this public repository, reads `store/cases.json`, and saves any text it does not hold
yet into itself. So no key to the private repository is kept here, and no article text passes
through this repository's job or its public logs.

    SDI_FULLTEXT_DIR=/path/to/private/checkout python -m pipeline.archive

Without that variable nothing is fetched or saved, and a folder inside this repository is refused.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import enrich, store as st
from .common import ROOT, load_config, log, setup_logging

ENV = "SDI_FULLTEXT_DIR"
FIELDS = ["text_id", "case_id", "url", "publisher", "title", "published", "status", "copy_from", "chars",
          "sha256", "retrieved", "attempts", "file"]
SAVED, UNAVAILABLE = "saved", "unavailable"


def archive_dir() -> Path | None:
    """The private checkout to write to, or None when no archive is connected."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    path = Path(raw).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError("The full-text archive must be outside the public repository.")
    return path if path.is_dir() else None


def text_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def load_index(root: Path) -> dict[str, dict]:
    path = root / "index.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["text_id"]: r for r in csv.DictReader(fh)}


def save_index(root: Path, index: dict[str, dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for row in sorted(index.values(), key=lambda r: (r["case_id"], r["published"], r["text_id"])):
        w.writerow(row)
    data = buf.getvalue().encode("utf-8")
    path = root / "index.csv"
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def read_report(src: dict, min_chars: int) -> tuple[str, str]:
    """(text, where the copy came from). The publisher's own page first; failing that, the Internet
    Archive's saved copy of the same link."""
    text = enrich.complete_text(src, min_chars)
    if text:
        return text, "publisher"
    text, stamp = enrich.wayback_text(src, min_chars)
    return (text, f"internet_archive:{stamp}") if text else ("", "")


def _document(src: dict, tid: str, retrieved: str, text: str, copy_from: str) -> str:
    head = [f"Title: {src['title']}", f"Publisher: {src['publisher']}", f"Published: {src['published'][:10]}",
            f"URL: {src['url']}", f"Retrieved: {retrieved}", f"Copy from: {copy_from}", f"Text ID: {tid}"]
    return "\n".join(head) + "\n\n" + text.strip() + "\n"


def update(store: dict, cfg: dict, root: Path | None = None, fetch=None, today: str | None = None) -> dict | None:
    """Save the text of reports not yet archived. Returns counts, or None when no archive is connected."""
    root = archive_dir() if root is None else root
    if root is None:
        return None
    opts = cfg.get("archive") or {}
    limit, tries = int(opts.get("max_per_run", 300)), int(opts.get("max_attempts", 3))
    min_chars = int(opts.get("min_chars", 400))
    fetch = fetch or (lambda src: read_report(src, min_chars))
    now = st.now_iso()
    today = today or now[:10]
    index = load_index(root)
    # One file per report link. A link attached to two cases is filed under the lower case ID.
    wanted: dict[str, tuple[str, dict]] = {}
    for c in sorted((c for c in store["cases"] if c["status"] == "published" and c.get("case_id")),
                    key=lambda c: c["case_id"]):
        for s in c["sources"]:
            wanted.setdefault(text_id(s["url"]), (c["case_id"], s))
    todo = []
    for tid, (case_id, src) in wanted.items():
        row = index.get(tid)
        if row is None:
            row = index[tid] = {"text_id": tid, "status": "", "copy_from": "", "chars": "", "sha256": "",
                                "retrieved": "", "attempts": "0", "file": ""}
        if row["status"] == SAVED and row.get("case_id") != case_id:
            # The report now belongs to another case: move its file to that case's folder.
            old, new = root / row["file"], root / "texts" / case_id / f"{tid}.txt"
            if old.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
                row["file"] = str(new.relative_to(root))
        row.update(case_id=case_id, url=src["url"], publisher=src["publisher"], title=src["title"],
                   published=src["published"][:10])
        if row["status"] != SAVED and int(row["attempts"] or 0) < tries and row["retrieved"][:10] != today:
            todo.append((case_id, src, row))
    todo = todo[:limit]
    with ThreadPoolExecutor(max_workers=6) as pool:
        texts = list(pool.map(lambda job: fetch(job[1]), todo))
    saved = 0
    for (case_id, src, row), (text, copy_from) in zip(todo, texts):
        row["attempts"], row["retrieved"] = str(int(row["attempts"] or 0) + 1), now
        if not text:
            row["status"] = UNAVAILABLE
            continue
        path = root / "texts" / case_id / f"{row['text_id']}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_document(src, row["text_id"], now, text, copy_from), encoding="utf-8")
        row.update(status=SAVED, copy_from=copy_from, chars=str(len(text.strip())), file=str(path.relative_to(root)),
                   sha256=hashlib.sha256(text.strip().encode("utf-8")).hexdigest())
        saved += 1
    save_index(root, index)
    held = sum(1 for r in index.values() if r["status"] == SAVED)
    tally = {"tried": len(todo), "saved": saved, "held": held, "reports": len(wanted)}
    log.info("Private archive: %d texts saved this run (%d tried); %d of %d reports held",
             saved, len(todo), held, len(wanted))
    return tally


def main() -> None:
    setup_logging()
    root = archive_dir()
    if root is None:
        raise SystemExit(f"Set {ENV} to the folder of the private archive.")
    tally = update(st.load(), load_config(), root=root)
    print(f"Archive update: {tally['saved']} report texts added; {tally['held']} of {tally['reports']} reports held")


if __name__ == "__main__":
    main()
