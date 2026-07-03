#!/usr/bin/env python3
"""K2 - validator false-positive control for D4.

A correct document may be serialized many legal ways: extra whitespace/newlines
between tags, reordered tag attributes, an XML/HTML declaration, a trailing
newline, upper-case tag names. None change the structural tree, so none must flip
a correct output. Stop rule: > 5% flips. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import documents as D  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
FILES = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl",
         PKG / "private" / "hidden.ref.jsonl"]


def legal_variants(html):
    yield "trailing_nl", html + "\n"
    yield "reindent", html.replace("\n", "\n  ")
    yield "collapsed", html.replace("\n", "")
    yield "doctype", "<!DOCTYPE html>\n" + html
    yield "upper_tags", html.replace("<p>", "<P>").replace("</p>", "</P>")


def main():
    records = []
    for f in FILES:
        if f.exists():
            records += [json.loads(l) for l in open(f, encoding="utf-8")]
    base_pass = base_total = n_var = flips = 0
    by_gen, flip_by_gen, examples = Counter(), Counter(), []
    for r in records:
        base_total += 1
        if not D.score_item(r, r["reference"])["pass"]:
            continue
        base_pass += 1
        for name, variant in legal_variants(r["reference"]):
            if variant == r["reference"]:
                continue
            n_var += 1
            by_gen[name] += 1
            if not D.score_item(r, variant)["pass"]:
                flips += 1
                flip_by_gen[name] += 1
                if len(examples) < 6:
                    examples.append({"gen": name, "item": r["item_id"]})
    rate = 100.0 * flips / n_var if n_var else 0.0
    report = {"base_acceptance_pct": round(100.0 * base_pass / base_total, 2),
              "legal_variants_tested": n_var, "false_positive_flips": flips,
              "false_positive_rate_pct": round(rate, 3), "stop_threshold_pct": 5.0,
              "verdict": "PASS" if rate <= 5.0 else "FAIL",
              "by_generator": dict(by_gen), "flips_by_generator": dict(flip_by_gen),
              "examples": examples}
    Path(PKG / "k2_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("base_acceptance_pct", "legal_variants_tested",
                                             "false_positive_flips", "false_positive_rate_pct",
                                             "verdict", "by_generator")}, indent=2))


if __name__ == "__main__":
    main()
