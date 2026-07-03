#!/usr/bin/env python3
"""K2 - validator false-positive control for D5.

A correct output remains correct under edits that do not change the prescribed
term: whitespace padding around the term, a trailing newline, and rewording of the
non-scored carrier prose. None must flip. v1.0 scores the exact prescribed term
surface form. Stop rule:
> 5% flips. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lingres as L  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
FILES = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl",
         PKG / "private" / "hidden.ref.jsonl"]


def legal_variants(r):
    ref = r["reference"]
    base = ref.rsplit(" [", 1)[0]
    ref_term = r["ref_term"]
    rep = r["repeated"]
    inner = (ref_term + " | " + ref_term) if rep else ref_term
    yield "pad", base + " [ " + inner + " ]"
    yield "trailing_nl", ref + "\n"
    yield "carrier_reword", "Note: " + base + " " + L.make_slot(ref_term, rep)


def main():
    records = []
    for f in FILES:
        if f.exists():
            records += [json.loads(l) for l in open(f, encoding="utf-8")]
    base_pass = base_total = n_var = flips = 0
    by_gen, flip_by_gen, examples = Counter(), Counter(), []
    for r in records:
        base_total += 1
        if not L.score_item(r, r["reference"])["pass"]:
            continue
        base_pass += 1
        for name, variant in legal_variants(r):
            if variant == r["reference"]:
                continue
            n_var += 1
            by_gen[name] += 1
            if not L.score_item(r, variant)["pass"]:
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
