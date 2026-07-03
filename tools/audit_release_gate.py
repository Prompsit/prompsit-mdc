#!/usr/bin/env python3
"""Publication release gate for the Prompsit MDC datasets.

This script checks cross-file publication invariants that individual dataset
validators do not own: card/manifest/doc consistency, checksum drift, public
archive contents, review-bundle contents, provenance status, and contrastive
signal coverage.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DATASETS = REPO / "datasets"
DOCS = REPO / "docs"
# Docs actually bundled/published (mirrors ROOT_DOCS in make_review_bundle.py)
# plus the repo root README. Internal-only docs (e.g. research notes) are not
# scanned for generic stale-release markers below — they legitimately use
# words like "roadmap" or "future work".
PUBLISHED_DOC_NAMES = {"REVIEW.md", "MDC_Dataset_Registry.md", "Prompsit_MDC_Benchmark_Memo.md"}

OPEN_FILES = {
    "data/dev.jsonl",
    "data/test.input.jsonl",
    "data/contrastive.dev.jsonl",
    "manifest.json",
    "croissant.json",
    "DATASHEET.md",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
}
TARGETS = {"ca", "es", "fr", "it", "pt-PT", "de", "nl", "pl", "ru"}
ANSWER_KEYS = {"reference", "ref_tag_positions", "legal_moves", "ref_term"}
ENTITY_ANSWER_KEYS = {"raw_target", "accepted_variants", "unacceptable"}
MDC_REQUIRED_FIELDS = {
    "name",
    "shortDescription",
    "longDescription",
    "locale",
    "task",
    "format",
    "licenseAbbreviation",
    "restrictions",
    "forbiddenUsage",
    "additionalConditions",
    "pointOfContactFullName",
    "pointOfContactEmail",
    "fundedByFullName",
    "fundedByEmail",
    "legalContactFullName",
    "legalContactEmail",
    "createdByFullName",
    "createdByEmail",
    "intendedUsage",
    "ethicalReviewProcess",
    "showContactInfo",
    "visibility",
    "exclusivityOptOut",
    "agreeToSubmit",
    "file_path",
    "datasheet_path",
}
PLACEHOLDER_CONTACTS = {
    "contact@prompsit.com",
    "legal@prompsit.com",
    "data@prompsit.com",
    "funding@prompsit.com",
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dataset_dirs() -> list[Path]:
    return sorted(p for p in DATASETS.iterdir() if p.is_dir() and (p / "manifest.json").exists())


def version_key(v: str) -> tuple[int, int, int]:
    parts = [int(p) for p in v.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


def audit_dataset(pkg: Path, errors: list[str]) -> None:
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    card = yaml.safe_load((pkg / "dataset.yaml").read_text(encoding="utf-8"))
    name = pkg.name

    refs = (
        load_jsonl(pkg / "data" / "dev.jsonl")
        + load_jsonl(pkg / "data" / "test.ref.jsonl")
        + load_jsonl(pkg / "private" / "hidden.ref.jsonl")
    )
    inputs = load_jsonl(pkg / "data" / "test.input.jsonl") + load_jsonl(
        pkg / "private" / "hidden.input.jsonl"
    )

    by_item_lang: dict[str, set[str]] = defaultdict(set)
    by_item_split: dict[str, set[str]] = defaultdict(set)
    split_records: Counter[str] = Counter()
    split_sources: dict[str, set[str]] = defaultdict(set)
    class_counts: Counter[str] = Counter()
    provenance_status: Counter[str] = Counter()

    for rec in refs:
        item_id = rec["item_id"]
        by_item_lang[item_id].add(rec["target_lang"])
        by_item_split[item_id].add(rec["split"])
        split_records[rec["split"]] += 1
        split_sources[rec["split"]].add(item_id)
        if rec["split"] in {"dev", "test"}:
            class_counts.update(rec.get("failure_opportunity_tags", []))
        prov = rec.get("provenance") or {}
        if "annotation_status" in prov:
            provenance_status[prov["annotation_status"]] += 1

    for rec in inputs:
        leaked = ANSWER_KEYS & set(rec)
        if leaked:
            errors.append(f"{name}: input leaks answer keys {sorted(leaked)} in {rec.get('item_id')}")
        for ent in rec.get("entities", []):
            nested = ENTITY_ANSWER_KEYS & set(ent)
            if nested:
                errors.append(
                    f"{name}: input leaks entity answer keys {sorted(nested)} in {rec.get('item_id')}"
                )
        prov = rec.get("provenance") or {}
        if "annotation_status" in prov:
            provenance_status[prov["annotation_status"]] += 1

    if len(refs) != manifest.get("records"):
        errors.append(f"{name}: manifest records {manifest.get('records')} != references {len(refs)}")
    if len(by_item_lang) != manifest.get("sources"):
        errors.append(f"{name}: manifest sources {manifest.get('sources')} != items {len(by_item_lang)}")
    if dict(split_records) != manifest.get("splits_records"):
        errors.append(f"{name}: splits_records mismatch {dict(split_records)}")
    got_split_sources = {k: len(v) for k, v in split_sources.items()}
    if got_split_sources != manifest.get("splits_sources"):
        errors.append(f"{name}: splits_sources mismatch {got_split_sources}")

    bad_rect = [item for item, langs in by_item_lang.items() if langs != TARGETS]
    if bad_rect:
        errors.append(f"{name}: non-rectangular item count {len(bad_rect)}")
    bad_split = [item for item, splits in by_item_split.items() if len(splits) != 1]
    if bad_split:
        errors.append(f"{name}: item crosses splits count {len(bad_split)}")

    floor = manifest.get("per_class_floor", 0)
    quota_keys = set(manifest.get("quota_status") or manifest.get("classes") or [])
    floor_counts = manifest.get("per_asset_class_records_k1") or class_counts
    below = {cls: floor_counts.get(cls, 0) for cls in quota_keys if floor_counts.get(cls, 0) < floor}
    if below:
        errors.append(f"{name}: classes below floor {floor}: {below}")

    stale_status = {k: v for k, v in provenance_status.items() if k != "oracle_validated"}
    if stale_status:
        errors.append(f"{name}: stale provenance annotation_status {stale_status}")

    expected_archive = f"open-v{manifest['version']}.tar.gz"
    if card.get("file_path") != expected_archive:
        errors.append(f"{name}: dataset.yaml file_path {card.get('file_path')} != {expected_archive}")
    missing_card_fields = sorted(
        field for field in MDC_REQUIRED_FIELDS if card.get(field) in (None, "")
    )
    if missing_card_fields:
        errors.append(f"{name}: dataset.yaml missing MDC fields {missing_card_fields}")
    if card.get("licenseAbbreviation") != "CC_BY_4_0":
        errors.append(f"{name}: dataset.yaml licenseAbbreviation must be CC_BY_4_0")
    if card.get("locale") != "mul":
        errors.append(f"{name}: dataset.yaml locale must be mul for multi-language MT datasets")
    datasheet_path = pkg / str(card.get("datasheet_path", ""))
    if not datasheet_path.exists() or datasheet_path.name != "DATASHEET.md":
        errors.append(f"{name}: dataset.yaml datasheet_path must point to DATASHEET.md")
    if card.get("other"):
        errors.append(f"{name}: dataset.yaml should not carry a short 'other'; upload loads DATASHEET.md")
    forbidden_usage = str(card.get("forbiddenUsage", ""))
    if "Do not use the test inputs for model training" in forbidden_usage:
        errors.append(f"{name}: forbiddenUsage imposes an extra training restriction under CC-BY-4.0")
    if "No additional legal restriction beyond CC-BY-4.0" not in forbidden_usage:
        errors.append(f"{name}: forbiddenUsage must state that it adds no legal restriction beyond CC-BY-4.0")
    if card.get("license") or card.get("licenseUrl"):
        errors.append(f"{name}: use licenseAbbreviation for CC-BY-4.0, not custom license fields")
    if card.get("visibility") != "PUBLIC":
        errors.append(f"{name}: dataset.yaml visibility must be PUBLIC")
    if card.get("showContactInfo") is not True:
        errors.append(f"{name}: dataset.yaml showContactInfo must be true")
    stale_contacts = {
        key: value
        for key, value in card.items()
        if key.endswith("Email") and isinstance(value, str) and value in PLACEHOLDER_CONTACTS
    }
    if stale_contacts:
        errors.append(f"{name}: placeholder contact emails remain {stale_contacts}")

    audit_builder_version(pkg, manifest, errors)
    audit_croissant(pkg, manifest, errors)
    audit_text_files(pkg, errors)
    audit_public_inputs(pkg, errors)
    audit_contrastive(pkg, manifest, errors)
    audit_checksums(pkg, errors)
    audit_open_archive(pkg, expected_archive, errors)


def audit_croissant(pkg: Path, manifest: dict, errors: list[str]) -> None:
    path = pkg / manifest.get("croissant", "croissant.json")
    if not path.exists():
        errors.append(f"{pkg.name}: croissant metadata missing")
        return

    text = path.read_text(encoding="utf-8")
    meta = json.loads(text)
    version = manifest["version"]

    if meta.get("version") != version:
        errors.append(f"{pkg.name}: croissant version {meta.get('version')} != manifest {version}")
    if f"v{version}" not in meta.get("citeAs", ""):
        errors.append(f"{pkg.name}: croissant citeAs does not include v{version}")


def audit_builder_version(pkg: Path, manifest: dict, errors: list[str]) -> None:
    path = pkg / "build" / "build_dataset.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if 'VERSION = "' in text and f'VERSION = "{manifest["version"]}"' not in text:
        errors.append(f"{pkg.name}: build_dataset.py VERSION does not match manifest")
    if re.search(r"Build the D\d+ v0", text) or re.search(r'^VERSION = "0', text, re.M):
        errors.append(f"{pkg.name}: build_dataset.py contains stale release version")


def audit_text_files(pkg: Path, errors: list[str]) -> None:
    for path in [
        pkg / "README.md",
        pkg / "DATASHEET.md",
        pkg / "dataset.yaml",
        pkg / "THIRD_PARTY_NOTICES.md",
    ]:
        if not path.exists():
            errors.append(f"{pkg.name}: required text file missing {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bC-D\d", text):
            errors.append(f"{pkg.name}: internal issue code in {path.relative_to(REPO)}")
    datasheet = pkg / "DATASHEET.md"
    if datasheet.exists() and "## Sample records" not in datasheet.read_text(encoding="utf-8"):
        errors.append(f"{pkg.name}: DATASHEET.md must include sample records")


def audit_public_inputs(pkg: Path, errors: list[str]) -> None:
    for rel in ["data/dev.jsonl", "data/test.input.jsonl", "data/contrastive.dev.jsonl"]:
        path = pkg / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "@gmail.com" in text:
            errors.append(f"{pkg.name}: public data contains non-reserved gmail example in {rel}")
    for rel in ["data/test.input.jsonl", "private/hidden.input.jsonl"]:
        path = pkg / rel
        if not path.exists():
            continue
        for rec in load_jsonl(path):
            if "provenance" not in rec:
                errors.append(f"{pkg.name}: input record lacks provenance in {rel}: {rec.get('item_id')}")
                break


def audit_contrastive(pkg: Path, manifest: dict, errors: list[str]) -> None:
    rows = load_jsonl(pkg / "data" / "contrastive.dev.jsonl")
    if not rows:
        errors.append(f"{pkg.name}: contrastive.dev.jsonl is empty or missing")
        return
    classes = Counter(
        row.get("failure_class") or row.get("error_class") or row.get("kind") for row in rows
    )
    expected = set(manifest.get("quota_status") or manifest.get("classes") or [])
    # D1 contrastive rows use D1 failure classes, while manifest quota_status
    # lists asset classes. D2-D5 use the same class namespace in both places.
    if rows[0].get("failure_class") is not None:
        missing = expected - set(classes)
        if missing:
            errors.append(f"{pkg.name}: contrastive missing classes {sorted(missing)}")
    for row in rows:
        if "validator_rejects_corrupt" in row and not row["validator_rejects_corrupt"]:
            errors.append(f"{pkg.name}: contrastive corrupt accepted in {row.get('item_id')}")
            break
        if "expected_gate" in row and row["expected_gate"] not in row.get("failed_gates", []):
            errors.append(f"{pkg.name}: contrastive expected gate not failed in {row.get('item_id')}")
            break


def audit_checksums(pkg: Path, errors: list[str]) -> None:
    chk = pkg / "checksums.sha256"
    if not chk.exists():
        errors.append(f"{pkg.name}: checksums.sha256 missing")
        return
    for line in chk.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(None, 1)
        rel = rel.strip()
        path = pkg / rel
        if not path.exists():
            errors.append(f"{pkg.name}: checksum target missing {rel}")
            continue
        got = sha256_lf(path)
        if got != expected:
            errors.append(f"{pkg.name}: checksum mismatch {rel}: {expected[:8]} != {got[:8]}")


def audit_open_archive(pkg: Path, archive_name: str, errors: list[str]) -> None:
    archive = pkg / archive_name
    if not archive.exists():
        errors.append(f"{pkg.name}: open archive missing {archive_name}")
        return
    with tarfile.open(archive, "r:gz") as tar:
        names = sorted(m.name for m in tar.getmembers() if m.isfile())
    forbidden = [
        n
        for n in names
        if n.startswith("private/")
        or "hidden" in n
        or n == "data/test.ref.jsonl"
        or "DO-NOT-PUBLISH" in n
    ]
    if forbidden:
        errors.append(f"{pkg.name}: open archive contains forbidden files {forbidden}")
    missing = OPEN_FILES - set(names)
    extra = set(names) - OPEN_FILES
    if missing or extra:
        errors.append(f"{pkg.name}: open archive file set mismatch missing={sorted(missing)} extra={sorted(extra)}")


def audit_docs(errors: list[str]) -> None:
    registry = (DOCS / "MDC_Dataset_Registry.md").read_text(encoding="utf-8")
    review = (DOCS / "REVIEW.md").read_text(encoding="utf-8")

    public_docs = "\n".join(
        [p.read_text(encoding="utf-8") for p in DOCS.glob("*.md") if p.name in PUBLISHED_DOC_NAMES]
        + [(REPO / "README.md").read_text(encoding="utf-8")]
    )
    if re.search(r"\bC-D\d", public_docs):
        errors.append("docs: internal issue code")

    for pkg in dataset_dirs():
        manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
        did = pkg.name.split("-", 1)[0].upper()
        expected_numbers = [
            manifest["version"],
            f"{manifest['sources']:,}".replace(",", " "),
            f"{manifest['records']:,}".replace(",", " "),
        ]
        for value in expected_numbers:
            if value not in registry:
                errors.append(f"registry: {did} missing value {value}")
        if manifest["version"] not in review:
            errors.append(f"review: missing version {manifest['version']} for {did}")

    versions = [
        json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))["version"]
        for pkg in dataset_dirs()
    ]
    max_version = max(versions, key=version_key)
    expected_archive = REPO / f"prompsit-mdc-review-v{max_version}.tar.gz"
    if not expected_archive.exists():
        errors.append(f"review bundle missing {expected_archive.name}")
    else:
        required = {
            f"prompsit-mdc-review-v{max_version}/REVIEW.md",
            f"prompsit-mdc-review-v{max_version}/MDC_Dataset_Registry.md",
            f"prompsit-mdc-review-v{max_version}/Prompsit_MDC_Benchmark_Memo.md",
        }
        with tarfile.open(expected_archive, "r:gz") as tar:
            names = {m.name for m in tar.getmembers() if m.isfile()}
        missing = required - names
        if missing:
            errors.append(f"review bundle missing docs {sorted(missing)}")


def main() -> int:
    errors: list[str] = []
    for pkg in dataset_dirs():
        audit_dataset(pkg, errors)
    audit_docs(errors)

    if errors:
        print("AUDIT: FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("AUDIT: PASS")
    print(json.dumps({"datasets": [p.name for p in dataset_dirs()]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
