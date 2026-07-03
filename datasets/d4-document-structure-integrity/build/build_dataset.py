#!/usr/bin/env python3
"""Build the D4 v1.0 (Document-structure integrity) package - deterministic.

Real content: human-translated sentences from the local D1 core (license
inherited). Each document places 13 real parallel segments into a fixed
structurally-rich HTML template (headings, paragraphs, list, table, link, image).
The TEXT is real; only the structural scaffolding is templated - and the
structure is exactly what D4 scores (round-trip + tree preservation).

Pipeline: load core segments -> compose 9-language documents -> attach failure
classes -> dev/test/hidden split -> emit + manifest. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import documents as D  # noqa: E402

PKG = Path(__file__).resolve().parent.parent
_D1_REFS = PKG.parent / "d1-inline-asset-integrity" / "data"
CORE = [_D1_REFS / "dev.jsonl", _D1_REFS / "test.ref.jsonl"]  # D1 9-language human references
DATA, PRIV = PKG / "data", PKG / "private"

SCHEMA_VERSION = "0.1"
VERSION = "1.0"
SEED = 15626473554817715828
SPLITS = {"dev": 0.10, "test": 0.70, "hidden": 0.20}
FLOOR = 400  # records per reported class in the K1 scored set (dev+test)
N_DOCS = 160
SEGS_PER_DOC = 13
PROVENANCE = {"content_source": "D1 human translations",
              "license": "per-segment (Apache-2.0 / BSD-3-Clause / MIT, inherited)",
              "structure": "templated HTML (headings/list/table/link/image)"}


def load_segments():
    """item_id -> {lang: short sentence}, items present in all 9 langs."""
    by = defaultdict(dict)
    for line in (ln for cf in CORE for ln in open(cf, encoding="utf-8")):
        r = json.loads(line)
        by[r["item_id"]][r["target_lang"]] = r["reference"]
        by[r["item_id"]]["en"] = r["source"]
        by[r["item_id"]]["_item_id"] = r["item_id"]
        by[r["item_id"]]["_provenance"] = r.get("provenance") or {}
    out = []
    for iid, m in by.items():
        if set(m) >= set(["en"] + D.LANGS):
            if all(3 <= len(m[l]) <= 110 and "\n" not in m[l] for l in ["en"] + D.LANGS):
                out.append(m)
    out.sort(key=lambda m: m["en"])
    return out


def source_provenance(segments):
    items = []
    for segment in segments:
        prov = segment.get("_provenance") or {}
        items.append({
            "item_id": segment.get("_item_id"),
            "corpus": prov.get("corpus"),
            "license": prov.get("license"),
            "url": prov.get("url"),
            "ref": prov.get("ref"),
            "source_key": prov.get("source_key"),
        })
    return items


def main():
    segs = load_segments()
    print("usable parallel segments:", len(segs))
    assert len(segs) >= SEGS_PER_DOC

    import random
    rng = random.Random(SEED ^ 0xD15C)
    items = []
    seen = set()  # guarantee N_DOCS DISTINCT source documents (no cross-split leak)
    guard = 0
    while len(items) < N_DOCS:
        guard += 1
        assert guard < 100000, "cannot draw enough distinct documents"
        idx = tuple(rng.sample(range(len(segs)), SEGS_PER_DOC))
        variant = len(items) % 4
        chosen = [segs[k] for k in idx]
        source_items = source_provenance(chosen)
        en_doc = D.build_html([c["en"] for c in chosen], variant=variant)
        if en_doc in seen:
            continue
        seen.add(en_doc)
        sig = D.signature(en_doc)
        iid = "d4-%06d" % len(items)
        recs = []
        for lang in D.LANGS:
            ref = D.build_html([c[lang] for c in chosen], variant=variant)
            recs.append({
                "item_id": iid, "source_lang": "en", "target_lang": lang,
                "profile": "html", "source": en_doc, "reference": ref,
                "source_signature": sig,
                "links": [D.LINK_HREF], "images": [D.IMG_SRC],
                "expected_invariants": ["roundtrip_valid", "tree_preserved",
                                        "block_order_preserved", "table_shape_preserved",
                                        "links_images_preserved", "segment_count_preserved"],
                "structure_profile_tags": ["html"],
                "provenance": {**PROVENANCE, "schema_version": SCHEMA_VERSION,
                                "source_item_ids": [p["item_id"] for p in source_items],
                                "source_provenance": source_items,
                                "annotation_status": "oracle_validated"},
            })
        classes = D.scoreable_classes({"source_signature": sig}, en_doc)
        for r in recs:
            r["failure_opportunity_tags"] = classes
        items.append({"iid": iid, "classes": classes, "recs": recs})

    assign_splits(items)
    split_records = emit(items)

    # per-class floor on RECORDS in the K1 scored set (dev+test)
    k1_split = {"dev", "test"}
    rec_k1, rec_test = Counter(), Counter()
    for it in items:
        for r in it["recs"]:
            if r["split"] in k1_split:
                for c in r["failure_opportunity_tags"]:
                    rec_k1[c] += 1
            if r["split"] == "test":
                for c in r["failure_opportunity_tags"]:
                    rec_test[c] += 1
    quota = {c: {"records_k1": rec_k1.get(c, 0), "records_test": rec_test.get(c, 0),
                 "status": "PASS" if rec_k1.get(c, 0) >= FLOOR else "FAIL"}
             for c in D.ALL_CLASSES}
    manifest = {
        "name": "prompsit-d4-document-structure-integrity",
        "version": VERSION, "schema_version": SCHEMA_VERSION, "seed": SEED,
        "correctness_logic": "preserve the document tree, translate only text",
        "languages": {"source": "en", "targets": D.LANGS},
        "structure_profiles": ["html"],
        "sources": len(items), "records": sum(split_records.values()),
        "splits_records": split_records,
        "splits_sources": dict(Counter(it["recs"][0]["split"] for it in items)),
        "classes": D.ALL_CLASSES,
        "per_class_floor": FLOOR, "quota": quota,
        "quota_status": {c: quota[c]["status"] for c in D.ALL_CLASSES},
        "content_source": PROVENANCE,
        "annotation_status": "oracle_validated",
    }
    (PKG / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in
                      ("sources", "records", "splits_records", "quota",
                       "quota_status")}, indent=2))


def assign_splits(items):
    import random
    groups = defaultdict(list)
    for it in items:
        groups[frozenset(it["classes"])].append(it)
    rng = random.Random(SEED ^ 0xD4)
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
            inp = {k: v for k, v in rec.items() if k != "reference"}
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
