# prompsit-d4-document-structure-integrity v1.0

D4 dataset (document-structure integrity): the document
tree (headings, blocks, list, table, links/images) must be preserved and
round-trip while only text is translated. HTML profile. EN -> 9 languages. 160 documents /
1,440 records.

Text is human translations (shared with the D1 inline-asset dataset); the
structure is templated. Reference labels are derived deterministically from the
source by an oracle (HTML tree plus round-trip parsers), not human
task-annotation. See `DATASHEET.md` (the per-dataset single source of truth) for
composition, method and limitations. `private/` (hidden split) must never be
published. Open-layer archive + `checksums.sha256` via `build/make_release.py`.

Discrimination check (K1) PASS; false-positive check (K2) PASS (0.0% false
positives); Croissant 1.0 validated.
