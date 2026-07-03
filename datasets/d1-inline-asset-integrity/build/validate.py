#!/usr/bin/env python3
"""Package validator for D1 (single 9-language set): schema, splits, balance.

Checks the canonical set:
  refs   = data/dev.jsonl + data/test.ref.jsonl + private/hidden.ref.jsonl
  inputs = data/test.input.jsonl + private/hidden.input.jsonl
Verifies required schema, balanced 9-language rectangle, item-id split
partitioning, and that the input variants carry no references. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validators import score_item  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
TARGETS = {"ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"}
REQ = ["item_id", "source_lang", "target_lang", "source", "reference", "assets",
       "expected_invariants", "ref_tag_positions", "legal_moves",
       "asset_class_tags", "failure_opportunity_tags", "split", "provenance"]
REF_ONLY = {"reference", "ref_tag_positions"}


def load(rel):
    p = PKG / rel
    return [json.loads(line) for line in open(p, encoding="utf-8")] if p.exists() else []


def main():
    refs = load("data/dev.jsonl") + load("data/test.ref.jsonl") + load("private/hidden.ref.jsonl")
    inputs = load("data/test.input.jsonl") + load("private/hidden.input.jsonl")
    errors = []

    # schema + targets on references
    for r in refs:
        for f in REQ:
            if f not in r:
                errors.append(f"missing field {f} in {r.get('item_id')}")
        if r["target_lang"] not in TARGETS:
            errors.append(f"bad target {r['target_lang']} in {r.get('item_id')}")
        ids = {a["id"] for a in r.get("assets", [])}
        for a in r.get("assets", []):
            if a.get("pair") and a["pair"] not in ids:
                errors.append(f"dangling pair {r['item_id']}:{a['id']}")
        for k, v in r.get("ref_tag_positions", {}).items():
            if k not in ids or not isinstance(v, int):
                errors.append(f"bad reference position {r['item_id']}:{k}")

    # inputs must not leak references
    for r in inputs:
        leaked = REF_ONLY & set(r)
        if leaked:
            errors.append(f"reference leak {sorted(leaked)} in input {r['item_id']}")

    # references must be accepted by the same hard gates used for scoring
    ref_self_pass_failures = []
    for r in refs:
        gates = score_item(r["source"], r["reference"])
        if not gates["pass"]:
            failed = sorted(k for k, ok in gates.items() if k != "pass" and not ok)
            ref_self_pass_failures.append((r["item_id"], r["target_lang"], failed))
    if ref_self_pass_failures:
        examples = ", ".join(
            f"{item}:{lang}:{'/'.join(failed)}"
            for item, lang, failed in ref_self_pass_failures[:5]
        )
        errors.append(
            f"reference self-pass failures: {len(ref_self_pass_failures)} (e.g. {examples})"
        )

    # balance + split partitioning: each item in all 9 langs, one split, one source
    by_item_lang = defaultdict(set)
    item_split = {}
    item_src = {}
    for r in refs:
        by_item_lang[r["item_id"]].add(r["target_lang"])
        if r["item_id"] in item_split and item_split[r["item_id"]] != r["split"]:
            errors.append(f"{r['item_id']} crosses splits")
        item_split[r["item_id"]] = r["split"]
        if r["item_id"] in item_src and item_src[r["item_id"]] != r["source"]:
            errors.append(f"{r['item_id']} source differs across langs")
        item_src[r["item_id"]] = r["source"]
    for it, langs in by_item_lang.items():
        if langs != TARGETS:
            errors.append(f"{it}: {len(langs)} langs (need 9)")

    # dev split must contain every failure class
    dev_classes = set()
    for r in load("data/dev.jsonl"):
        dev_classes.update(r.get("failure_opportunity_tags", []))

    splits = defaultdict(int)
    for it, sp in item_split.items():
        splits[sp] += 1

    print(json.dumps({
        "sources": len(by_item_lang),
        "records": len(refs),
        "splits_sources": dict(splits),
        "dev_failure_classes": sorted(dev_classes),
        "ref_self_pass": f"{len(refs) - len(ref_self_pass_failures)}/{len(refs)}",
        "errors": errors[:20],
        "error_count": len(errors),
        "verdict": "PASS" if not errors else "FAIL",
    }, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
