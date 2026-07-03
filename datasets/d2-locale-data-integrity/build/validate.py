#!/usr/bin/env python3
"""D2 integrity check + manifest finalize.

Verifies schema, rectangularity (every source has all 9 locale records), split
partitioning (no item_id leaks across splits), gated-input reference-stripping,
per-class floors, and reference self-pass. Then merges the K1/K2 verdicts, the
contrastive count, and the Croissant pointer into manifest.json.

Usage: python validate.py   (run last, after k1/k2/croissant). ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402
from validators import score_entity, value_from_semantic  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
DATA = PKG / "data"
PRIV = PKG / "private"

REQUIRED = ["item_id", "source_lang", "source_locale", "target_lang",
            "target_locale", "source", "entities", "expected_invariants", "track",
            "entity_class_tags", "failure_opportunity_tags", "split", "provenance"]
REF_ENTITY_KEYS = {"raw_target", "accepted_variants", "unacceptable"}


def _load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


def main() -> int:
    errs = []
    refs = (_load(DATA / "dev.jsonl") + _load(DATA / "test.ref.jsonl")
            + _load(PRIV / "hidden.ref.jsonl"))
    inputs = _load(DATA / "test.input.jsonl") + _load(PRIV / "hidden.input.jsonl")

    # 1. schema
    for r in refs:
        miss = [k for k in REQUIRED + ["reference"] if k not in r]
        if miss:
            errs.append(f"{r.get('item_id')}: missing {miss}")
            break

    # 2. rectangular + 3. split partition
    langs_by_item = defaultdict(set)
    split_by_item = defaultdict(set)
    for r in refs:
        langs_by_item[r["item_id"]].add(r["target_lang"])
        split_by_item[r["item_id"]].add(r["split"])
    want = set(o.TARGET_LANGS)
    bad_rect = [i for i, ls in langs_by_item.items() if ls != want]
    if bad_rect:
        errs.append(f"non-rectangular items: {len(bad_rect)} (e.g. {bad_rect[:3]})")
    bad_split = [i for i, ss in split_by_item.items() if len(ss) != 1]
    if bad_split:
        errs.append(f"items spanning splits: {len(bad_split)}")

    # 4. gated inputs carry no references
    for r in inputs:
        if "reference" in r:
            errs.append(f"{r['item_id']}: reference leaked into input"); break
        leak = REF_ENTITY_KEYS & set(r["entities"][0])
        if leak:
            errs.append(f"{r['item_id']}: reference keys {leak} leaked into input"); break

    # 5. per-class floor on RECORDS in the K1 scored set (dev+test), since K1
    # keys per-class pass lists on failure_opportunity_tags over those splits.
    # (A min-over-locales metric would wrongly fail locale-conditional classes
    # like wrong_unit_format, which only the symbol-localizing locales carry.)
    man = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    floor = man["per_class_floor"]
    seen_item = set()
    k1_split = {"dev", "test"}
    per_class = Counter()
    for r in refs:
        seen_item.add(r["item_id"])
        if r["split"] in k1_split:
            for c in r["failure_opportunity_tags"]:
                per_class[c] += 1
    headline = man["format_track"]["classes"]  # only the headline classes gate the build
    below = {c: per_class.get(c, 0) for c in headline if per_class.get(c, 0) < floor}
    if below:
        errs.append(f"headline classes below K1 record floor {floor}: {below}")

    # 6. reference self-pass (full, track-aware)
    fail = 0
    for r in refs:
        ent = r["entities"][0]
        if not score_entity(ent, r["target_lang"], ent["raw_target"],
                            r.get("track", "format"))["pass"]:
            fail += 1
    if fail:
        errs.append(f"reference rendering self-pass failures: {fail}")

    # 7. Currency invariant: the input surface (raw_source) must be the
    # faithful en_US rendering of semantic.amount, and the amount must carry no
    # precision beyond the currency's CLDR fraction digits (so it is recoverable
    # from the surface for ANY currency, not only 0-decimal JPY by rounding luck).
    cur_bad = 0
    for r in refs:
        ent = r["entities"][0]
        if ent["kind"] != "currency":
            continue
        amt, code = ent["semantic"]["amount"], ent["semantic"]["code"]
        if o.quantize_currency(amt, code) != amt:
            cur_bad += 1
        elif o.norm(ent["raw_source"]) != o.norm(o.render("currency", (amt, code), o.SOURCE_LANG)):
            cur_bad += 1
    if cur_bad:
        errs.append(f"currency surface/semantic invariant violations: {cur_bad}")

    # report
    if errs:
        print("VALIDATE: FAIL")
        for e in errs:
            print("  -", e)
        return 1
    print("VALIDATE: PASS")
    print(json.dumps({"ref_records": len(refs), "sources": len(seen_item),
                      "input_records": len(inputs),
                      "per_class_records_k1": dict(per_class),
                      "ref_self_pass": "%d/%d" % (len(refs) - fail, len(refs))},
                     indent=2))

    # finalize manifest with downstream verdicts
    def rd(name):
        p = PKG / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    k1, k2 = rd("k1_report.json"), rd("k2_report.json")
    contr = _load(DATA / "contrastive.dev.jsonl")
    man["k1_verdict"] = k1["k1_verdict"] if k1 else "not_run"
    man["k1"] = {"engines_overall_pass_pct": k1["engines_overall_pass_pct"]} if k1 else None
    man["k2_verdict"] = k2["verdict"] if k2 else "not_run"
    man["k2_false_positive_rate_pct"] = k2["false_positive_rate_pct"] if k2 else None
    man["contrastive_pairs"] = len(contr)
    man["croissant"] = "croissant.json" if (PKG / "croissant.json").exists() else None
    man["validation"] = "PASS"
    (PKG / "manifest.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    print("manifest finalized (k1/k2/contrastive/croissant merged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
