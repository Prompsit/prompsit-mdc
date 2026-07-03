"""K2 — false-positive check (release requirement).

False positive = a LEGAL edit flips a correct output from pass to fail. We
therefore measure flips: among references the validator already accepts
(base pass), how often does a legal-variation edit (reordered positional
placeholders, locale typography, guillemets, reordered ICU branches) make the
validator wrongly reject it. Stop rule: > 5 % flips -> fix or drop the class.

Items whose reference does NOT pass against the source (a separate
source<->target asset-mismatch data issue, reported as base_acceptance) are
excluded from the K2 denominator — they are not legal positives to begin with.
"""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from legal_moves import GENERATORS, legal_moves
from validators import score_item
from assets import extract_assets

PKG = Path(__file__).parent.parent
FILES = [PKG/"data"/"dev.jsonl", PKG/"data"/"test.ref.jsonl", PKG/"private"/"hidden.ref.jsonl"]


def main():
    records = []
    for f in FILES:
        if f.exists():
            records += [json.loads(l) for l in open(f, encoding="utf-8")]

    base_pass = base_total = 0
    n_variants = flips = 0
    by_gen = Counter(); flip_by_gen = Counter(); flip_by_gate = Counter()
    examples = []

    for r in records:
        src, ref = r["source"], r["reference"]
        base_total += 1
        base_ok = score_item(src, ref)["pass"]
        if base_ok:
            base_pass += 1
        else:
            continue  # not a legal positive; excluded from K2 denominator
        for name, gen in GENERATORS.items():
            variant = gen(ref)
            if variant is None or variant == ref:
                continue
            # legal variant must preserve the asset inventory
            if Counter((a.type, a.raw) for a in extract_assets(ref)) != \
               Counter((a.type, a.raw) for a in extract_assets(variant)):
                continue
            n_variants += 1
            by_gen[name] += 1
            g = score_item(src, variant)
            if not g["pass"]:
                flips += 1
                flip_by_gen[name] += 1
                for gate, ok in g.items():
                    if gate != "pass" and not ok:
                        flip_by_gate[gate] += 1
                if len(examples) < 6:
                    examples.append({"gen": name, "src": src[:70], "variant": variant[:70],
                                     "failed": [gate for gate, ok in g.items() if gate != "pass" and not ok]})

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
        "flips_by_gate": dict(flip_by_gate),
        "examples": examples,
    }
    lm_items = lm_total = 0
    for r in records:
        if r["target_lang"] != "ca":
            continue
        lm = legal_moves(extract_assets(r["source"]))
        if lm:
            lm_items += 1; lm_total += len(lm)
    report["legal_moves_sources_with_movable"] = lm_items
    report["legal_moves_total_marks"] = lm_total
    print(json.dumps(report, indent=2, ensure_ascii=False))
    (PKG / "k2_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
