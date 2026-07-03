# D3 - Structured-resource Integrity (datasheet)

**Version** 1.0 | **Schema** 0.2 | **Scoring rule:** keys, schema and non-translatable fields must be preserved; only values are translated; the file must still parse

Localization ships as structured resource files. This dataset tests whether
machine translation preserves the skeleton of such a file - its keys, its
schema, and its non-translatable fields - while translating only the values,
and returns output that still parses. Each record is a small resource file in
one of four formats (Android XML, JSON, Java .properties, Flutter ARB) paired
with a human translation into one of nine languages; the values are human
translations from AOSP Settings string resources.

The translations are human, drawn from real localization catalogs. The
labels on them (asset inventories, positions, expected forms) are derived
automatically and deterministically from the source, so they are reproducible
end to end; the false-positive check below verifies they never flag a correct
human translation. Every released
reference passes the scoring script (3,780/3,780). Values that carry inline
tags are the D1 dataset's concern; D3 covers keys, schema and plain values,
with no double-counting.

## How to use this dataset

1. Download the open layer from this page and unpack it: `data/dev.jsonl`
   (inputs plus reference translations), `data/test.input.jsonl` (inputs
   only), `data/contrastive.dev.jsonl`.
2. Translate the source strings with the MT system you want to evaluate - any
   system works; no special integration is required.
3. Score the outputs with the open-source scoring script - `score_item(...)`
   in https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d3-structured-resource-integrity/build
   (`resources.py`).

To verify your harness first, score the dev references themselves: they must
pass 100%.

## Task and scoring

The task: translate each resource file from English into the target language,
changing only the values while keeping keys, schema and non-translatable
fields unchanged, so that the file still parses.

Scoring is fully automatic; no human judges are involved. For every record, a
deterministic scoring script (open-source:
https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d3-structured-resource-integrity/build)
inspects the system output and reports which error categories occur (see the
Error categories table below). A record **passes** if no error category
occurs. The score of a system is its **pass rate**: the fraction of records
that pass, reported overall and per error category. The checks parse the
output resource file and compare its keys, schema and non-translatable fields
against the source, so no reference translation of the output is needed.

The scoring entry point is `score_item(...)` in `resources.py` there; the `README` and `AGENTS.md` at the repository root
walk through scoring your own outputs.

The automated checks are: `parser_valid`, `key_path_match`, `schema_match`,
`value_translated` (reference-aware: a value that legitimately stays identical
in the human reference, such as a proper noun, is not counted as
untranslated), and `nonvalue_preserved` in two tiers (see the Error categories
section).

## MDC technical summary

- Domain: software localization and machine-translation quality evaluation for
  structured resource files (XML, JSON, .properties, ARB).
- Size: 3,780 records; the open archive contains the dev split (with
  references), the test inputs, the contrastive pairs, README, this datasheet,
  third-party notices, manifest, and Croissant metadata.
- Structure: JSONL records with the source resource file and its reference
  translation, format, key/value metadata, non-translatable fields, expected
  invariants, error-category tags, split, and provenance.
- License: CC-BY-4.0 open layer; upstream attributions in
  `THIRD_PARTY_NOTICES.md`.
- Dataset on MDC (download the open layer): https://mozilladatacollective.com/datasets/cmr0mny2b01asns073985z0va

## Independent evaluation

The test references and the hidden split are withheld, so a score on those
splits reflects performance on unseen inputs rather than answers a system could
have memorised. For an independent evaluation of an MT or LLM system on the
withheld splits, contact Prompsit at info@prompsit.com.

## Contents and splits

| Split | File | Records | What it contains |
|---|---|---|---|
| Open dev | `data/dev.jsonl` | 378 | inputs plus the reference translation and labels |
| Test inputs | `data/test.input.jsonl` | 2,646 | inputs only; references withheld |
| Test references | `data/test.ref.jsonl` | 2,646 | withheld, retained by Prompsit |
| Hidden | - | 756 | never distributed |
| Contrastive | `data/contrastive.dev.jsonl` | 1,890 | verification records for (correct, damaged) minimal pairs; the damaged variants are regenerated bit-identically from the dev split by the open build pipeline, and each pair is separated by the scoring script |

420 sources x 9 languages = **3,780 records**. Split ~10% dev / 70% test / 20%
hidden (sources: 42 / 294 / 84), stratified by format and error-category
profile and partitioned by `item_id`, so a source and its nine translations
never cross splits.

No training set is shipped. The dev split is a small labelled set for optional
few-shot prompting or sanity checks; it is not required to run the benchmark.

