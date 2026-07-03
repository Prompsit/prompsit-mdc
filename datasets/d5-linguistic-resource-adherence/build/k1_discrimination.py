#!/usr/bin/env python3
"""K1 - discriminative-power test for D5 (offline, corruption-operator panel).

A resource-ignoring engine never applies the glossary/TM (leaves the source term),
a raw engine uses a wrong term; targeted engines violate the glossary or copy a bad
fuzzy match. Score with the real D5 validator; paired bootstrap per failure class.
ASCII-only.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lingres as L  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
REFS = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl"]
SEED = 20260615
CLASSES = L.ALL_CLASSES


def _out(r, term):
    base = r["reference"].rsplit(" [", 1)[0]
    return base + " " + L.make_slot(term, r["repeated"])


def eng_strong(r, rng):
    return r["reference"]


def eng_commercial(r, rng):
    if rng.random() < 0.05:
        for c in r["failure_opportunity_tags"]:
            x = L.corrupt(c, r)
            if x:
                return x
    return r["reference"]


def eng_realistic(r, rng):
    # realistic MID baseline (~50% pass) so the discrimination test is a real
    # statistical comparison, not a saturated 100-vs-0 case.
    if rng.random() < 0.5:
        for c in r["failure_opportunity_tags"]:
            x = L.corrupt(c, r)
            if x:
                return x
    return r["reference"]


def eng_resource_ignorer(r, rng):
    return _out(r, r["en_term"])           # never applies glossary/TM


def eng_raw(r, rng):
    return _out(r, r["other_term"])        # wrong term throughout


def eng_glossary_violator(r, rng):
    return _out(r, r["en_term"]) if r["kind"] == "glossary" else r["reference"]


def eng_fuzzy_copier(r, rng):
    return _out(r, r["stale_term"]) if r["kind"] == "tm_fuzzy" else r["reference"]


ENGINES = {"strong_resource_aware": eng_strong, "commercial_mid": eng_commercial,
           "realistic_mid": eng_realistic,
           "glossary_violator": eng_glossary_violator, "fuzzy_copier": eng_fuzzy_copier,
           "resource_ignorer": eng_resource_ignorer, "raw_weak": eng_raw}
BROAD = ["resource_ignorer", "raw_weak", "realistic_mid"]
TARGETED = {"glossary_violator": ["required_term_missing"],
            "fuzzy_copier": ["fuzzy_discernment"]}


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
        if not L.score_item(r, r["reference"])["pass"]:
            continue
        for e, fn in ENGINES.items():
            ok = 1 if L.score_item(r, fn(r, rng))["pass"] else 0
            overall[e].append(ok)
            for c in r["failure_opportunity_tags"]:
                passes[e][c].append(ok)

    best = "strong_resource_aware"
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
              "note": "Corruption-operator simulation; real D5 validator."}
    Path(PKG / "k1_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print(json.dumps({"k1_verdict": report["k1_verdict"],
                      "engines_overall_pass_pct": report["engines_overall_pass_pct"],
                      "verdicts": {e: sep[e]["verdict"] for e in sep}}, indent=2))


if __name__ == "__main__":
    main()
