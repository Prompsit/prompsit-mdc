#!/usr/bin/env python3
"""Build the D2 v1.0 (Locale-data integrity) package - deterministic, machine.

Pipeline (mirrors D1 build_dataset.py):
  1. load NATURAL carrier sentences from D1 (dev + test references, 9-language):
     EN source + human references in all 9 target locales, license inherited;
  2. deterministically inject ONE locale entity per item into a neutral slot
     `[...]` of the carrier (source = en-US rendering, reference = target-locale
     CLDR rendering via cldr_oracle) - the entity is the unit of evaluation, the
     carrier supplies realistic linguistic context + provenance;
  3. balance entity kinds (number / currency / date / unit) so every failure
     class clears its per-class-per-pair floor;
  4. dev/test/hidden split (10/70/20), stratified by class signature,
     partitioned by item_id (a source and all 9 locale records share a split);
  5. emit dev.jsonl, test.input/ref.jsonl, private/hidden.input/ref.jsonl,
     manifest.json.

Deterministic end-to-end: fixed seed derived from the dataset name. ASCII-only.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cldr_oracle as o  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
DATA = PKG / "data"
PRIV = PKG / "private"
_D1_REFS = PKG.parent / "d1-inline-asset-integrity" / "data"
CARRIERS = [_D1_REFS / "dev.jsonl", _D1_REFS / "test.ref.jsonl"]  # D1 9-language human references

SCHEMA_VERSION = "0.2"
VERSION = "1.0"
SEED = 7255450304059208671
SPLITS = {"dev": 0.10, "test": 0.70, "hidden": 0.20}

# (kind, track, source items). Each item -> 9 locale records. v1.0 resolution.
# target: every REPORTED class clears >=400 records in the K1 scored set
# (dev+test = 80% of records). FORMAT is the only track.
ITEM_SPECS = [
    ("number", "format", 160),
    ("currency", "format", 160),
    ("date", "format", 160),
    ("unit", "format", 200),       # symbol localization + separators (value as-is)
]
PER_CLASS_FLOOR = 400  # records per reported class in the K1 set (dev+test)


# --- deterministic value banks -----------------------------------------------
# Mixed magnitudes so grouping-dependent classes (wrong_grouping) fire on the
# larger values while small values still exercise decimal separators.
_NUMBERS = [1234567.5, 89012.34, 4500.0, 12.75, 305671.2, 76.4, 2048576.0,
            9999.99, 150.5, 27384.6, 6.25, 480920.75, 33.0, 1200000.0, 58.9]
_CUR_AMOUNTS = [1234.5, 49.99, 875000.0, 12.0, 3499.95, 250.0, 19999.9, 7.5]
_CUR_CODES = ["USD", "EUR", "GBP", "JPY"]
_DATES = ["2026-03-09", "2025-11-23", "2024-07-01", "2026-12-31", "2025-01-15",
          "2024-02-29", "2026-06-08", "2025-09-30", "2024-10-12", "2026-04-21"]
_UNITS = [(5, "length-mile"), (26.2, "length-mile"), (1200, "length-mile"),
          (6, "length-foot"), (180, "mass-pound"), (2.5, "volume-gallon"),
          (12, "length-inch"), (350, "mass-pound"), (60, "length-mile"),
          (3, "volume-gallon")]


def _pick(bank, h, n):
    return bank[(h + n) % len(bank)]


def entity_for(kind: str, h: int, n: int, track: str = "format") -> dict:
    """Build the canonical (locale-independent) entity for an item.

    Unit values are rendered as-is (symbol + separators localized, value
    unchanged), so conversion_required is always false in v1.0."""
    if kind == "number":
        v = _pick(_NUMBERS, h, n)
        return {"kind": "number", "value": v, "semantic": {"value": v},
                "conversion_required": False}
    if kind == "currency":
        amt = _pick(_CUR_AMOUNTS, h, n)
        code = _pick(_CUR_CODES, h, n // 3)
        amt = o.quantize_currency(amt, code)  # surface faithfully renders semantic
        return {"kind": "currency", "value": (amt, code),
                "semantic": {"amount": amt, "code": code},
                "conversion_required": False}
    if kind == "date":
        iso = _pick(_DATES, h, n)
        return {"kind": "date", "value": iso, "semantic": {"iso": iso},
                "conversion_required": False}
    if kind == "unit":
        amt, unit = _pick(_UNITS, h, n)
        return {"kind": "unit", "value": (amt, unit),
                "semantic": {"amount": amt, "unit": unit},
                "conversion_required": False}
    raise ValueError(kind)


# --- carriers -----------------------------------------------------------------

def load_carriers() -> list[dict]:
    """Unique EN sources from D1 core that carry human references in all 9
    target locales (rectangular)."""
    by_item: dict[str, dict] = {}
    for line in (ln for cf in CARRIERS for ln in open(cf, encoding="utf-8")):
        r = json.loads(line)
        it = by_item.setdefault(r["item_id"], {"source": r["source"],
                                               "refs": {}, "prov": r["provenance"],
                                               "item_id": r["item_id"]})
        it["refs"][r["target_lang"]] = r["reference"]
    carriers = [c for c in by_item.values()
                if set(c["refs"]) >= set(o.TARGET_LANGS)]
    carriers.sort(key=lambda c: c["source"])  # deterministic order
    return carriers


# --- item assembly ------------------------------------------------------------

def make_item(carrier: dict, kind: str, idx: int, track: str = "format") -> dict:
    h = int(hashlib.sha256((track + kind + carrier["source"]).encode()).hexdigest(), 16)
    ent = entity_for(kind, h, idx, track)
    val = ent["value"]
    raw_src = o.render(kind, val, o.SOURCE_LANG, track)
    # per-locale renderings + reference annotations (within this track)
    per_lang = {}
    fail_union = set()
    for lang in o.TARGET_LANGS:
        ref = o.render(kind, val, lang, track)
        accepted = o.accepted_variants(kind, val, lang, track)
        classes = o.scoreable_classes(kind, val, lang, track)
        unacceptable = {c: o.corrupt(c, kind, val, lang, track) for c in classes}
        per_lang[lang] = {"ref": ref, "accepted": accepted,
                          "classes": classes, "unacceptable": unacceptable}
        fail_union |= set(classes)
    return {"carrier": carrier, "kind": kind, "track": track, "entity": ent,
            "raw_src": raw_src, "per_lang": per_lang,
            "fail_tags": sorted(fail_union)}


def expected_invariants(kind: str, track: str, conv: bool) -> list[str]:
    inv = ["locale_form_conformant"]
    if kind in ("number", "currency", "unit"):
        inv.append("separators_correct")
    if kind == "currency":
        inv.append("currency_format_correct")
    if kind == "date":
        inv.append("datetime_format_correct")
    if kind == "unit":
        inv.append("unit_format_correct")  # symbol localized, value unchanged
    return inv


SLOT = "[%s]"  # neutral, locale-independent slot delimiter for the entity


def make_records(item: dict) -> list[dict]:
    c, kind, ent = item["carrier"], item["kind"], item["entity"]
    track = item["track"]
    iid = item["item_id"]
    src_text = c["source"] + " " + SLOT % item["raw_src"]
    inv = expected_invariants(kind, track, ent["conversion_required"])
    recs = []
    for lang in o.TARGET_LANGS:
        pl = item["per_lang"][lang]
        ref_text = c["refs"][lang] + " " + SLOT % pl["ref"]
        entity = {
            "id": "e1", "kind": kind,
            "raw_source": item["raw_src"], "raw_target": pl["ref"],
            "semantic": ent["semantic"],
            "conversion_required": ent["conversion_required"],
            "accepted_variants": pl["accepted"],
            "unacceptable": pl["unacceptable"],
        }
        recs.append({
            "item_id": iid,
            "source_lang": o.SOURCE_LANG, "source_locale": o.SOURCE_LOCALE,
            "target_lang": lang, "target_locale": o.LOCALES[lang],
            "source": src_text, "reference": ref_text,
            "entities": [entity],
            "expected_invariants": inv,
            "track": track,
            "entity_class_tags": [kind],
            "failure_opportunity_tags": pl["classes"],
            "split": item["split"],
            "provenance": {
                "carrier_corpus": c["prov"].get("corpus"),
                "license": c["prov"].get("license"),
                "url": c["prov"].get("url"),
                "ref": c["prov"].get("ref"),
                "carrier_item_id": c.get("item_id"),
                "carrier_item": c["prov"].get("source_key", c["source"][:48]),
                "cldr_version": o.CLDR_VERSION, "babel_version": o.BABEL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "annotation_status": "oracle_validated",
            },
        })
    return recs


# --- splits (mirror D1 assign_splits) ----------------------------------------

def assign_splits(items: list[dict]) -> None:
    import random
    groups: dict[frozenset, list[dict]] = defaultdict(list)
    for it in items:
        groups[frozenset([it["track"], it["kind"], *it["fail_tags"]])].append(it)
    rng = random.Random(SEED ^ 0xD2)
    for sig, members in sorted(groups.items(), key=lambda kv: sorted(kv[0])):
        members.sort(key=lambda x: x["item_id"])
        rng.shuffle(members)
        n = len(members)
        n_dev = max(1, round(n * SPLITS["dev"])) if n >= 3 else (1 if n else 0)
        n_hidden = round(n * SPLITS["hidden"])
        for i, it in enumerate(members):
            it["split"] = ("dev" if i < n_dev
                           else "hidden" if i < n_dev + n_hidden else "test")


# --- emission -----------------------------------------------------------------

INPUT_FIELDS = ["item_id", "source_lang", "source_locale", "target_lang",
                "target_locale", "source", "track", "entity_class_tags",
                "failure_opportunity_tags", "split", "provenance"]


def _entity_input(rec: dict) -> list[dict]:
    """Strip reference fields (raw_target / accepted_variants / unacceptable)
    from entities for the gated test/hidden inputs."""
    keep = ("id", "kind", "raw_source", "semantic", "conversion_required")
    return [{k: e[k] for k in keep} for e in rec["entities"]]


def emit(items: list[dict]) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    PRIV.mkdir(exist_ok=True)
    fh = {
        "dev": open(DATA / "dev.jsonl", "w", encoding="utf-8"),
        "ti": open(DATA / "test.input.jsonl", "w", encoding="utf-8"),
        "tg": open(DATA / "test.ref.jsonl", "w", encoding="utf-8"),
        "hi": open(PRIV / "hidden.input.jsonl", "w", encoding="utf-8"),
        "hg": open(PRIV / "hidden.ref.jsonl", "w", encoding="utf-8"),
    }
    n = Counter()
    for it in sorted(items, key=lambda x: x["item_id"]):
        for rec in make_records(it):
            line = json.dumps(rec, ensure_ascii=False) + "\n"
            inp = dict(rec)
            inp.pop("reference"); inp["entities"] = _entity_input(rec)
            iline = json.dumps({**{k: rec[k] for k in INPUT_FIELDS},
                                "entities": inp["entities"]},
                               ensure_ascii=False) + "\n"
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


def main() -> None:
    carriers = load_carriers()
    print("carriers (9-locale, from D1 core):", len(carriers))

    # build items per (kind, track) spec, cycling carriers
    items: list[dict] = []
    for kind, track, quota in ITEM_SPECS:
        for i in range(quota):
            carrier = carriers[i % len(carriers)]
            items.append(make_item(carrier, kind, i, track))
    # content-final stable ids
    for i, it in enumerate(sorted(items, key=lambda x: (
            x["track"], x["kind"], x["carrier"]["source"], id(x)))):
        it["item_id"] = "d2-%06d" % i

    assign_splits(items)
    split_records = emit(items)

    # --- reporting / manifest -------------------------------------------------
    # Resolution floor is on RECORDS per reported class in the K1 scored set
    # (dev+test), since K1 keys per-class pass lists on failure_opportunity_tags
    # over those splits. Also report the locales where each class is applicable
    # (wrong_unit_format is locale-conditional: only locales that localize the
    # unit symbol carry it).
    K1_SPLITS = {"dev", "test"}

    def class_records(split_filter=None) -> Counter:
        cnt: Counter = Counter()
        for it in items:
            if split_filter is not None and it["split"] not in split_filter:
                continue
            for lang in o.TARGET_LANGS:
                for c in it["per_lang"][lang]["classes"]:
                    cnt[c] += 1
        return cnt

    def class_locales() -> dict:
        loc: dict[str, set] = defaultdict(set)
        for it in items:
            for lang in o.TARGET_LANGS:
                for c in it["per_lang"][lang]["classes"]:
                    loc[c].add(lang)
        return {c: sorted(loc[c]) for c in o.ALL_CLASSES}

    rec_k1 = class_records(K1_SPLITS)
    rec_test = class_records({"test"})
    applicable = class_locales()
    kind_counts = Counter(it["kind"] for it in items)
    track_counts = Counter(it["track"] for it in items)
    split_sources = Counter(it["split"] for it in items)

    def quota_block(classes):
        return {c: {"records_k1": rec_k1.get(c, 0), "records_test": rec_test.get(c, 0),
                    "applicable_locales": applicable.get(c, []),
                    "status": "PASS" if rec_k1.get(c, 0) >= PER_CLASS_FLOOR else "FAIL"}
                for c in classes}

    fmt_q = quota_block(o.FORMAT_CLASSES)
    manifest = {
        "name": "prompsit-d2-locale-data-integrity",
        "version": VERSION, "schema_version": SCHEMA_VERSION, "seed": SEED,
        "correctness_logic": "adapt to target locale; the value itself must not change",
        "tracks": {
            "format": "headline: deterministic CLDR formatting (number/currency/"
                      "date separators + unit symbol localization); value unchanged",
        },
        "source_locale": o.SOURCE_LOCALE,
        "locales": {"source": o.SOURCE_LOCALE,
                    "targets": [o.LOCALES[l] for l in o.TARGET_LANGS]},
        "oracle": {"library": "babel", "babel_version": o.BABEL_VERSION,
                   "cldr_version": o.CLDR_VERSION},
        "sources": len(items),
        "records": sum(split_records.values()),
        "splits_records": split_records,
        "splits_sources": dict(split_sources),
        "entity_kind_sources": dict(kind_counts),
        "track_sources": dict(track_counts),
        "per_class_floor": PER_CLASS_FLOOR,
        "format_track": {"classes": o.FORMAT_CLASSES, "quota": fmt_q,
                         "headline": True},
        "quota_status": {c: fmt_q[c]["status"] for c in o.FORMAT_CLASSES},
        "carrier_source": "D1 human translations; license inherited per record",
        "annotation_status": "oracle_validated",
    }
    (PKG / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in
                      ("sources", "records", "splits_records", "entity_kind_sources",
                       "track_sources", "format_track")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
