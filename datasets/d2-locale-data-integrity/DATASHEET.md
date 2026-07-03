# D2 - Locale-data Integrity (datasheet)

**Version** 1.0 | **Schema** 0.2 | **Scoring rule:** locale-sensitive values must be rendered in the target-locale convention; the value itself must not change

Translated software and documentation carry locale-sensitive values: numbers,
dates, currency amounts, and physical units. The correct output depends on the
target locale - `1,200,000` in en-US text should read `1.200.000` in ca-ES - so
a translation that copies the source form through is wrong even when every word
is right. This dataset tests whether machine translation renders such values in
the target-locale convention: decimal and grouping separators, date pattern,
currency symbol and position, localized unit symbol. The value itself must not
change - no exchange-rate conversion, no metrication. Each record embeds one
value in a neutral `[...]` slot of a human-translated sentence shared with the
D1 dataset. A markup-preservation check like D1's would wrongly penalise a
correctly localised number, so locale rendering is scored as its own dataset.

The surrounding sentences are human translations shared with the D1 dataset.
The expected target-locale forms and their accepted variants are derived
automatically and deterministically by rendering each value with Unicode CLDR
locale data via Babel (this renderer is the reference oracle), so the labels
are reproducible end to end; the false-positive check below verifies they
never flag a correct human translation.

## How to use this dataset

1. Download the open layer from this page and unpack it: `data/dev.jsonl`
   (inputs plus reference translations), `data/test.input.jsonl` (inputs
   only), `data/contrastive.dev.jsonl`.
2. Translate the source strings with the MT system you want to evaluate - any
   system works; no special integration is required.
3. Score the outputs with the open-source scoring script - `score_item(...)`
   in https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d2-locale-data-integrity/build
   (`validators.py`).

To verify your harness first, score the dev references themselves: they must
pass 100%.

## Task and scoring

The task: translate each sentence from English into the target locale while
rendering the embedded locale-sensitive value in that locale's convention.

Scoring is fully automatic; no human judges are involved. For every record, a
deterministic scoring script (open-source:
https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d2-locale-data-integrity/build) inspects the
system output and reports which error categories occur (see the Error categories
table below). A record **passes** if no error category occurs. The score of a
system is its **pass rate**: the fraction of records that pass, reported overall
and per error category. The checks compare the rendered value in the output
against the target-locale forms derived from Unicode CLDR (Babel) for that
record, so no reference translation of the output is needed.

The scoring entry point is `score_item(...)` in `validators.py` there; the `README` and `AGENTS.md` at the repository root
walk through scoring your own outputs.

Every record in v1.0 is a **format-track** record: the value is rendered as-is
in the target locale, and only the locale form is scored. A conversion track
that does change the value (exchange rates, metrication) is defined in the
record schema as an opt-in extension; v1.0 ships no conversion records, and
`conversion_required` is false in every record. Legal variants - for example
the currency code instead of the symbol, or a long unit form - are listed per
record in `accepted_variants` and are not penalised.

## MDC technical summary

- Domain: software localization and machine-translation quality evaluation for
  locale-specific rendering of numbers, dates, currencies, and units.
- Size: 6,120 records; the open archive contains the dev split (with
  references), the test inputs, the contrastive pairs, README, this datasheet,
  third-party notices, manifest, and Croissant metadata.
- Structure: JSONL records with source and target text, source and target
  locales, entity metadata (kind, semantic value, expected rendering, accepted
  variants), expected invariants, error-category tags, split, and provenance.
- License: CC-BY-4.0 open layer; upstream attributions in
  `THIRD_PARTY_NOTICES.md`.
- Dataset on MDC (download the open layer): https://mozilladatacollective.com/datasets/cmr0mnoo201bwmk07nh4yc04u

## Independent evaluation

The test references and the hidden split are withheld, so a score on those
splits reflects performance on unseen inputs rather than answers a system could
have memorised. For an independent evaluation of an MT or LLM system on the
withheld splits, contact Prompsit at info@prompsit.com.

## Contents and splits

| Split | File | Records | What it contains |
|---|---|---|---|
| Open dev | `data/dev.jsonl` | 630 | inputs plus the reference translation and labels |
| Test inputs | `data/test.input.jsonl` | 4,266 | inputs only; references withheld |
| Test references | `data/test.ref.jsonl` | 4,266 | withheld, retained by Prompsit |
| Hidden | - | 1,224 | never distributed |
| Contrastive | `data/contrastive.dev.jsonl` | 821 | (correct, damaged) minimal pairs from the dev split, each pair separated by the scoring script |

