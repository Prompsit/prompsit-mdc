#!/usr/bin/env python3
"""Build the D5 v1.0 (Linguistic-resource adherence) package - deterministic.

Real resources:
  - terminology: CLDR display names (territories / languages / currencies) via
    Babel (Unicode license), real translations across 9 languages;
  - carriers + a real translation-memory backbone: human-translated sentences
    from the local D1 core (license inherited).

Each item embeds a term into a `[...]` slot of a real carrier and attaches the
provided resources (a glossary entry and/or a TM match). Four item kinds cover the
six failure classes: glossary (required/forbidden/inconsistent), tm_exact
(approved-TM-ignored), tm_fuzzy (bad-fuzzy-copied), conflict (glossary-vs-TM).
ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from babel import __version__ as BABEL_VERSION

sys.path.insert(0, str(Path(__file__).parent))
import lingres as L  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
_D1_REFS = PKG.parent / "d1-inline-asset-integrity" / "data"
CORE = [_D1_REFS / "dev.jsonl", _D1_REFS / "test.ref.jsonl"]  # D1 9-language human references
DATA, PRIV = PKG / "data", PKG / "private"

SCHEMA_VERSION = "0.2"
VERSION = "1.0"
SEED = 705719668539613162
SPLITS = {"dev": 0.10, "test": 0.70, "hidden": 0.20}
FLOOR = 400  # records per reported class in the K1 scored set (dev+test)
# parity across the four resource kinds; glossary is upsized because its three
# classes (required/forbidden/inconsistent) share the glossary records and
# forbidden is not scoreable on every locale.
KIND_QUOTA = {"glossary": 150, "tm_exact": 120, "tm_fuzzy": 120, "conflict": 120}
PROVENANCE = {"terminology": "CLDR display names via Babel",
              "terminology_license": "Unicode-3.0",
              "terminology_url": "https://unicode.org/Public/cldr/",
              "babel_version": BABEL_VERSION,
              "carrier_tm": "D1 human translations, license inherited"}


def load_carriers():
    by = defaultdict(dict)
    for line in (ln for cf in CORE for ln in open(cf, encoding="utf-8")):
        r = json.loads(line)
        by[r["item_id"]][r["target_lang"]] = r["reference"]
        by[r["item_id"]]["en"] = r["source"]
        by[r["item_id"]]["_item_id"] = r["item_id"]
        by[r["item_id"]]["_provenance"] = r.get("provenance") or {}
    out = [m for m in by.values()
           if set(m) >= set(["en"] + L.LANGS)
           and all(3 <= len(m[l]) <= 90 for l in ["en"] + L.LANGS)]
    out.sort(key=lambda m: m["en"])
    return out


def carrier_provenance(carrier):
    prov = carrier.get("_provenance") or {}
    return {
        "item_id": carrier.get("_item_id"),
        "corpus": prov.get("corpus"),
        "license": prov.get("license"),
        "url": prov.get("url"),
        "ref": prov.get("ref"),
        "source_key": prov.get("source_key"),
    }


def main():
    bank = L.term_bank()
    carriers = load_carriers()
    print("terms:", len(bank), "carriers:", len(carriers))

    items = []
    idx = 0
    for kind, quota in KIND_QUOTA.items():
        for j in range(quota):
            en_term, tr = bank[idx % len(bank)]
            other_en, other_tr = bank[(idx + 1) % len(bank)]
            stale_en, stale_tr = bank[(idx + 2) % len(bank)]
            carrier = carriers[idx % len(carriers)]
            repeated = (kind == "glossary")
            iid = "d5-%06d" % idx
            recs = []
            for lang in L.LANGS:
                ref_term = tr[lang]
                base_src = carrier["en"]
                base_ref = carrier[lang]
                source = base_src + " " + L.make_slot(en_term, repeated)
                reference = base_ref + " " + L.make_slot(ref_term, repeated)
                # forbidden_term_used is a GLOSSARY-only class (KIND_CLASSES / spec),
                # so the forbidden list is set only for glossary; enforced over the
                # whole hypothesis, but skipped when the term occurs naturally in the
                # reference carrier (avoids false positives).
                forb = [other_tr[lang]] if (kind == "glossary" and other_tr[lang]
                        and other_tr[lang] != ref_term
                        and not L.term_in(other_tr[lang], reference)) else []
                resources = _resources(kind, lang, source, base_ref, repeated,
                                       en_term, ref_term, other_tr[lang], stale_tr[lang])
                recs.append({
                    "item_id": iid, "source_lang": "en", "target_lang": lang,
                    "kind": kind, "track": L.track_for(kind),
                    "source": source, "reference": reference,
                    "ref_term": ref_term, "en_term": en_term,
                    "other_term": other_tr[lang], "stale_term": stale_tr[lang],
                    "forbidden_terms": forb,
                    "repeated": repeated, "resources": resources,
                    "expected_invariants": ["required_terms_used", "forbidden_terms_absent",
                                            "term_consistency", "approved_tm_reused",
                                            "fuzzy_match_discernment", "conflict_resolved"],
                    "resource_profile_tags": [kind],
                    "provenance": {**PROVENANCE, "schema_version": SCHEMA_VERSION,
                                    "carrier_item_id": carrier.get("_item_id"),
                                    "carrier_provenance": carrier_provenance(carrier),
                                    "annotation_status": "oracle_validated"},
                })
            # scoreable classes per locale (term differences are locale-specific)
            for r in recs:
                r["failure_opportunity_tags"] = L.scoreable_classes(r)
            classes = sorted({c for r in recs for c in r["failure_opportunity_tags"]})
            items.append({"iid": iid, "kind": kind, "classes": classes, "recs": recs})
            idx += 1

    assign_splits(items)
    split_records = emit(items)

    # per-class floor on RECORDS in the K1 scored set (dev+test), grouped by the
    # resource track each class belongs to. Headline = glossary + tm;
    # conflict and quality (fuzzy discernment) are reported apart, never folded in.
    k1_split = {"dev", "test"}
    rec_k1, rec_test = Counter(), Counter()
    for it in items:
        for r in it["recs"]:
            for c in r["failure_opportunity_tags"]:
                if r["split"] in k1_split:
                    rec_k1[c] += 1
                if r["split"] == "test":
                    rec_test[c] += 1
    class_track = {c: L.track_for(k) for k, cs in L.KIND_CLASSES.items() for c in cs}
    quota = {c: {"records_k1": rec_k1.get(c, 0), "records_test": rec_test.get(c, 0),
                 "track": class_track.get(c),
                 "status": "PASS" if rec_k1.get(c, 0) >= FLOOR else "FAIL"}
             for c in L.ALL_CLASSES}
    tracks = {t: {"classes": [c for c in L.ALL_CLASSES if class_track[c] == t],
                  "headline": t in L.HEADLINE_TRACKS}
              for t in L.TRACKS}
    manifest = {
        "name": "prompsit-d5-linguistic-resource-adherence",
        "version": VERSION, "schema_version": SCHEMA_VERSION, "seed": SEED,
        "correctness_logic": "respect the provided linguistic resources",
        "languages": {"source": "en", "targets": L.LANGS},
        "resource_profiles": list(KIND_QUOTA),
        "tracks": tracks,
        "delivery_contract": {
            "glossary": "vendor-specific forced terminology (Google/DeepL/MS "
                        "dictionaries); many engines (incl. prompsit) have none",
            "tm": "universal TMX import / segment API",
            "conflict": "glossary-over-TM precedence; TM-only systems cannot satisfy "
                        "it -> reported apart, never headlined",
            "quality": "fuzzy-match discernment: a stale 85% match must NOT be "
                       "copied (anti-correlated with adherence; not an adherence metric)",
        },
        "sources": len(items), "records": sum(split_records.values()),
        "splits_records": split_records,
        "splits_sources": dict(Counter(it["recs"][0]["split"] for it in items)),
        "resource_profile_sources": dict(Counter(it["kind"] for it in items)),
        "classes": L.ALL_CLASSES,
        "per_class_floor": FLOOR,
        "quota": quota,
        "quota_status": {c: quota[c]["status"] for c in L.ALL_CLASSES},
        "resource_sources": PROVENANCE,
        "annotation_status": "oracle_validated",
    }
    (PKG / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in
                      ("sources", "records", "resource_profile_sources",
                       "quota_status")}, indent=2))
    print(json.dumps(quota, indent=2, ensure_ascii=False))


def _resources(kind, lang, source, base_ref, repeated, en_term, ref_term, other, stale):
    if kind == "glossary":
        return {"glossary": [{"term": en_term, "required": ref_term,
                              "forbidden": [en_term, other]}]}
    if kind == "tm_exact":
        return {"tm": [{"source": source, "target": base_ref + " " + L.make_slot(ref_term, repeated),
                        "match_pct": 100}]}
    if kind == "tm_fuzzy":
        return {"tm": [{"source": source.replace("[%s]" % en_term, "[%s]" % other),
                        "target": base_ref + " " + L.make_slot(stale, repeated),
                        "match_pct": 85}]}
    if kind == "conflict":
        return {"glossary": [{"term": en_term, "required": ref_term}],
                "tm": [{"source": source, "target": base_ref + " " + L.make_slot(stale, repeated),
                        "match_pct": 100}]}
    return {}


def assign_splits(items):
    import random
    groups = defaultdict(list)
    for it in items:
        groups[frozenset([it["kind"], *it["classes"]])].append(it)
    rng = random.Random(SEED ^ 0xD5)
    for sig, members in sorted(groups.items(), key=lambda kv: sorted(kv[0])):
        members.sort(key=lambda x: x["iid"])
        rng.shuffle(members)
        n = len(members)
        n_dev = max(1, round(n * SPLITS["dev"])) if n >= 3 else (1 if n else 0)
        n_hidden = round(n * SPLITS["hidden"])
        for i, it in enumerate(members):
            s = ("dev" if i < n_dev else "hidden" if i < n_dev + n_hidden else "test")
            for r in it["recs"]:
                r["split"] = s


def emit(items):
    DATA.mkdir(parents=True, exist_ok=True)
    PRIV.mkdir(exist_ok=True)
    fh = {"dev": open(DATA / "dev.jsonl", "w", encoding="utf-8"),
          "ti": open(DATA / "test.input.jsonl", "w", encoding="utf-8"),
          "tg": open(DATA / "test.ref.jsonl", "w", encoding="utf-8"),
          "hi": open(PRIV / "hidden.input.jsonl", "w", encoding="utf-8"),
          "hg": open(PRIV / "hidden.ref.jsonl", "w", encoding="utf-8")}
    n = Counter()
    for it in sorted(items, key=lambda x: x["iid"]):
        for rec in it["recs"]:
            line = json.dumps(rec, ensure_ascii=False) + "\n"
            inp = {k: v for k, v in rec.items() if k not in ("reference", "ref_term")}
            iline = json.dumps(inp, ensure_ascii=False) + "\n"
            s = rec["split"]; n[s] += 1
            if s == "dev":
                fh["dev"].write(line)
            elif s == "test":
                fh["ti"].write(iline); fh["tg"].write(line)
            else:
                fh["hi"].write(iline); fh["hg"].write(line)
    for f in fh.values():
        f.close()
    return dict(n)


if __name__ == "__main__":
    main()
