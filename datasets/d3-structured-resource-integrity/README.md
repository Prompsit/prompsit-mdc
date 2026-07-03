# prompsit-d3-structured-resource-integrity v1.0

D3 dataset (structured-resource integrity): the resource
skeleton (keys, schema) must be preserved and only values translated, in four
format profiles (xml / json / properties / arb). EN -> 9 languages
(ca/es/fr/it/pt-PT/de/nl/pl/ru). 420 sources / 3,780 records with a tiered
do-not-translate contract.

Source: AOSP Settings string resources (Apache-2.0), re-downloadable via
`build/fetch_sources.sh`; values are human translations. See `DATASHEET.md` (the
per-dataset single source of truth) for the v1.0 taxonomy, composition and
limitations. `private/` (hidden split) must never be published. Open-layer
archive + `checksums.sha256` via `build/make_release.py`.

Discrimination check (K1) PASS, false-positive check (K2) PASS (0.0% false
positives), Croissant 1.0 validated.