680 sources x 9 locales = **6,120 records**. Split ~10% dev / 70% test / 20%
hidden (sources: 70 / 474 / 136), stratified by error category and partitioned
by `item_id`, so a source and its nine translations never cross splits.

No training set is shipped. The dev split is a small labelled set for optional
few-shot prompting or sanity checks; it is not required to run the benchmark.

## Languages

`en-US` into `ca-ES, es-ES, fr-FR, it-IT, pt-PT, de-DE, nl-NL, pl-PL, ru-RU` -
the same nine-language matrix as the D1 dataset. The dataset is keyed by full
locale rather than language alone, because a language code underspecifies
separators, date patterns, and currency format. Every source is present in all
nine locales with the same embedded value, so per-locale scores are directly
comparable.

## Error categories

Every record is tagged with the error categories it can expose; the scoring
script detects each category with a dedicated automated check. Severity is
reported alongside a failure for error analysis; it does not change the
pass/fail rule.

| Error category | What it means | Severity | Records |
|---|---|---|---|
| `wrong_decimal_separator` | the decimal separator is not the target-locale one (comma vs point) | Major | 2,223 |
| `wrong_grouping` | digit grouping is missing or uses the wrong separator for the target locale | Minor | 1,449 |
| `mis_converted_datetime` | the date is not rendered in the target-locale pattern (for example left in the source form) | Major | 1,152 |
| `broken_currency_format` | the currency symbol, code, or its position does not follow the target-locale pattern | Major | 1,152 |
| `wrong_unit_format` | the unit symbol is not the localized form the target locale uses | Minor | 425 |
| `missing_entity` | the output drops the value entirely | Critical | all |

At least 400 records per error category (our minimum for a reliable
per-category estimate). Record counts are over the scored set (the dev and test
splits). Four entity kinds are covered: number (160 sources), currency (160),
date (160), and unit (200). `missing_entity` can occur on any record, since
every record carries exactly one value. `wrong_unit_format` is scoreable in the
four locales where CLDR prescribes a unit symbol different from the English
form (fr-FR, pl-PL, pt-PT, ru-RU); elsewhere the unchanged symbol is the
correct rendering.

## Sample records

Real records from the open dev split, truncated for width. Angle brackets in
markup are shown as ⟨ ⟩ because this platform strips raw HTML-like tags; the
data files contain the ordinary characters.

| item_id | target | source text | target text | entity (input -> expected) | error categories |
|---|---|---|---|---|---|
| d2-000023 | ca | ⟨ahelp hid="..."⟩Sorts the selection from the lowest value to the highest value. You can define the sort rules...⟨/ahelp⟩ ... [£19,999.90] | ⟨ahelp hid="..."⟩Ordena la selecció del valor més petit al més gran. Podeu definir les regles d'ordenació...⟨/ahelp⟩ ... [19.999,90 £] | currency: `£19,999.90 -> 19.999,90 £` | wrong_decimal_separator, wrong_grouping, broken_currency_format |
| d2-000163 | ca | ⟨item type="input"⟩=OFFSET(A1;2;2)⟨/item⟩ returns the value in cell C3 (A1 moved by two rows and two columns down)... [Jul 1, 2024] | ⟨item type="input"⟩=DESPLAÇAMENT(A1;2;2)⟨/item⟩ retorna el valor de la cel·la C3 (A1 desplaçada dues files i dues columnes cap avall)... [1 de jul. 2024] | date: `Jul 1, 2024 -> 1 de jul. 2024` | mis_converted_datetime |
| d2-000321 | ca | ⟨emph⟩Server⟨/emph⟩ is the name of a server application. ⟨item type="productname"⟩%PRODUCTNAME⟨/item⟩ applications have the server name... [1,200,000] | ⟨emph⟩Servidor⟨/emph⟩ és el nom d'una aplicació de servidor. En el cas de les aplicacions de l'⟨item type="productname"⟩%PRODUCTNAME⟨/item⟩... [1.200.000] | number: `1,200,000 -> 1.200.000` | wrong_decimal_separator, wrong_grouping |
| d2-000489 | ca | ⟨ahelp hid=""⟩Enter or edit general information for an ⟨link ...⟩XML filter⟨/link⟩.⟨/ahelp⟩ [350 lb] | ⟨ahelp hid=""⟩Introduïu o editeu la informació general per a un ⟨link ...⟩filtre XML⟨/link⟩.⟨/ahelp⟩ [350 lb] | unit: `350 lb -> 350 lb` (ca-ES keeps `lb`; `350 lliures` also accepted) | missing_entity only (the ca-ES unit symbol is unchanged) |

