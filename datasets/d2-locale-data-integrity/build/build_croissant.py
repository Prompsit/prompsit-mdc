#!/usr/bin/env python3
"""Build + validate Croissant 1.0 metadata for the D2 open layer.

Open layer = dev.jsonl (full references) + test.input.jsonl (inputs only) +
contrastive.dev.jsonl. Computes sha256 inline, writes croissant.json, validates
with mlcroissant, and runs a dev record-load smoke test. ASCII-only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
DATA = PKG / "data"


def sha_of(rel: str) -> str:
    p = PKG / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


FIELDS = [
    ("item_id", "sc:Text", "item_id", "Stable item id; shared by all 9 locale rows."),
    ("source_locale", "sc:Text", "source_locale", "Source locale (en-US)."),
    ("target_locale", "sc:Text", "target_locale", "Target locale (es-ES, fr-FR, ...)."),
    ("source", "sc:Text", "source", "EN carrier sentence; entity in the [...] slot, en-US form."),
    ("reference", "sc:Text", "reference", "Carrier translation; entity localized (dev only)."),
    ("split", "sc:Text", "split", "dev / test / hidden."),
]

CTX = {
    "@language": "en", "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs", "column": "cr:column", "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/", "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"}, "dct": "http://purl.org/dc/terms/",
    "examples": {"@id": "cr:examples", "@type": "@json"}, "extract": "cr:extract",
    "field": "cr:field", "fileObject": "cr:fileObject", "fileProperty": "cr:fileProperty",
    "format": "cr:format", "includes": "cr:includes", "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath", "key": "cr:key", "md5": "cr:md5", "parentField": "cr:parentField",
    "path": "cr:path", "recordSet": "cr:recordSet", "references": "cr:references",
    "regex": "cr:regex", "repeated": "cr:repeated", "replace": "cr:replace",
    "sc": "https://schema.org/", "separator": "cr:separator", "source": "cr:source",
    "subField": "cr:subField", "transform": "cr:transform", "fileSet": "cr:fileSet",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "equivalentProperty": "cr:equivalentProperty", "samplingRate": "cr:samplingRate",
}


def field(rs_id, fid, dtype, jsonpath, desc, file_id):
    return {"@type": "cr:Field", "@id": f"{rs_id}/{fid}", "name": fid,
            "description": desc, "dataType": dtype,
            "source": {"fileObject": {"@id": file_id}, "extract": {"column": jsonpath}}}


def build() -> Path:
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    meta = {
        "@context": CTX, "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": "prompsit-d2-locale-data-integrity",
        "description": (
            "D2 - Locale-data integrity. Numeric, temporal, measure and currency "
            "values that must adapt to the target locale (CLDR), with natural EN "
            "carrier sentences and human-translated carriers from the D1 core. "
            "Source en-US -> 9 target locales (es-ES, fr-FR, pt-PT, it-IT, ca-ES, "
            "de-DE, nl-NL, pl-PL, ru-RU). Open layer = dev (full references) + test "
            "inputs + a validator-verified contrastive pack; references for test and "
            "the hidden split are withheld. Version 1.0 uses oracle-validated machine labels "
            "(oracle_validated); human review is not required."),
        "version": manifest["version"], "datePublished": "2026-06-22",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://mozilladatacollective.com/",
        "citeAs": f"Prompsit D2 - Locale-data Integrity (v{manifest['version']}, 2026).",
        "distribution": [
            {"@type": "cr:FileObject", "@id": "dev.jsonl", "name": "dev.jsonl",
             "description": "Open dev split: records with references.",
             "contentUrl": "data/dev.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("data/dev.jsonl")},
            {"@type": "cr:FileObject", "@id": "test.input.jsonl", "name": "test.input.jsonl",
             "description": "Test split: inputs only (references withheld).",
             "contentUrl": "data/test.input.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("data/test.input.jsonl")},
            {"@type": "cr:FileObject", "@id": "contrastive.dev.jsonl", "name": "contrastive.dev.jsonl",
             "description": "Validator-verified contrastive minimal pairs (dev).",
             "contentUrl": "data/contrastive.dev.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("data/contrastive.dev.jsonl")},
        ],
        "recordSet": [
            {"@type": "cr:RecordSet", "@id": "dev", "name": "dev",
             "description": "Dev records (one per source x target locale).",
             "field": [field("dev", *f, "dev.jsonl") for f in FIELDS]},
            {"@type": "cr:RecordSet", "@id": "test_inputs", "name": "test_inputs",
             "description": "Test inputs (no reference).",
             "field": [field("test_inputs", *f, "test.input.jsonl")
                       for f in FIELDS if f[0] != "reference"]},
        ],
    }
    out = PKG / "croissant.json"
    out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def validate(path: Path) -> bool:
    import mlcroissant as mlc
    ds = mlc.Dataset(jsonld=str(path))
    print("Croissant: loaded OK, conformsTo 1.0")
    rs = next(r for r in ds.metadata.record_sets if r.id == "dev")
    n = 0
    for _ in ds.records(record_set=rs.id):
        n += 1
        if n >= 3:
            break
    print(f"Croissant: dev record-load smoke test read {n} records")
    return True


if __name__ == "__main__":
    p = build()
    print("wrote", p)
    sys.exit(0 if validate(p) else 1)
