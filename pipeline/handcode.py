"""Code cases outside the scheduled job, with exactly the same checks.

Used when answers are drafted somewhere other than the configured API (for example by a person,
or by a different model in a supervised session). Article text is written only to a scratch
folder you name, never to the repository.

    python -m pipeline.handcode list
    python -m pipeline.handcode merge k3 k12            join pending case k12 into k3
    python -m pipeline.handcode join SDI-00003 SDI-00054 --reason "Both report ..."
                                                        join published cases that are one event: the lowest
                                                        ID survives, the others are retired and listed in
                                                        data/retired_ids.csv with the reason given
    python -m pipeline.handcode prepare /tmp/scratch [k3 k7 ...]
    python -m pipeline.handcode apply /tmp/scratch answers.json "Name of the coder"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import coder, export, store as st
from .common import load_config, setup_logging
from .run import absorb, join_published, reports_for, settle


def _by_key(store, key):
    return next(c for c in store["cases"] if c["key"] == key)


def main(argv: list[str]) -> None:
    setup_logging()
    cfg, store = load_config(), st.load()
    cmd = argv[0]
    if cmd == "list":
        for c in sorted((c for c in store["cases"] if c.get("needs_coding")), key=st.first_reported):
            print(f"{c['key']:>5} {c['status']:9} {st.first_reported(c)} n={len(c['sources']):<2} {c['headline'][:120]}")
    elif cmd == "merge":
        target = _by_key(store, argv[1])
        for k in argv[2:]:
            absorb(target, _by_key(store, k), store, cfg)
        st.save(store)
    elif cmd == "join":
        if "--reason" not in argv or argv.index("--reason") + 1 >= len(argv):
            raise SystemExit('Give the evidence: join SDI-00003 SDI-00054 --reason "Both report ..."')
        at = argv.index("--reason")
        target = join_published(store, cfg, argv[1:at], argv[at + 1])
        st.save(store)
        print(f"Joined into {target['case_id']} ({len(target['sources'])} reports); it will be coded again "
              f"at the next refresh.", export.export_all(store, cfg))
    elif cmd == "prepare":
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        keys = argv[2:] or [c["key"] for c in store["cases"] if c.get("needs_coding")]
        for k in keys:
            case = _by_key(store, k)
            reports = reports_for(case, cfg)
            coder.build_messages(case, reports, [], cfg)   # fills in the exact text each report offers
            (out / f"{k}.json").write_text(json.dumps(reports, ensure_ascii=False), encoding="utf-8")
            print(f"{k}: {len(reports)} reports, {sum(len(r['given']) for r in reports)} characters")
    elif cmd == "apply":
        scratch, answers, name = Path(argv[1]), json.loads(Path(argv[2]).read_text(encoding="utf-8")), argv[3]
        tally = {"published": 0, "recoded": 0, "excluded": 0, "merged": 0}
        for k, raw in answers.items():
            case = _by_key(store, k)
            reports = json.loads((scratch / f"{k}.json").read_text(encoding="utf-8"))
            earlier = [{"ref": c["case_id"], "case": c} for c in store["cases"]
                       if c["status"] == "published" and c is not case]
            decision = settle(store, case, raw, reports, earlier, cfg, name, tally)
            removed = (case.get("coding") or {}).get("unsupported_values_removed")
            print(f"{k}: {decision}" + (f" as {case['case_id']}, {removed} unsupported removed" if decision == "publish" else ""))
        st.save(store)
        print(tally, export.export_all(store, cfg))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
