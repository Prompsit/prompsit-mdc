#!/usr/bin/env python3
"""Package the D1 OPEN layer + write checksums (reproducibility / MDC upload).

Open layer = dev.jsonl (full references) + test.input.jsonl (inputs only) +
contrastive.dev.jsonl + manifest.json + croissant.json + DATASHEET.md +
README.md + THIRD_PARTY_NOTICES.md. test.ref.jsonl, the hidden split and
private/ are NEVER packaged.
Output:
  - open-v<version>.tar.gz   (referenced by dataset.yaml; git-ignored)
  - checksums.sha256         (LF endings, over the published files)

Pipeline (deterministic; run after validate.py):
  1. write checksums over the data files so build_croissant can read fresh hashes
  2. regenerate croissant.json from those hashes (build_croissant.build)
  3. rewrite checksums over ALL published files (data + metadata)
  4. validate croissant with mlcroissant + record-load smoke test
  5. tar the open layer with a fixed mtime (reproducible bytes)
ASCII-only.
"""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import build_croissant

PKG = Path(__file__).resolve().parent.parent

# Published data files (must match croissant.json distribution).
DATA_FILES = [
    "data/dev.jsonl",
    "data/test.input.jsonl",
    "data/contrastive.dev.jsonl",
]
META_FILES = [
    "manifest.json",
    "croissant.json",
    "DATASHEET.md",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
]


def _lf_bytes(path: Path) -> bytes:
    """Normalize text payloads to LF for reproducible archives on Windows."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def write_checksums(rels):
    present = [r for r in rels if (PKG / r).exists()]
    lines = []
    for rel in sorted(present):
        h = hashlib.sha256(_lf_bytes(PKG / rel)).hexdigest()
        lines.append("%s  %s" % (h, rel))
    # LF endings, trailing newline -> portable `sha256sum -c`
    (PKG / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return present


def main():
    man = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    version = man["version"]

    # 1. data-file checksums (consumed by build_croissant.sha_of)
    write_checksums(DATA_FILES)
    # 2. regenerate croissant.json from fresh hashes
    croissant_path = build_croissant.build()
    # 3. final checksums over the full published set
    present = write_checksums(DATA_FILES + META_FILES)
    # 4. validate croissant + smoke test
    build_croissant.validate(croissant_path)

    # 5. open-layer archive (fixed mtime -> reproducible)
    archive = PKG / ("open-v%s.tar.gz" % version)
    with tarfile.open(archive, "w:gz", compresslevel=9) as tar:
        for rel in sorted(present):
            info = tar.gettarinfo(str(PKG / rel), arcname=rel)
            info.mtime = 1750000000
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            data = _lf_bytes(PKG / rel)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    size_kb = archive.stat().st_size / 1024
    print(json.dumps({"archive": archive.name, "size_kb": round(size_kb, 1),
                      "files": present, "checksums": "checksums.sha256"}, indent=2))


if __name__ == "__main__":
    main()
