#!/usr/bin/env python3
"""Build the D1 derived files from the committed references (single 9-language set).

The dataset's raw material is the human-translated references, committed as:
  data/dev.jsonl              (dev split, full records with references)
  data/test.ref.jsonl         (test split, full records; held by Prompsit)
  private/hidden.ref.jsonl    (hidden split, full records; never published)

This builder regenerates the reference-stripped input variants (what a system
sees) and verifies the set is a balanced 9-language rectangle with no answer
leakage:
  data/test.input.jsonl       (test inputs)
  private/hidden.input.jsonl  (hidden inputs)

Run after editing references, then: make_contrastive -> k1 -> k2 ->
build_croissant -> make_release -> validate. Deterministic; ASCII-only.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from validators import score_item

PKG = Path(__file__).resolve().parent.parent
TARGETS = {"ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"}
STRIP = {"ref_tag_positions", "legal_moves", "reference"}


def load(rel):
    return [json.loads(line) for line in open(PKG / rel, encoding="utf-8")]


def dump(rel, recs):
    with open(PKG / rel, "w", encoding="utf-8", newline="\n") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def strip(r):
    return {k: v for k, v in r.items() if k not in STRIP}


def check_balance(name, recs, errors):
    by_item = defaultdict(set)
    src_of = {}
    for r in recs:
        if r["target_lang"] not in TARGETS:
            errors.append(f"{name}: bad target {r['target_lang']} in {r['item_id']}")
        by_item[r["item_id"]].add(r["target_lang"])
        src_of.setdefault(r["item_id"], r["source"])
        if r["source"] != src_of[r["item_id"]]:
            errors.append(f"{name}: source mismatch across langs for {r['item_id']}")
    for it, langs in by_item.items():
        if langs != TARGETS:
            errors.append(f"{name}: {it} has {len(langs)} langs (need 9)")
    return len(by_item)


def main():
    dev = load("data/dev.jsonl")
    testg = load("data/test.ref.jsonl")
    hidden = load("private/hidden.ref.jsonl")

    # regenerate reference-stripped inputs
    dump("data/test.input.jsonl", [strip(r) for r in testg])
    dump("private/hidden.input.jsonl", [strip(r) for r in hidden])

    errors = []
    n_dev = check_balance("dev", dev, errors)
    n_test = check_balance("test", testg, errors)
    n_hidden = check_balance("hidden", hidden, errors)

    # References must be a clean positive set for the D1 hard gates. K1/K2 can
    # filter non-clean references, but the published dataset must not carry them.
    ref_fail = 0
    for r in dev + testg + hidden:
        gates = score_item(r["source"], r["reference"])
        if not gates["pass"]:
            ref_fail += 1
            if len(errors) < 20:
                failed = sorted(k for k, ok in gates.items() if k != "pass" and not ok)
                errors.append(f"reference self-pass failed {r['item_id']}:{r['target_lang']} {failed}")

    # no item_id leaks across splits
    seen = {}
    for name, recs in (("dev", dev), ("test", testg), ("hidden", hidden)):
        for r in recs:
            prev = seen.setdefault(r["item_id"], name)
            if prev != name:
                errors.append(f"item {r['item_id']} crosses splits ({prev}/{name})")

    summary = {
        "sources": n_dev + n_test + n_hidden,
        "records": len(dev) + len(testg) + len(hidden),
        "splits_sources": {"dev": n_dev, "test": n_test, "hidden": n_hidden},
        "ref_self_pass_failures": ref_fail,
        "errors": errors[:20],
        "error_count": len(errors),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
