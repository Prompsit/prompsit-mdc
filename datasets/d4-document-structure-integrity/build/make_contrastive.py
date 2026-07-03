#!/usr/bin/env python3
"""D4 contrastive pack: verified minimal-pair structural corruptions (dev split).
ASCII-only."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import documents as D  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
DEV = PKG / "data" / "dev.jsonl"
OUT = PKG / "data" / "contrastive.dev.jsonl"


def main():
    rows, by_class, skipped = [], Counter(), 0
    for line in open(DEV, encoding="utf-8"):
        r = json.loads(line)
        if not D.score_item(r, r["reference"])["pass"]:
            skipped += 1
            continue
        for cls in r["failure_opportunity_tags"]:
            c = D.corrupt(cls, r["reference"])
            if c is None or D.score_item(r, c)["pass"]:
                skipped += 1
                continue
            rows.append({"item_id": r["item_id"], "target_lang": r["target_lang"],
                         "profile": r["profile"], "failure_class": cls,
                         "severity": D.SEVERITY[cls], "validator_rejects_corrupt": True})
            by_class[cls] += 1
    with open(OUT, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"contrastive_pairs": len(rows), "by_class": dict(by_class),
                      "skipped": skipped}, indent=2))


if __name__ == "__main__":
    main()
