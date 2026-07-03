#!/usr/bin/env python3
"""Materialize the K1 simulated-engine panel as published baseline files.

Each dataset's build/k1_discrimination.py already defines a panel of >=5
corruption-operator "engines" (a strong reference-aware system, a couple of
mid-quality systems, deliberately weak ones such as raw_weak /
*_passthrough, and targeted probes) and scores them with the REAL validators.
This tool reuses those exact engines and writes their per-item outputs to

    datasets/<id>/baselines/<engine>/<pair>.jsonl
    -> {"item_id", "target_lang", "hypothesis"}

i.e. the same on-disk shape as D1's live Prompsit-API baselines, so the >=5
baselines required by the requirements checklist (sec.10, "including one that is
'bad' on the task") exist as concrete artifacts WITHOUT a network credential.

These are OFFLINE simulated baselines on the reference-bearing splits (dev +
test.ref), because the engines transform the reference. Live system
baselines over the gated test inputs come from each dataset's
baselines/run_baselines.py once a Prompsit credential is available; this tool
and that runner write the same format and can be mixed freely.

Usage:
  python tools/baselines/materialize_baselines.py --dataset d2-locale-data-integrity
  python tools/baselines/materialize_baselines.py --all
ASCII-only; deterministic (per-engine seeded RNG).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATASETS = REPO / "datasets"

# Per-dataset adapter: how to turn an engine fn + record into a hypothesis
# string. Every engine in every panel returns a string; only the call shape
# differs. `k1` is the imported k1_discrimination module.
def _adapt_d1(k1, fn, r, rng):
    return fn(r["reference"], rng)


def _adapt_d2(k1, fn, r, rng):
    ent = r["entities"][0]
    return fn(ent, r["target_lang"], k1.value_from_semantic(ent), rng)


def _adapt_record(k1, fn, r, rng):  # d3 / d4 / d5: fn(record, rng)
    return fn(r, rng)


ADAPTERS = {
    "d1-inline-asset-integrity": _adapt_d1,
    "d2-locale-data-integrity": _adapt_d2,
    "d3-structured-resource-integrity": _adapt_record,
    "d4-document-structure-integrity": _adapt_record,
    "d5-linguistic-resource-adherence": _adapt_record,
}


def load_k1(dataset_dir: Path):
    """Import datasets/<id>/build/k1_discrimination.py as a module."""
    k1_path = dataset_dir / "build" / "k1_discrimination.py"
    spec = importlib.util.spec_from_file_location(f"{dataset_dir.name}_k1", k1_path)
    mod = importlib.util.module_from_spec(spec)
    # build/ must be importable so its sibling deps (validators, *_oracle) load
    import sys
    build_dir = dataset_dir / "build"
    before = set(sys.modules)
    sys.path.insert(0, str(build_dir))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
        # Sibling deps are imported by bare name (validators, *_oracle) and would
        # otherwise shadow the next dataset's same-named modules. Drop the ones
        # that live in THIS build dir so each dataset reimports its own.
        build_str = str(build_dir)
        for name in set(sys.modules) - before:
            f = getattr(sys.modules.get(name), "__file__", None)
            if f and build_str in str(Path(f)):
                del sys.modules[name]
    return mod


def ref_records(k1) -> list:
    recs = []
    for f in k1.REFS:
        if Path(f).exists():
            recs += [json.loads(line) for line in open(f, encoding="utf-8")]
    return recs


def materialize(dataset_id: str) -> dict:
    dataset_dir = DATASETS / dataset_id
    adapt = ADAPTERS[dataset_id]
    k1 = load_k1(dataset_dir)
    recs = ref_records(k1)
    out_root = dataset_dir / "baselines"

    written = {}
    for ename, fn in k1.ENGINES.items():
        # stable per-engine seed (hash() is salted per process, so derive one)
        seed = sum((i + 1) * ord(ch) for i, ch in enumerate(ename)) & 0xFFFFFFFF
        rng = random.Random(seed)
        by_pair = {}
        for r in recs:
            hyp = adapt(k1, fn, r, rng)
            pair = "en-%s" % r["target_lang"]
            by_pair.setdefault(pair, []).append(
                {"item_id": r["item_id"], "target_lang": r["target_lang"],
                 "hypothesis": hyp if isinstance(hyp, str) else json.dumps(hyp, ensure_ascii=False)})
        eng_dir = out_root / ename
        eng_dir.mkdir(parents=True, exist_ok=True)
        for pair, rows in sorted(by_pair.items()):
            with open(eng_dir / ("%s.jsonl" % pair), "w", encoding="utf-8", newline="\n") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        written[ename] = sum(len(v) for v in by_pair.values())

    # README next to the engine dirs (the per-item outputs are git-ignored)
    weak = [e for e in k1.ENGINES if "raw" in e or "passthrough" in e or "ignorer" in e
            or "blind" in e or "violator" in e or "dropper" in e or "flatten" in e]
    (out_root / "README.md").write_text(
        "# Baselines (%s)\n\n"
        "K1 discrimination panel from `build/k1_discrimination.py`, scored by the "
        "dataset validators. The per-item outputs `<engine>/<pair>.jsonl` "
        "(`{item_id, target_lang, hypothesis}`) are **git-ignored and regenerated "
        "on demand**:\n\n"
        "    python tools/baselines/materialize_baselines.py --dataset %s\n\n"
        "- Engines (%d, >=5 incl. deliberately weak): %s\n"
        "- Deliberately weak/'bad' on the task: %s\n"
        "- Split: dev + test.ref (engines transform the reference).\n"
        "- Engine pass-rates: `../k1_report.json`. Live Prompsit-API baselines over "
        "the gated test inputs: run `baselines/run_baselines.py` with a credential.\n"
        % (dataset_id, dataset_id, len(k1.ENGINES), ", ".join(k1.ENGINES),
           ", ".join(weak) or "(see panel)"),
        encoding="utf-8", newline="\n")
    return {"dataset": dataset_id, "engines": list(k1.ENGINES), "records_per_engine": written}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", help="dataset id under datasets/, e.g. d2-locale-data-integrity")
    ap.add_argument("--all", action="store_true", help="materialize every dataset")
    args = ap.parse_args()

    ids = list(ADAPTERS) if args.all else [args.dataset]
    if not ids or ids == [None]:
        ap.error("pass --dataset <id> or --all")
    for did in ids:
        res = materialize(did)
        print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
