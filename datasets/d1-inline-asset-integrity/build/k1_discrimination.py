"""K1 — discrimination check (release requirement), offline edition.

A benchmark must separate a weak system from a strong one. With no live API
credential, we stand in a panel of engines simulated by *corruption operators*
that mutate the reference the way real engines fail (a tag-blind engine
strips tags, an ICU-weak engine breaks a plural branch, etc.), then score every
output with the REAL D1 validators (build/validators.py) and run paired
bootstrap between systems per asset class.

Stop rule: if the deliberately weak/tag-blind engine is NOT separated
from the best engine on >= half the classes (paired-bootstrap p > 0.05) ->
redesign. When a live credential exists, run run_baselines.py and feed the real
baselines/<system>/<pair>.jsonl here instead — the scoring + stats are identical.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validators import score_item
from assets import extract_assets

PKG = Path(__file__).parent.parent
REFS = [PKG / "data" / "dev.jsonl", PKG / "data" / "test.ref.jsonl"]
SEED = 20260605
CLASSES = ["xliff", "html_tag", "software_placeholder", "template_variable",
           "icu_messageformat", "markdown_inline", "do_not_translate"]

TAG_RE = re.compile(r"</?xliff:g[^>]*>|</?(?:b|i|u|em|strong|a|code|span)\b[^>]*>|<ph[^>]*/>|<[^>]*/>")
PH_RE = re.compile(r"%(?:\d+\$)?[sdfeEgGxXc]|\{\d+\}|\{\{[^}]*\}\}|\{[A-Za-z_][\w.-]*\}")


# --- corruption operators: each maps a reference -> an engine's output --------

def eng_strong(ref, rng):
    return ref  # perfect: preserves everything


def eng_commercial(ref, rng):
    # occasionally drops one placeholder (5%)
    phs = PH_RE.findall(ref)
    if phs and rng.random() < 0.05:
        return ref.replace(phs[0], "", 1)
    return ref


def eng_tag_blind(ref, rng):
    # strips inline tags entirely (the classic tag-unaware NMT); keeps text/placeholders
    return TAG_RE.sub("", ref)


def eng_icu_weak(ref, rng):
    # breaks an ICU plural: drop the 'other' branch keyword
    if "plural" in ref and rng.random() < 0.8:
        return re.sub(r"\bother\s*\{", "{", ref, count=1)
    return ref


def eng_placeholder_weak(ref, rng):
    # corrupts placeholder syntax: '%s' -> '% s', '{0}' -> '{ 0 }'
    out = ref
    if rng.random() < 0.6:
        out = re.sub(r"%(\d*\$?[sd])", r"% \1", out, count=1)
        out = re.sub(r"\{(\d+)\}", r"{ \1 }", out, count=1)
    return out


def eng_raw(ref, rng):
    # weak all-round: drop first tag AND first placeholder sometimes
    out = ref
    if rng.random() < 0.5:
        out = TAG_RE.sub("", out, count=2)
    phs = PH_RE.findall(out)
    if phs and rng.random() < 0.4:
        out = out.replace(phs[0], "", 1)
    return out


ENGINES = {
    "strong_tag_aware": eng_strong,
    "commercial_mid": eng_commercial,
    "icu_weak": eng_icu_weak,
    "placeholder_weak": eng_placeholder_weak,
    "tag_blind_nmt": eng_tag_blind,
    "raw_nmt": eng_raw,
}


def paired_bootstrap(a, b, iters=2000, seed=0):
    """One-sided p that engine B's pass-rate >= engine A's (A=best). a,b are
    aligned 0/1 lists over the same items."""
    rng = random.Random(seed)
    n = len(a)
    obs = sum(a) / n - sum(b) / n
    if obs <= 0:
        return 1.0
    ge = 0
    idx = list(range(n))
    for _ in range(iters):
        s = [idx[rng.randrange(n)] for _ in range(n)]
        da = sum(a[i] for i in s) / n - sum(b[i] for i in s) / n
        if da <= 0:
            ge += 1
    return ge / iters


def main():
    recs = []
    for f in REFS:
        if f.exists():
            recs += [json.loads(l) for l in open(f, encoding="utf-8")]
    rng = random.Random(SEED)

    # pass[engine][class] = list of 0/1 over items that carry that class
    passes = {e: defaultdict(list) for e in ENGINES}
    overall = {e: [] for e in ENGINES}
    for r in recs:
        src, ref, classes = r["source"], r["reference"], set(r["asset_class_tags"])
        # only score items whose reference the validator accepts (clean positives)
        if not score_item(src, ref)["pass"]:
            continue
        for ename, fn in ENGINES.items():
            hyp = fn(ref, rng)
            ok = 1 if score_item(src, hyp)["pass"] else 0
            overall[ename].append(ok)
            for c in classes:
                passes[ename][c].append(ok)

    best = "strong_tag_aware"
    rows = {}
    for e in ENGINES:
        n = len(overall[e]) or 1
        rows[e] = {"overall_pass_pct": round(100 * sum(overall[e]) / n, 1)}

    # Two engine kinds need different criteria:
    #  - BROAD-weak (tag-blind / raw NMT): the K1 baseline -> must be
    #    separated from best on >= half of ALL classes.
    #  - TARGETED-weak (icu_weak, placeholder_weak): diagnostic probes -> must be
    #    separated on their TARGET class, and SHOULD look identical elsewhere
    #    (correct localization). Separating everywhere would mean the metric
    #    leaks across classes.
    BROAD = ["tag_blind_nmt", "raw_nmt"]
    TARGETED = {"icu_weak": ["icu_messageformat"],
                "placeholder_weak": ["software_placeholder", "template_variable"]}
    sep = {}
    for e in [*BROAD, *TARGETED]:
        classes_sep = 0
        per_class = {}
        for c in CLASSES:
            a = passes[best][c]; b = passes[e][c]
            if len(a) < 20:
                continue
            p = paired_bootstrap(a, b, seed=(sum((i + 1) * ord(ch) for i, ch in enumerate(str(e) + "|" + str(c))) & 0xFFFF))
            ra, rb = 100 * sum(a) / len(a), 100 * sum(b) / len(b)
            separated = p < 0.05
            classes_sep += separated
            per_class[c] = {"best_pass": round(ra, 1), "eng_pass": round(rb, 1),
                            "p": round(p, 4), "separated": separated}
        if e in BROAD:
            verdict = "SEPARATED" if classes_sep >= len(per_class) / 2 else "NOT_SEPARATED"
            sep[e] = {"kind": "broad", "classes_separated": classes_sep,
                      "classes_total": len(per_class), "verdict": verdict, "per_class": per_class}
        else:
            tgt_ok = all(per_class.get(c, {}).get("separated") for c in TARGETED[e])
            sep[e] = {"kind": "targeted", "target_classes": TARGETED[e],
                      "separated_on_target": tgt_ok,
                      "classes_separated": classes_sep, "classes_total": len(per_class),
                      "verdict": "LOCALIZED" if tgt_ok else "MISSED_TARGET", "per_class": per_class}

    k1_pass = (all(sep[e]["verdict"] == "SEPARATED" for e in BROAD)
               and all(sep[e]["verdict"] == "LOCALIZED" for e in TARGETED))
    report = {
        "scored_items_clean": len(overall[best]),
        "engines_overall_pass_pct": {e: rows[e]["overall_pass_pct"] for e in ENGINES},
        "best_engine": best,
        "separation_vs_best": sep,
        "k1_verdict": "PASS" if k1_pass else "FAIL",
        "note": "Engines are corruption-operator simulations; scoring uses the real D1 validators. "
                "Swap in live baselines/<system>/<pair>.jsonl when a credential is available.",
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    (PKG / "k1_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
