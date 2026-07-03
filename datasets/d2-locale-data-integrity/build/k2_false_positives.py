#!/usr/bin/env python3
"""K2 - false-positive check (release requirement).

False positive = a LEGAL locale variant flips a correct output from pass to fail.
We measure flips: among reference renderings the validator accepts (base pass), how
often does a locale-LEGAL edit make the validator wrongly reject it. The legal
edits are the D2 false-positive traps named in the plan:

  - grouping whitespace swap: regular space / NBSP / NNBSP / thin space are
    interchangeable for digit grouping (the headline D2 risk);
  - alternate date length (short / long) where CLDR offers one;
  - currency ISO-code form instead of the symbol;
  - unit long form instead of the short symbol.

Stop rule: > 5% flips -> fix or drop the offending class. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402
from validators import score_entity, value_from_semantic  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
FILES = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl",
         PKG / "private" / "hidden.ref.jsonl"]

_SPACES = [chr(0x20), chr(0xA0), chr(0x202F), chr(0x2009)]
_WS_RE = o._WS_RE


def gen_ws_swaps(ref: str):
    """Every grouping-whitespace re-rendering of the reference (legal)."""
    if not _WS_RE.search(ref):
        return
    for sp in _SPACES:
        v = _WS_RE.sub(sp, ref)
        if v != ref:
            yield "ws_%04x" % ord(sp), v


def gen_accepted_alternates(kind, value, lang, ref: str, track: str = "format"):
    """Accepted variants beyond the canonical reference (date length, currency
    code, unit long form)."""
    for v in o.accepted_variants(kind, value, lang, track):
        if o.norm(v) != o.norm(ref):
            yield "alt", v


def main():
    records = []
    for f in FILES:
        if f.exists():
            records += [json.loads(l) for l in open(f, encoding="utf-8")]

    base_pass = base_total = 0
    n_variants = flips = 0
    by_gen = Counter(); flip_by_gen = Counter(); flip_by_kind = Counter()
    examples = []

    for r in records:
        ent = r["entities"][0]
        lang = r["target_lang"]
        track = r.get("track", "format")
        value = value_from_semantic(ent)
        ref = ent["raw_target"]
        base_total += 1
        if not score_entity(ent, lang, ref, track)["pass"]:
            continue  # not a legal positive; excluded from K2 denominator
        base_pass += 1
        variants = list(gen_ws_swaps(ref)) + \
            list(gen_accepted_alternates(ent["kind"], value, lang, ref, track))
        for name, variant in variants:
            n_variants += 1
            by_gen[name.split("_")[0]] += 1
            if not score_entity(ent, lang, variant, track)["pass"]:
                flips += 1
                flip_by_gen[name.split("_")[0]] += 1
                flip_by_kind[ent["kind"]] += 1
                if len(examples) < 8:
                    examples.append({"kind": ent["kind"], "lang": lang,
                                     "gen": name, "ref": ref, "variant": variant})

    rate = 100.0 * flips / n_variants if n_variants else 0.0
    report = {
        "base_acceptance_pct": round(100.0 * base_pass / base_total, 2),
        "base_pass": base_pass, "base_total": base_total,
        "legal_variants_tested": n_variants,
        "false_positive_flips": flips,
        "false_positive_rate_pct": round(rate, 3),
        "stop_threshold_pct": 5.0,
        "verdict": "PASS" if rate <= 5.0 else "FAIL",
        "by_generator": dict(by_gen),
        "flips_by_generator": dict(flip_by_gen),
        "flips_by_kind": dict(flip_by_kind),
        "examples": examples,
    }
    Path(PKG / "k2_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("base_acceptance_pct", "legal_variants_tested",
                       "false_positive_flips", "false_positive_rate_pct",
                       "verdict", "by_generator")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
