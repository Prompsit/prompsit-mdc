# D1 - Inline Asset Integrity (datasheet)

**Version** 1.0 | **Schema** 0.1 | **Scoring rule:** every inline asset in the source must appear in the translation byte-for-byte intact

English UI strings carry inline localization assets: XLIFF and HTML markup,
printf and brace placeholders, template variables, inline ICU MessageFormat,
inline Markdown, and do-not-translate spans. This dataset tests whether machine
translation keeps those assets intact instead of dropping or corrupting them. Each source string is paired with human translations into nine
languages, drawn from permissively licensed, key-aligned localization catalogs.

The translations are human, drawn from real localization catalogs. The
labels on them (asset inventories, positions, expected forms) are derived
automatically and deterministically from the source, so they are reproducible
end to end; the false-positive check below verifies they never flag a correct
human translation.

## How to use this dataset

1. Download the open layer from this page and unpack it: `data/dev.jsonl`
   (inputs plus reference translations), `data/test.input.jsonl` (inputs
   only), `data/contrastive.dev.jsonl`.
2. Translate the source strings with the MT system you want to evaluate - any
   system works; no special integration is required.
3. Score the outputs with the open-source scoring script - `score_item(...)`
   in https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d1-inline-asset-integrity/build
   (`validators.py`).

To verify your harness first, score the dev references themselves: they must
pass 100%.

## Task and scoring

The task: translate each UI string from English into the target language while
keeping every inline asset structurally intact.

Scoring is fully automatic; no human judges are involved. For every record, a
deterministic scoring script (open-source:
https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d1-inline-asset-integrity/build) inspects the
system output and reports which error categories occur (see the Error categories
table below). A record **passes** if no error category occurs. The score of a
system is its **pass rate**: the fraction of records that pass, reported overall
and per error category. The checks compare the assets in the output against the
source string, so no reference translation of the output is needed.

The scoring entry point is `score_item(...)` in `validators.py` there; the `README` and `AGENTS.md` at the repository root
walk through scoring your own outputs.

The seven automated checks are: asset `inventory`, `placeholder_syntax`,
`nesting`, `icu_syntax`, `order`, `attributes`, and `verbatim` (for
do-not-translate spans).

## MDC technical summary

- Domain: software localization and machine-translation quality evaluation for
  UI and resource strings with inline assets.
- Size: 5,391 records; the open archive contains the dev split (with
  references), the test inputs, the contrastive pairs, README, this datasheet,
  third-party notices, manifest, and Croissant metadata.
- Structure: JSONL records with source and target text, target language, asset
  inventory, asset positions (`ref_tag_positions`, located by verbatim search),
  expected invariants, error-category tags, split, and provenance.
- License: CC-BY-4.0 open layer; upstream attributions in
  `THIRD_PARTY_NOTICES.md`.
- Dataset on MDC (download the open layer): https://mozilladatacollective.com/datasets/cmr0mng9z01bsmk07cuqltz81

## Independent evaluation

The test references and the hidden split are withheld, so a score on those
splits reflects performance on unseen inputs rather than answers a system could
have memorised. For an independent evaluation of an MT or LLM system on the
withheld splits, contact Prompsit at info@prompsit.com.

## Contents and splits

| Split | File | Records | What it contains |
|---|---|---|---|
| Open dev | `data/dev.jsonl` | 639 | inputs plus the reference translation and labels |
| Test inputs | `data/test.input.jsonl` | 3,717 | inputs only; references withheld |
| Test references | `data/test.ref.jsonl` | 3,717 | withheld, retained by Prompsit |
| Hidden | - | 1,035 | never distributed |
| Contrastive | `data/contrastive.dev.jsonl` | 1,279 | (correct, damaged) minimal pairs from the dev split, each pair separated by the scoring script |

599 sources x 9 languages = **5,391 records**. Split ~10% dev / 70% test / 20%
hidden (sources: 71 / 413 / 115), stratified by asset-class profile and
partitioned by `item_id`, so a source and its nine translations never cross
splits.

No training set is shipped. The dev split is a small labelled set for optional
few-shot prompting or sanity checks; it is not required to run the benchmark.

