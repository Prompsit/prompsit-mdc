# prompsit-d5-linguistic-resource-adherence v1.0

D5 dataset (linguistic-resource adherence): a provided
glossary and translation memory (TM) must be respected. Four resource profiles
(glossary / tm_exact / tm_fuzzy / conflict), scored in glossary/tm/conflict/
quality tracks. EN -> 9 languages. 510 sources / 4,590 records.

Resources: CLDR glossary terminology (territories/languages/currencies via Babel,
Unicode license) plus a translation-memory backbone of D1 human translations.
Reference labels are derived deterministically from the source by an oracle
(glossary/TM matching), not human task-annotation. This is an evaluation
benchmark: no training data is provided; the dev split is an open set for few-shot
or tuning, not required. See `DATASHEET.md` (the per-dataset single source of
truth) for the v1.0 track taxonomy, composition, and limitations. `private/`
(hidden split) must never be published. Open-layer archive plus
`checksums.sha256` via `build/make_release.py`.

Discrimination check (K1) passes; false-positive check (K2) passes (0.0% false
positives); Croissant 1.0 validated.