## Source data and licenses

The sentences that host the values are human translations shared with the D1
inline-asset dataset, drawn from key-aligned localization catalogs; each
record's `provenance` field names its corpus, license, URL, revision, and the
originating D1 item. The expected target-locale forms come from Unicode CLDR
locale data as bundled with Babel 2.18.0.

| Source | License |
|---|---|
| Apache OpenOffice (openoffice-translation) | Apache-2.0 |
| AOSP Settings / frameworks/base | Apache-2.0 |
| Chromium (generated_resources + ui_strings) | BSD-3-Clause |
| DSpace dspace-angular | BSD-3-Clause |
| Unicode CLDR (via Babel 2.18.0) | Unicode-3.0 |

All upstream licenses are permissive and compatible with a CC-BY-4.0 open layer;
upstream attribution notices accompany the release in `THIRD_PARTY_NOTICES.md`.

## Construction method

1. **Sentence selection**: human-translated segments present in EN plus all
   nine target languages, reused from the D1 harvest with their licenses and
   provenance inherited per record.
2. **Value generation**: 680 items - 160 numbers, 160 currency amounts, 160
   dates, 200 unit measures - with values picked deterministically from fixed
   pools, seeded per item.
3. **Rendering**: the source form is produced for en-US and the expected form
   for each target locale from CLDR data via Babel 2.18.0, together with the
   accepted legal variants and, for each applicable error category, a damaged
   form used to build the contrastive pairs.
4. **Injection**: the value is appended to the sentence in a neutral `[...]`
   slot, in the same position in the source and in every reference.
5. **Splits**: ~10/70/20, stratified by error category, partitioned by
   `item_id`.

## Dataset-quality checks

Two checks are run on the dataset itself before release. They validate the
benchmark, not any particular MT system.

- **Discrimination check (K1):** can the dataset separate systems that render
  locale-sensitive values in the target-locale convention from systems that do
  not? Contrasting baseline systems are scored with the real scoring script,
  and the damaging baselines must come out significantly worse (paired
  bootstrap, p-value below 0.05).
- **False-positive check (K2):** does the scoring script ever flag a correct
  human translation as an error? The released references and legal variants of
  them are rescored; the target is 0%.

| Check | Result |
|---|---|
| Discrimination (K1) | **PASS** - locale-blind passthrough baselines score 16.5% overall where a locale-aware system scores 100%, separated on all 5 error categories that have a corruption operator (paired bootstrap p-value below 0.05); the sixth, missing_entity, fires only when the output drops the value entirely. The baselines are simulated corruption operators scored with the real scoring script. |
| False positives (K2) | **PASS** - 0.0% flips over 20,036 legal variants (NBSP/NNBSP/thin-space grouping, date length, currency code, unit long form) |
| Reference self-check | 6,120/6,120 - every released reference passes the scoring script |
| Croissant 1.0 | `croissant.json`, mlcroissant-validated |

## Reproducibility

The build is deterministic and seeded; rebuilding produces a bit-identical
package, and `checksums.sha256` (shipped in the archive) verifies a download.
The build seed and the locale-data pin (Babel 2.18.0 with
its bundled CLDR) are recorded in `manifest.json`, shipped in the archive.
Rebuilding starts from the reference translations, so the open layer alone
does not regenerate the withheld splits.

The scoring script and the full build pipeline are open-source at
https://github.com/Prompsit/prompsit-mdc - the dataset content itself is
distributed here on MDC.

## Scope boundaries

- Reference renderings are machine-generated from CLDR (via Babel) and checked
  by the scoring script rather than manually double-annotated; all released
  references pass the D2 checks (self-check 6,120/6,120).
- One value per source; the host sentences are reused across entity kinds.
- Baseline scores in this package come from simulated systems (deterministic
  corruption operators); no outputs of live MT engines are included.
- The package contains es-ES and pt-PT profiles; it does not include pt-BR.

## Related work

This datasheet follows the structure proposed in Datasheets for Datasets
(Gebru et al., https://arxiv.org/abs/1803.09010). The error categories map to
the locale, terminology and markup branches of the MQM error typology
(https://themqm.org/), turned from human
annotation tags into automated checks.

The closest prior work is Wang et al. (Findings ACL 2021,
https://aclanthology.org/2021.findings-acl.415/), which tests numerical
translation for numerals and separators only. This dataset extends locale
conformance to dates, currency amounts and units, with CLDR as the
reference for the expected target-locale forms.
