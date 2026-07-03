"""Build + validate Croissant 1.0 metadata for the D1 open layer.

Describes the publishable open layer (dev.jsonl with full references +
test.input.jsonl inputs-only + contrastive.dev.jsonl) as a Croissant dataset, writes
croissant.json, validates it with mlcroissant, and runs a record-load smoke
test. Single balanced 9-language set. ASCII-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PKG = Path(__file__).parent.parent
DATA = PKG / "data"


def sha_of(name: str) -> str:
    for line in (PKG / "checksums.sha256").read_text().splitlines():
        h, fn = line.split()
        if fn.split("/")[-1] == name:
            return h
    return ""


FIELDS = [
    ("item_id", "sc:Text", "item_id", "Stable item id; shared by all 9 target rows."),
    ("source_lang", "sc:Text", "source_lang", "Source language (en)."),
    ("target_lang", "sc:Text", "target_lang", "Target language (ca/es/fr/it/pt-PT/de/nl/pl/ru)."),
    ("source", "sc:Text", "source", "English source string with inline assets."),
    ("reference", "sc:Text", "reference", "Human reference translation (dev split only)."),
    ("split", "sc:Text", "split", "dev / test / hidden."),
]


def field(rs_id, fid, dtype, jsonpath, desc, file_id):
    return {
        "@type": "cr:Field",
        "@id": f"{rs_id}/{fid}",
        "name": fid,
        "description": desc,
        "dataType": dtype,
        "source": {"fileObject": {"@id": file_id}, "extract": {"column": jsonpath}},
    }


def build():
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    ctx = {
        "@language": "en",
        "@vocab": "https://schema.org/",
        "citeAs": "cr:citeAs", "column": "cr:column", "conformsTo": "dct:conformsTo",
        "cr": "http://mlcommons.org/croissant/", "data": {"@id": "cr:data", "@type": "@json"},
        "dataType": {"@id": "cr:dataType", "@type": "@vocab"}, "dct": "http://purl.org/dc/terms/",
        "examples": {"@id": "cr:examples", "@type": "@json"}, "extract": "cr:extract",
        "field": "cr:field", "fileObject": "cr:fileObject", "fileProperty": "cr:fileProperty",
        "format": "cr:format", "includes": "cr:includes", "isLiveDataset": "cr:isLiveDataset",
        "jsonPath": "cr:jsonPath", "key": "cr:key", "md5": "cr:md5", "parentField": "cr:parentField",
        "path": "cr:path", "recordSet": "cr:recordSet", "references": "cr:references",
        "regex": "cr:regex", "repeated": "cr:repeated", "replace": "cr:replace", "sc": "https://schema.org/",
        "separator": "cr:separator", "source": "cr:source", "subField": "cr:subField",
        "transform": "cr:transform", "fileSet": "cr:fileSet", "rai": "http://mlcommons.org/croissant/RAI/",
        "equivalentProperty": "cr:equivalentProperty", "samplingRate": "cr:samplingRate",
    }
    meta = {
        "@context": ctx,
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.0",
        "name": "prompsit-d1-inline-asset-integrity",
        "description": ("D1 - Inline asset integrity. EN UI strings with inline assets "
                        "(XLIFF tags, HTML, printf/brace placeholders, template vars, inline ICU "
                        "MessageFormat, Markdown, do-not-translate spans) and human translations "
                        "into ca/es/fr/it/pt-PT/de/nl/pl/ru, from permissively-licensed "
                        "key-aligned localization catalogues. A single balanced 9-language set "
                        f"({manifest['sources']} sources, identical class profile per language). Open layer = dev "
                        "(full references) + test inputs + a validator-verified contrastive pack; "
                        "references for test and the hidden split are withheld. Version 1.0 uses "
                        "oracle-validated machine labels (oracle_validated); human review is not required."),
        "version": manifest["version"],
        "datePublished": "2026-06-22",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "url": "https://mozilladatacollective.com/",
        "citeAs": f"Prompsit D1 - Inline Asset Integrity (v{manifest['version']}, 2026).",
        "distribution": [
            {"@type": "cr:FileObject", "@id": "dev.jsonl", "name": "dev.jsonl",
             "description": "Open dev split: records with references.",
             "contentUrl": "data/dev.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("dev.jsonl")},
            {"@type": "cr:FileObject", "@id": "test.input.jsonl", "name": "test.input.jsonl",
             "description": "Test split: inputs only (references withheld).",
             "contentUrl": "data/test.input.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("test.input.jsonl")},
            {"@type": "cr:FileObject", "@id": "contrastive.dev.jsonl", "name": "contrastive.dev.jsonl",
             "description": "Validator-verified contrastive minimal pairs (dev).",
             "contentUrl": "data/contrastive.dev.jsonl", "encodingFormat": "application/jsonlines",
             "sha256": sha_of("contrastive.dev.jsonl")},
        ],
        "recordSet": [
            {"@type": "cr:RecordSet", "@id": "dev", "name": "dev",
             "description": "Dev records (one per source x target).",
             "field": [field("dev", fid, dt, jp, ds, "dev.jsonl") for fid, dt, jp, ds in FIELDS]},
            {"@type": "cr:RecordSet", "@id": "test_inputs", "name": "test_inputs",
             "description": "Test inputs (no reference).",
             "field": [field("test_inputs", fid, dt, jp, ds, "test.input.jsonl")
                       for fid, dt, jp, ds in FIELDS if fid != "reference"]},
        ],
    }
    out = PKG / "croissant.json"
    out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def validate(path):
    import mlcroissant as mlc
    ds = mlc.Dataset(jsonld=str(path))
    print("Croissant: loaded OK, conformsTo 1.0")
    rs = next(r for r in ds.metadata.record_sets if r.id == "dev")
    n = 0
    for rec in ds.records(record_set=rs.id):
        n += 1
        if n >= 3:
            break
    print(f"Croissant: dev record-load smoke test read {n} records")
    return True


if __name__ == "__main__":
    p = build()
    print("wrote", p)
    ok = validate(p)
    sys.exit(0 if ok else 1)