## Languages

`en` into `ca, es, fr, it, pt-PT, de, nl, pl, ru`. Every source is present in
all nine languages with the same asset-class profile, so per-language scores are
directly comparable.

## Error categories

Every record is tagged with the error categories it can expose; the scoring
script detects each category with a dedicated automated check. The scoring
script does not assign per-category severity: a record that triggers any
category fails.

| Error category | What it means | Records |
|---|---|---|
| `missing_asset` | an inline asset from the source is absent from the output | 4,356 |
| `extra_asset` | the output contains an asset the source does not have | 4,356 |
| `corrupted_syntax` | an asset survives but its markup or placeholder syntax is damaged | 4,356 |
| `invalid_nesting` | paired tags overlap or close in the wrong order | 2,772 |
| `moved_paired_tag` | a paired tag moved so it no longer wraps the content it wrapped in the source | 2,772 |
| `wrong_order` | assets appear in an order that breaks a required ordering (for example positional placeholders) | 2,565 |
| `lost_attribute` | a tag survives but loses an attribute it had in the source (href, id, ...) | 2,304 |
| `broken_icu` | an ICU MessageFormat structure is damaged (missing branch, broken braces) | 1,467 |
| `dnt_violation` | a do-not-translate span was translated or altered | 1,260 |

At least 400 records per error category (our minimum for a reliable
per-category estimate). Seven asset classes are covered, each with at least 400
records in the scored set: `xliff` (1,548), `software_placeholder` (1,503),
`icu_messageformat` (1,467), `markdown_inline` (1,431), `template_variable`
(1,350), `html_tag` (1,323), `do_not_translate` (1,260). The dev split contains
every class.

## Sample records

Real records from the open dev split, truncated for width. Angle brackets in
markup are shown as ⟨ ⟩ because this platform strips raw HTML-like tags; the
data files contain the ordinary characters.

