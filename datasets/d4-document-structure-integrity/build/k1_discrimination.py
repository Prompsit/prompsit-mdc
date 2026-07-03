#!/usr/bin/env python3
"""K1 - discriminative-power test for D4 (offline, corruption-operator panel).

A structure-flattening engine drops the document tree, a raw engine breaks
round-trip, targeted engines drop a node / break a link. Score with the real D4
validators; paired bootstrap per failure class. ASCII-only.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import documents as D  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
REFS = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl"]
SEED = 20260615
CLASSES = D.ALL_CLASSES


def eng_strong(r, rng):
    return r["reference"]


def eng_commercial(r, rng):
    if rng.random() < 0.05:
        for c in r["failure_opportunity_tags"]:
            x = D.corrupt(c, r["reference"])
            if x:
                return x
    return r["reference"]


def eng_realistic(r, rng):
    # realistic MID baseline (~50% pass) so the discrimination test is a real
    # statistical comparison, not a saturated 100-vs-0 case.
    if rng.random() < 0.5:
        for c in r["failure_opportunity_tags"]:
            x = D.corrupt(c, r["reference"])
            if x:
                return x
    return r["reference"]


def eng_flatten(r, rng):
    return re.sub(r"<[^>]+>", "", r["reference"])  # strip the document tree


def eng_raw(r, rng):
    return D.corrupt("roundtrip_failure", r["reference"])


def eng_node_dropper(r, rng):
    return D.corrupt("lost_or_duplicated_node", r["reference"]) or r["reference"]


def eng_link_breaker(r, rng):
    return D.corrupt("broken_link_image", r["reference"]) or r["reference"]


ENGINES = {"strong_structure_aware": eng_strong, "commercial_mid": eng_commercial,
           "realistic_mid": eng_realistic,
           "node_dropper": eng_node_dropper, "link_breaker": eng_link_breaker,
           "structure_flattener": eng_flatten, "raw_weak": eng_raw}
BROAD = ["structure_flattener", "raw_weak", "realistic_mid"]
TARGETED = {"node_dropper": ["lost_or_duplicated_node"],
            "link_breaker": ["broken_link_image"]}


def paired_bootstrap(a, b, iters=2000, seed=0):
    rng = random.Random(seed)
    n = len(a)
    if sum(a) / n - sum(b) / n <= 0:
        return 1.0
    ge = 0
    for _ in range(iters):
        s = [rng.randrange(n) for _ in range(n)]
        if sum(a[i] for i in s) / n - sum(b[i] for i in s) / n <= 0:
            ge += 1
    return ge / iters


def main():
    recs = []
    for f in REFS:
        if f.exists():
            recs += [json.loads(l) for l in open(f, encoding="utf-8")]
    rng = random.Random(SEED)
    passes = {e: defaultdict(list) for e in ENGINES}
    overall = {e: [] for e in ENGINES}
    for r in recs:
        if not D.score_item(r, r["reference"])["pass"]:
            continue
        for e, fn in ENGINES.items():
            ok = 1 if D.score_item(r, fn(r, rng))["pass"] else 0
            overall[e].append(ok)
            for c in r["failure_opportunity_tags"]:
                passes[e][c].append(ok)

    best = "strong_structure_aware"
    sep = {}
    for e in [*BROAD, *TARGETED]:
        per_class, classes_sep = {}, 0
        for c in CLASSES:
            a, b = passes[best][c], passes[e][c]
            if len(a) < 20:
                continue
            p = paired_bootstrap(a, b, seed=(sum((i + 1) * ord(ch) for i, ch in enumerate(str(e) + "|" + str(c))) & 0xFFFF))
            separated = p < 0.05
            classes_sep += separated
            per_class[c] = {"best_pass": round(100 * sum(a) / len(a), 1),
                            "eng_pass": round(100 * sum(b) / len(b), 1),
                            "p": round(p, 4), "separated": separated}
        if e in BROAD:
            v = "SEPARATED" if classes_sep >= len(per_class) / 2 else "NOT_SEPARATED"
            sep[e] = {"kind": "broad", "classes_separated": classes_sep,
                      "classes_total": len(per_class), "verdict": v, "per_class": per_class}
        else:
            tgt = all(per_class.get(c, {}).get("separated") for c in TARGETED[e])
            sep[e] = {"kind": "targeted", "target_classes": TARGETED[e],
                      "verdict": "LOCALIZED" if tgt else "MISSED_TARGET", "per_class": per_class}

    k1 = (all(sep[e]["verdict"] == "SEPARATED" for e in BROAD)
          and all(sep[e]["verdict"] == "LOCALIZED" for e in TARGETED))
    report = {"scored_items_clean": len(overall[best]),
              "engines_overall_pass_pct": {e: round(100 * sum(overall[e]) / (len(overall[e]) or 1), 1)
                                           for e in ENGINES},
              "best_engine": best, "separation_vs_best": sep,
              "k1_verdict": "PASS" if k1 else "FAIL",
              "note": "Corruption-operator simulation; real D4 validators."}
    Path(PKG / "k1_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print(json.dumps({"k1_verdict": report["k1_verdict"],
                      "engines_overall_pass_pct": report["engines_overall_pass_pct"],
                      "verdicts": {e: sep[e]["verdict"] for e in sep}}, indent=2))


if __name__ == "__main__":
    main()
