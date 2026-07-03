#!/usr/bin/env python3
"""K2 - validator false-positive control for D3.

A correct resource may be serialized many legal ways: different indentation, key
order, added comments/blank lines, trailing newline. None of these change the
parsed skeleton or values, so none must flip a correct output. Stop rule: > 5%
flips -> fix. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import resources as R  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
FILES = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl",
         PKG / "private" / "hidden.ref.jsonl"]


def legal_variants(r):
    """Yield (name, text) legal re-serializations of the reference."""
    fmt = r["format"]
    ok, kv, meta = R.parse(fmt, r["reference"])
    if not ok:
        return
    items = list(kv.items())
    rev = list(reversed(items))
    if fmt in ("json", "arb"):
        obj = {}
        if fmt == "arb":
            obj["@@locale"] = meta.get("@@locale")
        for k, v in rev:
            obj[k] = v
        yield "reorder", json.dumps(obj, ensure_ascii=False, indent=2)
        yield "reindent", json.dumps(obj, ensure_ascii=False, indent=4)
        yield "trailing_nl", r["reference"] + "\n"
    elif fmt == "properties":
        yield "comment", "# generated\n" + r["reference"]
        yield "blank_lines", r["reference"].replace("\n", "\n\n")
        yield "reorder", "".join("%s=%s\n" % (k, v) for k, v in rev)
    elif fmt == "xml":
        body = "".join('    <string name="%s">%s</string>\n' % (k, R._xml_esc(v))
                       for k, v in rev)  # reordered + deeper indent
        yield "reorder_indent", ('<?xml version="1.0" encoding="utf-8"?>\n'
                                 '<resources>\n%s</resources>\n' % body)
        yield "trailing_nl", r["reference"] + "\n"


def main():
    records = []
    for f in FILES:
        if f.exists():
            records += [json.loads(l) for l in open(f, encoding="utf-8")]
    base_pass = base_total = 0
    n_var = flips = 0
    by_gen, flip_by_gen = Counter(), Counter()
    examples = []
    for r in records:
        base_total += 1
        if not R.score_item(r, r["reference"])["pass"]:
            continue
        base_pass += 1
        for name, variant in legal_variants(r):
            n_var += 1
            by_gen[name] += 1
            if not R.score_item(r, variant)["pass"]:
                flips += 1
                flip_by_gen[name] += 1
                if len(examples) < 6:
                    examples.append({"format": r["format"], "gen": name,
                                     "item": r["item_id"]})
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