| item_id | target | source text | target text | asset classes | error categories |
|---|---|---|---|---|---|
| d1-001527 | ca | {HOURS, plural, =1 {This device will be saved for 1 hour and you can connect without a code next time...}} | {HOURS,plural, =1{Aquest dispositiu es desarà durant 1 hora i et podràs connectar sense un codi la propera vegada...}} | icu_messageformat | broken_icu |
| d1-000934 | ca | ⟨xliff:g id="app_name" example="Gmail"⟩%1$s⟨/xliff:g⟩ isn't available right now. This is managed by... | ⟨xliff:g id="APP_NAME_0"⟩%1$s⟨/xliff:g⟩ no està disponible en aquests moments. Aquesta opció es gestiona a... | xliff, software_placeholder | missing_asset, corrupted_syntax |
| d1-000048 | ca | FileName: Name of the file, including the path, that you want to test attributes of. If you do not enter a path, ⟨emph⟩SetAttr⟨/emph⟩... | FileName: Nom del fitxer, inclòs el camí, del qual voleu provar els atributs. Si no introduïu un camí, ⟨emph⟩SetAttr⟨/emph⟩... | html_tag, do_not_translate | dnt_violation, invalid_nesting |
| d1-000418 | ca | This ⟨emph⟩Fontwork⟨/emph⟩ dialog is only available for Fontwork in old Writer text documents that were created prior to %PRODUCTNAME... | Aquest diàleg ⟨emph⟩Fontwork⟨/emph⟩ només està disponible per al Fontwork de documents de text del Writer creats amb una versió anterior a %PRODUCTNAME... | html_tag, template_variable | missing_asset, moved_paired_tag |
| d1-000161 | ca | ⟨emph⟩Reference⟨/emph⟩ (list of options) is the position of the cell to be examined... | ⟨emph⟩Referència⟨/emph⟩ (llista d'opcions) és la posició de la cel·la que s'ha d'examinar... | html_tag, markdown_inline | wrong_order, extra_asset |

## Source data and licenses

Key-aligned localization catalogs (msgid / resource name / JSON key); values are
human translations.

| Corpus | License |
|---|---|
| Apache OpenOffice (openoffice-translation) | Apache-2.0 |
| Chromium (generated_resources + ui_strings) | BSD-3-Clause |
| AOSP Settings / frameworks/base | Apache-2.0 |
| DSpace dspace-angular | BSD-3-Clause |
| Flutter Gallery | BSD-3-Clause |
| Godot editor-l10n | MIT |

All upstream licenses are permissive and compatible with a CC-BY-4.0 open layer;
upstream attribution notices accompany the release in `THIRD_PARTY_NOTICES.md`.
Injected HTML/Markdown assets (added to meet the per-class minimum) are flagged
in provenance.

## Construction method

1. **Harvest** key-aligned catalogs; keep only strings translated in EN plus all
   nine targets; deduplicate; drop fuzzy, obsolete and stale entries.
2. **Asset extraction** with deterministic parsers and regular expressions:
   XLIFF placeholders (`xliff:g`), HTML, printf / positional / named
   placeholders, `{{template}}` variables, inline ICU, Markdown, and
   do-not-translate spans (URLs, emails, brand terms verbatim in all
   references).
3. **Plural conversion**: Android `plurals` resources and gettext plurals
   re-serialized as inline ICU `{count, plural, ...}` with the original human
   translations.
4. **Injection** for classes the UI catalogs lack (HTML, Markdown): one tag pair
   around a verbatim anchor identical across the source and all human
   translations.
5. **Splits**: ~10/70/20, stratified by asset-class profile, partitioned by
   `item_id`.

## Dataset-quality checks

Two checks are run on the dataset itself before release. They validate the
benchmark, not any particular MT system.

- **Discrimination check (K1):** can the dataset separate systems that preserve
  inline assets from systems that do not? Contrasting baseline systems are
  scored with the real scoring script, and the damaging baselines must come out
  significantly worse (paired bootstrap, p-value below 0.05 - that is, the gap is too large to be chance).
- **False-positive check (K2):** does the scoring script ever flag a correct
  human translation as an error? The released references and legal variants of
  them are rescored; the target is 0%.

| Check | Result |
|---|---|
| Discrimination (K1) | **PASS** - in a live run of MT engines, a structure-blind baseline is statistically separated from a tag-aware system on 6 of 7 asset classes (7 of 7 in the offline simulation), paired bootstrap p-value below 0.05; inline ICU is the one class not separated in the live run |
| False positives (K2) | **PASS** - 0.0% |
| Reference self-check | 5,391/5,391 - every released reference passes the scoring script |
| Croissant 1.0 | `croissant.json`, mlcroissant-validated |

## Reproducibility

The build is deterministic and seeded; rebuilding produces a bit-identical
package, and `checksums.sha256` (shipped in the archive) verifies a download.
Rebuilding the inputs starts from the reference translations, so the open
layer alone regenerates and verifies the dev split but not the withheld test
and hidden material.

The scoring script and the full build pipeline are open-source at
https://github.com/Prompsit/prompsit-mdc - the dataset content itself is
distributed here on MDC.

## Scope boundaries

- Asset inventories and positions are machine-extracted and checked by the
  scoring script rather than manually double-annotated; all released references
  pass the D1 checks (self-check 5,391/5,391).
- `ref_tag_positions` are located by verbatim search (NFKC plus regex
  word-break); assets whose surface differs in the human translation are omitted
  rather than guessed.
- Injected pairs wrap verbatim anchors only.
- Converted ICU items are re-serializations of plural tables
  (provenance-flagged).

## Related work

This datasheet follows the structure proposed in Datasheets for Datasets
(Gebru et al., https://arxiv.org/abs/1803.09010). The error categories map to
the locale, terminology and markup branches of the MQM error typology
(https://themqm.org/), turned from human
annotation tags into automated checks.

Tag handling in MT has been studied before: Hashimoto et al.
(https://arxiv.org/abs/2006.13425) measured XML tag translation accuracy for
a single format. This dataset packages the problem as an auto-scored
benchmark across seven asset classes (XLIFF, HTML, placeholders, template
variables, ICU, Markdown, do-not-translate spans) with per-category error
reporting.
