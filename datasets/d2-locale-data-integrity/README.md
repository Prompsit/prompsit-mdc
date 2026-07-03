# prompsit-d2-locale-data-integrity v1.0

D2 dataset (locale-data integrity): numeric, temporal,
measure and currency values that must adapt to the target locale (CLDR).
en-US -> 9 target locales (es-ES, fr-FR, pt-PT, it-IT, ca-ES, de-DE, nl-NL,
pl-PL, ru-RU). 680 sources / 6,120 records (single headline format track).

See `DATASHEET.md` (the per-dataset single source of truth) for composition,
licensing, method, the taxonomy and limitations.
`private/` (hidden split) must never be published. Build pipeline in `build/`
(deterministic; CLDR oracle via Babel). Open-layer archive + `checksums.sha256`
are produced by `build/make_release.py`.

Reference labels are derived deterministically from the source by an oracle
(here, CLDR via Babel), not human task-annotation. This is an evaluation
benchmark: no training data is provided, and the dev split is an open set for
few-shot/tuning, not required.

Both validation checks pass: the discrimination check (K1) confirms a
locale-blind baseline scores worse than a locale-aware system, and the
false-positive check (K2) shows the automated validators do not wrongly flag
correct human references (0.0%). Croissant 1.0 validated.
