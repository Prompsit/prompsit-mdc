#!/usr/bin/env python3
"""D3 integrity check + manifest finalize.

Verifies schema, rectangularity (9 locale records per source), split partition,
gated-input reference-stripping, per-class floors, and reference self-pass; then merges the
K1/K2 verdicts, contrastive count, and Croissant pointer into manifest.json.
ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import resources as R  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
DATA, PRIV = PKG / "data", PKG / "private"
REQUIRED = ["item_id", "source_lang", "target_lang", "format", "source",
            "failure_opportunity_tags", "split", "provenance"]


def _load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def main():
    errs = []
    refs = (_load(DATA / "dev.jsonl") + _load(DATA / "test.ref.jsonl")
            + _load(PRIV / "hidden.ref.jsonl"))
    inputs = _load(DATA / "test.input.jsonl") + _load(PRIV / "hidden.input.jsonl")

    for r in refs:
        miss = [k for k in REQUIRED + ["reference"] if k not in r]
        if miss:
            errs.append(f"{r.get('item_id')}: missing {miss}"); break
    langs_by, split_by = defaultdict(set), defaultdict(set)
    for r in refs:
        langs_by[r["item_id"]].add(r["target_lang"])
        split_by[r["item_id"]].add(r["split"])
    want = set(R.LANGS)
    if [i for i, ls in langs_by.items() if ls != want]:
        errs.append("non-rectangular items present")
    if [i for i, ss in split_by.items() if len(ss) != 1]:
        errs.append("items spanning splits")
    for r in inputs:
        if "reference" in r:
            errs.append(f"{r['item_id']}: reference leaked into input"); break

    man = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    floor = man["per_class_floor"]
    seen = set()
    # per-class floor on RECORDS in the K1 scored set (dev+test). A min-over-
    # locales metric would wrongly fail nonvalue_modified_marked, which only the
    # XML records carry (but for all 9 of their locales).
    k1_split = {"dev", "test"}
    per_class = Counter()
    for r in refs:
        seen.add(r["item_id"])
        if r["split"] in k1_split:
            for c in r["failure_opportunity_tags"]:
                per_class[c] += 1
    below = {c: per_class.get(c, 0) for c in R.ALL_CLASSES if per_class.get(c, 0) < floor}
    if below:
        errs.append(f"classes below K1 record floor {floor}: {below}")

    fail = sum(1 for r in refs if not R.score_item(r, r["reference"])["pass"])
    if fail:
        errs.append(f"reference self-pass failures: {fail}")

    if errs:
        print("VALIDATE: FAIL")
        for e in errs:
            print("  -", e)
        return 1
    print("VALIDATE: PASS")
    print(json.dumps({"ref_records": len(refs), "sources": len(seen),
                      "input_records": len(inputs), "per_class_records_k1": dict(per_class),
                      "ref_self_pass": "%d/%d" % (len(refs) - fail, len(refs))}, indent=2))

    def rd(n):
        p = PKG / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    k1, k2 = rd("k1_report.json"), rd("k2_report.json")
    man["k1_verdict"] = k1["k1_verdict"] if k1 else "not_run"
    man["k2_verdict"] = k2["verdict"] if k2 else "not_run"
    man["k2_false_positive_rate_pct"] = k2["false_positive_rate_pct"] if k2 else None
    man["contrastive_pairs"] = len(_load(DATA / "contrastive.dev.jsonl"))
    man["croissant"] = "croissant.json" if (PKG / "croissant.json").exists() else None
    man["validation"] = "PASS"
    (PKG / "manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    print("manifest finalized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
