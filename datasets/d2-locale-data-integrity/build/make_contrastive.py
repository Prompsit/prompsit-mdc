#!/usr/bin/env python3
"""D2 contrastive pack: verified minimal-pair corruptions over the dev split.

For every dev record and every scoreable failure class, emit a minimal pair
(correct reference rendering vs one corrupted rendering) and VERIFY with the
real validator that the reference passes and the corruption is rejected
(verify-or-skip).
Output: data/contrastive.dev.jsonl. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402
from validators import score_item, value_from_semantic  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
DEV = PKG / "data" / "dev.jsonl"
OUT = PKG / "data" / "contrastive.dev.jsonl"
SLOT = " [%s]"


def main() -> None:
    rows = []
    by_class = Counter()
    skipped = 0
    for line in open(DEV, encoding="utf-8"):
        r = json.loads(line)
        ent = r["entities"][0]
        lang = r["target_lang"]
        track = r.get("track", "format")
        value = value_from_semantic(ent)
        base = r["reference"].rsplit(" [", 1)[0]  # carrier text without the slot
        # the reference must pass
        if not score_item(r, r["reference"])["pass"]:
            skipped += 1
            continue
        for cls in r["failure_opportunity_tags"]:
            c = o.corrupt(cls, ent["kind"], value, lang, track)
            if c is None:
                continue
            bad_sentence = base + SLOT % c
            res = score_item(r, bad_sentence)
            if res["pass"]:
                skipped += 1
                continue  # not actually rejected -> skip (do not ship)
            rows.append({
                "item_id": r["item_id"], "target_lang": lang,
                "target_locale": r["target_locale"], "kind": ent["kind"],
                "track": track,
                "failure_class": cls, "severity": res["severity"],
                "ref_render": ent["raw_target"], "corrupt_render": c,
                "validator_rejects_corrupt": True,
            })
            by_class[cls] += 1

    with open(OUT, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"contrastive_pairs": len(rows),
                      "by_class": dict(by_class), "skipped": skipped},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