## Languages

`en` into `ca, es, fr, it, pt-PT, de, nl, pl, ru`. Every source is present in
all nine languages in the same format, so per-language scores are directly
comparable.

## Error categories

Every record is tagged with the error categories it can expose; the scoring
script detects each category with a dedicated automated check. Severity is
reported alongside a failure for error analysis; it does not change the
pass/fail rule.

| Error category | What it means | Severity | Records |
|---|---|---|---|
| `parser_break` | the output no longer parses | Critical | 3,024 |
| `key_path_translated` | a key or path was translated | Major | 3,024 |
| `schema_changed` | the structure or nesting changed | Major | 3,024 |
| `value_untranslated` | a translatable value was left in English | Major | 3,024 |
| `nonvalue_modified_literal` | a non-translatable token - symbols, numbers, ratios, degrees, placeholders, the ARB `@@locale` field - was altered; checked in every format | Major | 2,592 |
| `nonvalue_modified_marked` | an alphabetic token explicitly marked `translatable="false"` was altered; XML only | Major | 432 |

At least 400 records per error category (our minimum for a reliable
per-category estimate); counts are over the scored dev and test records. Four
format profiles are covered: `xml` (native Android), `json`, `properties`, and
`arb` (which carries the non-translatable `@@locale` metadata field).

Non-translatable fields are protected in two tiers. Tier 1 covers tokens with
no letters - symbols, numbers, ratios, degrees, placeholders, and the ARB
`@@locale` field. These can never be legitimately translated, so they are
checked in every format, no marker needed. Tier 2 covers alphabetic tokens
(acronyms, brands, proper nouns), which sometimes are legitimately
translatable; these are checked only in XML, where the source explicitly marks
them with `translatable="false"`. An unmarked alphabetic token that passes
through unchanged in JSON, .properties or ARB is not penalised; no inline
do-not-translate list is shipped, which keeps this dataset separate from the
D5 dataset.

## Sample records

Real records from the open dev split, truncated for width. Angle brackets in
markup are shown as ⟨ ⟩ because this platform strips raw HTML-like tags; the
data files contain the ordinary characters.

| item_id | target | source text | target text | format | error categories |
|---|---|---|---|---|---|
| d3-000001 | ca | ⟨?xml version="1.0" encoding="utf-8"?⟩ ⟨resources⟩ ⟨string name="accessibility_action_label_panel_slice"⟩enter settings⟨/string⟩ ... ⟨string name="external_display_rotation_180" translatable="false"⟩180°⟨/string⟩ ⟨/resources⟩ | ⟨?xml version="1.0" encoding="utf-8"?⟩ ⟨resources⟩ ⟨string name="accessibility_action_label_panel_slice"⟩obre la configuració⟨/string⟩ ... ⟨string name="external_display_rotation_180" translatable="false"⟩180°⟨/string⟩ ⟨/resources⟩ | xml | parser_break, key_path_translated, schema_changed, value_untranslated, nonvalue_modified_literal |
| d3-000124 | ca | { "apn_user": "Username", "app_and_notification_dashboard_summary": "Recent apps, default apps", ... "external_display_rotation_270": "270°" } | { "apn_user": "Nom d'usuari", "app_and_notification_dashboard_summary": "Aplicacions recents, aplicacions predeterminades", ... "external_display_rotation_270": "270°" } | json | parser_break, key_path_translated, schema_changed, value_untranslated, nonvalue_modified_literal |
| d3-000223 | ca | battery_app_usage=App usage since last full charge battery_app_usage_for=App usage for %s ... | battery_app_usage=Ús de l'aplicació des de la darrera càrrega completa battery_app_usage_for=Ús d'aplicacions entre %s ... | properties | parser_break, key_path_translated, schema_changed, value_untranslated, nonvalue_modified_literal |
| d3-000322 | ca | { "@@locale": "en", "bounce_keys_dialog_title": "Bounce key threshold", ... "print_job_summary": "%1$s %2$s" } | { "@@locale": "ca", "bounce_keys_dialog_title": "Llindar de la tecla de rebot", ... "print_job_summary": "%1$s %2$s" } | arb | parser_break, key_path_translated, schema_changed, value_untranslated, nonvalue_modified_literal |

Every record exercises the first five categories; XML records whose
non-translatable token is alphabetic (marked `translatable="false"` in the
source) also exercise `nonvalue_modified_marked`.

## Source data and licenses

