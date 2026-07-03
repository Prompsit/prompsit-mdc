#!/usr/bin/env python3
"""K1 - discrimination check (release requirement), offline edition.

A benchmark must separate a weak system from a strong one. With no live API
credential we stand in a panel of engines simulated by corruption operators that
mutate the reference rendering the way real engines fail (an unlocalized-passthrough
engine keeps the en-US form, a conversion-blind engine never metricates units,
etc.), score every output with the REAL D2 validators, and run paired bootstrap
between systems per failure class.

Stop rule: if the deliberately weak engine is NOT separated from the
best engine on >= half the classes (paired-bootstrap p > 0.05) -> redesign. When
a live credential exists, feed real baselines/<system>/<pair>.jsonl here instead;
the scoring + stats are identical. ASCII-only.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402
from validators import score_entity, value_from_semantic  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
REFS = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl"]
SEED = 20260615
CLASSES = o.ALL_CLASSES


# --- engines: reference rendering -> an engine's output rendering -------------

def eng_strong(ent, lang, value, rng, track):
    return ent["raw_target"]


def eng_commercial(ent, lang, value, rng, track):
    if rng.random() < 0.05:
        cs = o.scoreable_classes(ent["kind"], value, lang, track)
        if cs:
            return o.corrupt(cs[0], ent["kind"], value, lang, track)
    return ent["raw_target"]


def eng_realistic(ent, lang, value, rng, track):
    # realistic MID baseline (~50% pass) so the discrimination test is a real
    # statistical comparison, not a saturated 100-vs-0 case.
    if rng.random() < 0.5:
        cs = o.scoreable_classes(ent["kind"], value, lang, track)
        if cs:
            return o.corrupt(cs[0], ent["kind"], value, lang, track)
    return ent["raw_target"]


def eng_passthrough(ent, lang, value, rng, track):
    return o.render(ent["kind"], value, o.SOURCE_LANG, track)  # unlocalized en-US form


def eng_raw(ent, lang, value, rng, track):
    out = o.render(ent["kind"], value, o.SOURCE_LANG, track)
    swap = o.corrupt("wrong_decimal_separator", ent["kind"], value, lang, track)
    return swap if (swap and rng.random() < 0.5) else out


def eng_separator(ent, lang, value, rng, track):
    c = o.corrupt("wrong_decimal_separator", ent["kind"], value, lang, track)
    return c if (c and rng.random() < 0.85) else ent["raw_target"]


ENGINES = {
    "strong_locale_aware": eng_strong,
    "commercial_mid": eng_commercial,
    "realistic_mid": eng_realistic,
    "separator_weak": eng_separator,
    "unlocalized_passthrough": eng_passthrough,
    "raw_weak": eng_raw,
}
BROAD = ["unlocalized_passthrough", "raw_weak", "realistic_mid"]
TARGETED = {"separator_weak": ["wrong_decimal_separator"]}


def paired_bootstrap(a, b, iters=2000, seed=0):
    """One-sided p that engine B's pass-rate >= engine A's (A=best)."""
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
        ent = r["entities"][0]
        lang = r["target_lang"]
        track = r.get("track", "format")
        value = value_from_semantic(ent)
        classes = r["failure_opportunity_tags"]
        # clean positive: the reference must be accepted by the validator
        if not score_entity(ent, lang, ent["raw_target"], track)["pass"]:
            continue
        for ename, fn in ENGINES.items():
            hyp = fn(ent, lang, value, rng, track)
            ok = 1 if score_entity(ent, lang, hyp, track)["pass"] else 0
            overall[ename].append(ok)
            for c in classes:
                passes[ename][c].append(ok)

    best = "strong_locale_aware"
    sep = {}
    for e in [*BROAD, *TARGETED]:
        per_class = {}
        classes_sep = 0
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
            verdict = "SEPARATED" if classes_sep >= len(per_class) / 2 else "NOT_SEPARATED"
            sep[e] = {"kind": "broad", "classes_separated": classes_sep,
                      "classes_total": len(per_class), "verdict": verdict,
                      "per_class": per_class}
        else:
            tgt_ok = all(per_class.get(c, {}).get("separated") for c in TARGETED[e])
            sep[e] = {"kind": "targeted", "target_classes": TARGETED[e],
                      "separated_on_target": tgt_ok,
                      "classes_separated": classes_sep, "classes_total": len(per_class),
                      "verdict": "LOCALIZED" if tgt_ok else "MISSED_TARGET",
                      "per_class": per_class}

    k1_pass = (all(sep[e]["verdict"] == "SEPARATED" for e in BROAD)
               and all(sep[e]["verdict"] == "LOCALIZED" for e in TARGETED))
    report = {
        "scored_items_clean": len(overall[best]),
        "engines_overall_pass_pct": {
            e: round(100 * sum(overall[e]) / (len(overall[e]) or 1), 1)
            for e in ENGINES},
        "best_engine": best,
        "separation_vs_best": sep,
        "k1_verdict": "PASS" if k1_pass else "FAIL",
        "note": "Engines are corruption-operator simulations; scoring uses the real "
                "D2 validators. Swap in live baselines/<system>/<pair>.jsonl when a "
                "credential is available.",
    }
    Path(PKG / "k1_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"k1_verdict": report["k1_verdict"],
                      "engines_overall_pass_pct": report["engines_overall_pass_pct"],
                      "verdicts": {e: sep[e]["verdict"] for e in sep}},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
