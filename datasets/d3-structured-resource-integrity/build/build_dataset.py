#!/usr/bin/env python3
"""Build the D3 v1.0 (Structured-resource integrity) package - deterministic.

Real source: AOSP Settings string resources (Apache-2.0), 9 target languages with
identical keys (downloaded to sources/ by fetch_sources.sh). Pipeline:
  1. parse the 9-language resource set; keep keys aligned across all langs;
     classify translatable (en differs) vs non-translatable (en == every lang);
  2. group keys into small resource FRAGMENTS (3 translatable + 1 non-translatable)
     and serialize each into a format profile (xml / json / properties / arb);
  3. source = EN serialization, reference = target serialization (real human
     values); attach the failure classes scoreable on the fragment;
  4. dev/test/hidden split (10/70/20), partitioned by item_id;
  5. emit dev/test/hidden + manifest.json.

Deterministic, seeded. ASCII-only.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import resources as R  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
SRC = PKG / "sources"
DATA = PKG / "data"
PRIV = PKG / "private"

SCHEMA_VERSION = "0.2"
VERSION = "1.0"
SEED = 7967358486219981801
SPLITS = {"dev": 0.10, "test": 0.70, "hidden": 0.20}
FLOOR = 400  # records per reported class in the K1 scored set (dev+test)
# XML carries the explicit DNT marker, so it hosts BOTH nonvalue tiers (~half its
# fragments use a marked/alphabetic nontrans key, half a literal one); the
# marker-less profiles host only the Tier-1 literal class.
FORMAT_QUOTA = {"xml": 120, "json": 100, "properties": 100, "arb": 100}
FRAG_TRANSL = 3   # translatable keys per fragment
PROVENANCE = {"corpus": "aosp_settings", "license": "Apache-2.0",
              "url": "https://github.com/aosp-mirror/platform_packages_apps_Settings",
              "ref": "7c598253ff60"}


def _unescape(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    # decode \uXXXX escapes (AOSP uses them, e.g. …) before collapsing the
    # remaining backslash escapes, so the EN skeleton holds real characters.
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    return (s.replace("\\'", "'").replace('\\"', '"')
            .replace("\\n", " ").replace("\\\\", "\\")).strip()


def load_lang(lang: str) -> dict:
    out = {}
    root = ET.parse(SRC / ("strings.%s.xml" % lang)).getroot()
    for s in root.findall("string"):
        k = s.get("name")
        if not k or s.get("translatable") == "false":
            continue
        txt = "".join(s.itertext())
        if not txt:
            continue
        v = _unescape(txt)
        if v and "\n" not in v and not v.startswith("@"):
            out[k] = v
    return out


def harvest():
    langs = [R.SOURCE_LANG] + R.LANGS
    M = {l: load_lang(l) for l in langs}
    keys = set(M["en"])
    for l in langs:
        keys &= set(M[l])
    transl, nontrans = [], []
    for k in sorted(keys):
        en = M["en"][k]
        if not (3 <= len(en) <= 100):
            continue
        diffs = sum(1 for l in R.LANGS if M[l][k] != en)
        if diffs >= 6:
            transl.append(k)
        elif diffs == 0:
            nontrans.append(k)
    return M, transl, nontrans


def make_record(M, item_id, fmt, frag_transl, nontrans_key, lang):
    keys = frag_transl + [nontrans_key]
    nt = [nontrans_key]
    entries_src = [(k, M["en"][k]) for k in keys]
    entries_tgt = [(k, M[lang][k]) for k in keys]
    src_kv = {k: M["en"][k] for k in keys}
    rec = {
        "item_id": item_id, "source_lang": "en", "target_lang": lang,
        "format": fmt,
        # XML serializes translatable="false" on the nontrans key (the explicit,
        # observable DNT marker the system reads); other profiles have no native
        # marker.
        "source": R.serialize(fmt, entries_src, "en", nt),
        "reference": R.serialize(fmt, entries_tgt, lang, nt),
        "src_keyvals": src_kv,
        "translatable_keys": frag_transl,
        "nontrans_keys": nt,
        "nontrans_tier": R.classify_nontrans(M["en"][nontrans_key]),
        "resource_schema": {"key_count": len(keys), "keys": keys},
    }
    return rec


def main():
    M, transl, nontrans = harvest()
    print("aligned keys: transl=%d nontrans=%d" % (len(transl), len(nontrans)))
    assert nontrans, "need >=1 non-translatable key"

    # split the non-translatable pool by tier
    lit_nt = [k for k in nontrans if R.classify_nontrans(M["en"][k]) == "literal"]
    marked_nt = [k for k in nontrans if R.classify_nontrans(M["en"][k]) == "marked"]
    assert lit_nt and marked_nt, "need both literal and marked non-translatable keys"

    # build fragment specs (deterministic): consume translatable keys in order,
    # cycle the non-translatable keys per format. XML alternates marked/literal so
    # both nonvalue tiers clear their floor; marker-less profiles use literal keys
    # only (un-marked alphabetic is not scoreable there, so a marked key would
    # waste the fragment's nonvalue coverage).
    specs = []
    ti = 0
    fmt_list = [f for f, q in FORMAT_QUOTA.items() for _ in range(q)]
    lci = mci = 0
    for i, fmt in enumerate(fmt_list):
        frag = transl[ti:ti + FRAG_TRANSL]
        ti += FRAG_TRANSL
        if len(frag) < FRAG_TRANSL:
            break
        if fmt == "xml" and i % 2 == 0:
            nt = marked_nt[mci % len(marked_nt)]; mci += 1
        else:
            nt = lit_nt[lci % len(lit_nt)]; lci += 1
        specs.append((fmt, frag, nt))

    items = []
    for i, (fmt, frag, nt) in enumerate(specs):
        iid = "d3-%06d" % i
        recs = [make_record(M, iid, fmt, frag, nt, l) for l in R.LANGS]
        # scoreable classes per locale (value_untranslated is locale-specific)
        for r in recs:
            r["failure_opportunity_tags"] = R.scoreable_classes(r, r["reference"])
        classes = sorted({c for r in recs for c in r["failure_opportunity_tags"]})
        for r in recs:
            r["format_profile_tags"] = [fmt]
            r["expected_invariants"] = ["parser_valid", "key_path_preserved",
                                        "schema_preserved", "value_only_translated"]
            r["provenance"] = {**PROVENANCE, "schema_version": SCHEMA_VERSION,
                               "annotation_status": "oracle_validated"}
        items.append({"iid": iid, "fmt": fmt, "classes": classes, "recs": recs})

    assign_splits(items)
    split_records = emit(items)

    # per-class floor on RECORDS in the K1 scored set (dev+test), with the
    # locales/formats where each class is applicable (nonvalue_modified_marked is
    # XML-only: it needs the explicit DNT marker).
    k1_split = {"dev", "test"}
    rec_k1 = Counter()
    rec_test = Counter()
    fmt_by_class = defaultdict(set)
    for it in items:
        for r in it["recs"]:
            for c in r["failure_opportunity_tags"]:
                fmt_by_class[c].add(r["format"])
                if r["split"] in k1_split:
                    rec_k1[c] += 1
                if r["split"] == "test":
                    rec_test[c] += 1
    quota = {c: {"records_k1": rec_k1.get(c, 0), "records_test": rec_test.get(c, 0),
                 "formats": sorted(fmt_by_class.get(c, [])),
                 "status": "PASS" if rec_k1.get(c, 0) >= FLOOR else "FAIL"}
             for c in R.ALL_CLASSES}
    fmt_counts = Counter(it["fmt"] for it in items)
    manifest = {
        "name": "prompsit-d3-structured-resource-integrity",
        "version": VERSION, "schema_version": SCHEMA_VERSION, "seed": SEED,
        "correctness_logic": "preserve the skeleton, translate only content",
        "languages": {"source": "en", "targets": R.LANGS},
        "format_profiles": list(FORMAT_QUOTA),
        "dnt_contract": {
            "literal_tier": "letterless symbol / number / ratio / placeholder -- "
                            "auto-skip, gated for every format, no signal required",
            "marked_tier": "any alphabetic token (acronyms AND brands / proper "
                           "nouns) -- gated ONLY where an explicit DNT marker is "
                           "observable (XML translatable=\"false\"); un-marked "
                           "passthrough is not penalized",
        },
        "sources": len(items), "records": sum(split_records.values()),
        "splits_records": split_records,
        "splits_sources": dict(Counter(it["recs"][0]["split"] for it in items)),
        "format_profile_sources": dict(fmt_counts),
        "classes": R.ALL_CLASSES,
        "per_class_floor": FLOOR,
        "quota": quota,
        "quota_status": {c: quota[c]["status"] for c in R.ALL_CLASSES},
        "source_data": PROVENANCE,
        "annotation_status": "oracle_validated",
    }
    (PKG / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in
                      ("sources", "records", "splits_records", "format_profile_sources",
                       "quota_status")}, indent=2))
    print(json.dumps({c: quota[c] for c in R.ALL_CLASSES}, indent=2))


def assign_splits(items):
    import random
    groups = defaultdict(list)
    for it in items:
        groups[frozenset([it["fmt"], *it["classes"]])].append(it)
    rng = random.Random(SEED ^ 0xD3)
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


INPUT_DROP = ("reference",)


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
            inp = {k: v for k, v in rec.items() if k not in INPUT_DROP}
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