| Corpus | License | What |
|---|---|---|
| AOSP Settings string resources (`aosp-mirror/platform_packages_apps_Settings@7c598253ff60`) | Apache-2.0 | EN plus 9-language `strings.xml`, identical keys, human translations |

The pinned upstream files can be re-downloaded with the open build pipeline. Values are human translations from AOSP; the JSON, .properties and
ARB profiles re-serialize the same key-value pairs. The upstream license is
permissive and compatible with a CC-BY-4.0 open layer; the attribution notice
accompanies the release in `THIRD_PARTY_NOTICES.md`.

## Construction method

1. **Harvest**: download the pinned AOSP Settings string resources - English
   plus the nine target languages with identical keys; keep only keys present
   in all ten files.
2. **Classification**: mark each key as translatable (the English value
   differs from the translations) or non-translatable (identical in every
   language); assign non-translatable tokens to Tier 1 (letterless) or Tier 2
   (alphabetic, marked `translatable="false"` in XML).
3. **Fragmenting and serialization**: group keys into small resource fragments
   (three translatable keys plus one non-translatable) and serialize each
   fragment into one of the four format profiles - Android XML, JSON, Java
   .properties, or Flutter ARB (which adds the `@@locale` metadata field).
4. **Pairing**: the source is the English serialization; the reference is the
   target-language serialization of the same fragment with the human values;
   each record is tagged with the error categories it can expose.
5. **Splits**: ~10/70/20, stratified by format and error-category profile,
   partitioned by `item_id`.

## Dataset-quality checks

Two checks are run on the dataset itself before release. They validate the
benchmark, not any particular MT system.

- **Discrimination check (K1):** can the dataset separate systems that preserve
  the resource skeleton from systems that do not? Contrasting baseline systems
  are scored with the real scoring script, and the damaging baselines must come
  out significantly worse (paired bootstrap, p-value below 0.05 - that is, the gap is too large to be chance).
- **False-positive check (K2):** does the scoring script ever flag a correct
  human translation as an error? The released references and legal variants of
  them are rescored; the target is 0%.

| Check | Result |
|---|---|
| Discrimination (K1) | **PASS** - resource-blind baselines (untranslated passthrough, raw copy) score 0% where a resource-aware system scores 100%, separated on 6 of 6 error categories (paired bootstrap p-value below 0.05); single-error baselines are caught on their target category. The baselines are simulated corruption operators scored with the real scoring script. |
| False positives (K2) | **PASS** - 0.0% flips over 10,260 legal variants (key reorder, reindent, comments, blank lines, trailing newline) |
| Reference self-check | 3,780/3,780 - every released reference passes the scoring script |
| Croissant 1.0 | `croissant.json`, mlcroissant-validated |

## Reproducibility

The build is deterministic and seeded; rebuilding produces a bit-identical
package, and `checksums.sha256` (shipped in the archive) verifies a download.
D3 is built from a pinned public upstream (the AOSP revision in the Source
data table), so the open build pipeline can regenerate the dataset in full;
official, comparable scores on the withheld splits are still issued only by
Prompsit (see Independent evaluation).

The scoring script and the full build pipeline are open-source at
https://github.com/Prompsit/prompsit-mdc - the dataset content itself is
distributed here on MDC.

## Scope boundaries

- Reference labels are machine-generated by format parsers and checked by the
  scoring script rather than manually double-annotated; all released
  references pass the D3 checks (self-check 3,780/3,780).
- One source corpus (AOSP Settings); the JSON, .properties and ARB profiles
  re-serialize the AOSP key-value pairs rather than native files of those
  formats.
- Flat resources only; nested-path schemas such as deep JSON or YAML are
  outside this package.
- The baseline results shipped with this package are synthetic
  (deterministically generated corruptions used to exercise the scoring
  script), not outputs of real MT systems.
- Values that carry inline tags are covered by the D1 dataset; adherence to
  supplied glossaries and translation memories by the D5 dataset; D3 covers
  keys, schema and plain values, with no double-counting.

## Related work

This datasheet follows the structure proposed in Datasheets for Datasets
(Gebru et al., https://arxiv.org/abs/1803.09010). The error categories map to
the locale, terminology and markup branches of the MQM error typology
(https://themqm.org/), turned from human
annotation tags into automated checks.

FormatRL (https://arxiv.org/abs/2512.05100) trains and evaluates
format-preserving translation for XML/HTML markup only, and Hashimoto et al.
(https://arxiv.org/abs/2006.13425) measured XML tag accuracy for one format.
This dataset scores key, schema and non-translatable-field preservation
across four resource formats (XML, JSON, .properties, ARB) with a
parse-or-fail check.
