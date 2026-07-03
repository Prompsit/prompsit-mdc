#!/usr/bin/env python3
"""Package the OPEN layer + write checksums (reproducibility / MDC upload).

Open layer = dev.jsonl (full references) + test.input.jsonl (references withheld) +
contrastive.dev.jsonl + manifest.json + croissant.json + DATASHEET.md +
README.md + THIRD_PARTY_NOTICES.md. The hidden split (private/) and the test
references are NEVER packaged. Output:
  - open-v<version>.tar.gz   (referenced by dataset.yaml; git-ignored)
  - checksums.sha256         (over the published files)
Deterministic; run after validate.py. ASCII-only.
"""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
OPEN_FILES = ["data/dev.jsonl", "data/test.input.jsonl", "data/contrastive.dev.jsonl",
              "manifest.json", "croissant.json", "DATASHEET.md", "README.md",
              "THIRD_PARTY_NOTICES.md"]


def _lf_bytes(path: Path) -> bytes:
    """File bytes with CRLF normalized to LF, so checksums + the open archive
    match the canonical LF git blobs (.gitattributes eol=lf) on every OS, even
    when the build wrote the file via Windows text-mode (CRLF)."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def main():
    man = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    version = man["version"]
    present = [f for f in OPEN_FILES if (PKG / f).exists()]

    lines = []
    for rel in sorted(present):
        h = hashlib.sha256(_lf_bytes(PKG / rel)).hexdigest()
        lines.append("%s  %s" % (h, rel))
    (PKG / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    archive = PKG / ("open-v%s.tar.gz" % version)
    with tarfile.open(archive, "w:gz", compresslevel=9) as tar:
        for rel in sorted(present):
            info = tar.gettarinfo(str(PKG / rel), arcname=rel)
            info.mtime = 1750000000
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            data = _lf_bytes(PKG / rel)
            info.size = len(data)  # LF bytes may be shorter than the on-disk file
            tar.addfile(info, io.BytesIO(data))
    size_kb = archive.stat().st_size / 1024
    print(json.dumps({"archive": archive.name, "size_kb": round(size_kb, 1),
                      "files": present, "checksums": "checksums.sha256"}, indent=2))


if __name__ == "__main__":
    main()
