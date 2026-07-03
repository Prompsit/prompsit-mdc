# D4 - Document-structure Integrity (datasheet)

**Version** 1.0 | **Schema** 0.1 | **Scoring rule:** the document tree must be preserved - same nodes, same block order, same table shape, same link and image targets; only the text is translated

An HTML document carries structure beyond its text: headings, paragraphs,
lists, tables, links, and images arranged in a tree. This dataset tests whether
machine translation preserves that tree while translating only the text. Each
document is composed from human translation segments shared with the D1
inline-asset dataset, arranged on a templated structure, and exists in English
plus nine target languages. Inline tags inside text are covered by the D1
dataset and locale data by the D2 dataset; this dataset scores the document
tree, with no double-counting.

The translations are human, drawn from real localization catalogs. The
labels on them (asset inventories, positions, expected forms) are derived
automatically and deterministically from the source, so they are reproducible
end to end; the false-positive check below verifies they never flag a correct
human translation.
Every released reference passes the scoring script (1,440/1,440).

## How to use this dataset

1. Download the open layer from this page and unpack it: `data/dev.jsonl`
   (inputs plus reference translations), `data/test.input.jsonl` (inputs
   only), `data/contrastive.dev.jsonl`.
2. Translate the source strings with the MT system you want to evaluate - any
   system works; no special integration is required.
3. Score the outputs with the open-source scoring script - `score_item(...)`
   in https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d4-document-structure-integrity/build
   (`documents.py`).

To verify your harness first, score the dev references themselves: they must
pass 100%.

## Task and scoring

The task: translate each HTML document from English into the target language
while keeping the document tree intact.

Scoring is fully automatic; no human judges are involved. For every record, a
deterministic scoring script (open-source:
https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d4-document-structure-integrity/build)
inspects the system output and reports which error categories occur (see the
Error categories table below). A record **passes** if no error category occurs.
The score of a system is its **pass rate**: the fraction of records that pass,
reported overall and per error category. The checks compare the document tree
of the output against the source document, so no reference translation of the
output is needed.

The scoring entry point is `score_item(...)` in `documents.py` there; the `README` and `AGENTS.md` at the repository root
walk through scoring your own outputs.

The six automated checks are: `roundtrip_valid` (strict XML well-formedness via
ElementTree, which catches broken attributes and unclosed tags a lenient HTML
parser would swallow), `tree_match` (the node multiset matches the source),
`block_order` (the block sequence, table internals excluded), `table_shape`
(per-table rows x columns), `links_images` (href and src verbatim), and
`segment_count` (text-segment count). All are compared against the source
structure, which is language-independent.

## MDC technical summary

- Domain: machine-translation quality evaluation for document-structure
  preservation.
- Size: 1,440 records; the open archive contains the dev split (with
  references), the test inputs, the contrastive pairs, README, this datasheet,
  third-party notices, manifest, and Croissant metadata.
- Structure: JSONL records with source and target HTML, a structural
  fingerprint of the document tree (node types and counts), link and image
  targets, expected invariants, error-category tags, split, and provenance.
- License: CC-BY-4.0 open layer; upstream attributions in
  `THIRD_PARTY_NOTICES.md`.
- Dataset on MDC (download the open layer): https://mozilladatacollective.com/datasets/cmr0moi2k01c0mk07eocv137z

## Independent evaluation

The test references and the hidden split are withheld, so a score on those
splits reflects performance on unseen inputs rather than answers a system could
have memorised. For an independent evaluation of an MT or LLM system on the
withheld splits, contact Prompsit at info@prompsit.com.

## Contents and splits

| Split | File | Records | What it contains |
|---|---|---|---|
| Open dev | `data/dev.jsonl` | 144 | inputs plus the reference translation and labels |
| Test inputs | `data/test.input.jsonl` | 1,008 | inputs only; references withheld |
| Test references | `data/test.ref.jsonl` | 1,008 | withheld, retained by Prompsit |
| Hidden | - | 288 | never distributed |
| Contrastive | `data/contrastive.dev.jsonl` | 720 | verification records for (correct, damaged) minimal pairs; the damaged variants are regenerated bit-identically from the dev split by the open build pipeline, and each pair is separated by the scoring script |

160 sources x 9 languages = **1,440 records**. Split ~10% dev / 70% test / 20%
hidden (sources: 16 / 112 / 32), partitioned by `item_id`, so a source and its
nine translations never cross splits.

No training set is shipped. The dev split is a small labelled set for optional
few-shot prompting or sanity checks; it is not required to run the benchmark.

## Languages

`en` into `ca, es, fr, it, pt-PT, de, nl, pl, ru`. Every source document is
present in all nine languages with the same document tree, so per-language
scores are directly comparable.

## Error categories

Every record is tagged with the error categories it can expose; the scoring
script detects each category with a dedicated automated check. Severity is
reported alongside a failure for error analysis; it does not change the
pass/fail rule.

| Error category | What it means | Severity | Records |
|---|---|---|---|
| `lost_or_duplicated_node` | a node from the source tree is missing or duplicated | Major | 1,152 |
| `block_order_change` | block elements appear in a different order | Major | 1,152 |
| `table_cell_corruption` | a table's rows-by-columns shape changed | Major | 1,152 |
| `broken_link_image` | an href or src no longer matches the source verbatim | Major | 1,152 |
| `roundtrip_failure` | the output is no longer well-formed XML | Critical | 1,152 |

At least 400 records per error category (our minimum for a reliable
per-category estimate). Each error category is exercised in all 1,152 dev+test
records; the 288 hidden records are additional.

## Sample records

Real records from the open dev split, truncated for width. Angle brackets in
markup are shown as ⟨ ⟩ because this platform strips raw HTML-like tags; the
data files contain the ordinary characters.

| item_id | target | source text | target text | structure profile | error categories |
|---|---|---|---|---|---|
| d4-000023 | ca | ⟨html⟩⟨body⟩ ⟨h1⟩{COUNT, plural, =1 {an address} other {# addresses}}⟨/h1⟩ ⟨p⟩{MINUTES, plural, =1 {1m} other {#m}}⟨/p⟩... | ⟨html⟩⟨body⟩ ⟨h1⟩{COUNT,plural, =1{1 adreça}other{# adreces}}⟨/h1⟩ ⟨p⟩{MINUTES,plural, =1{1 m}other{# m}}⟨/p⟩... | h1 p h2 p ul(3) p+a table(2x2) img | lost_or_duplicated_node, roundtrip_failure |
| d4-000025 | ca | ⟨html⟩⟨body⟩ ⟨h1⟩⟨xliff:g id="numprocess"⟩%1$d⟨/xliff:g⟩ process and ⟨xliff:g id="numservices"⟩**%2$d**⟨/xliff:g⟩ service⟨/h1⟩ ⟨h2⟩{COUNT, plural, =1 {Item} other {# items}}⟨/h2⟩... | ⟨html⟩⟨body⟩ ⟨h1⟩⟨xliff:g id="NUMPROCESS"⟩%1$d⟨/xliff:g⟩ procés i ⟨xliff:g id="NUMSERVICES"⟩**%2$d**⟨/xliff:g⟩ servei⟨/h1⟩ ⟨h2⟩{COUNT,plural, =1{Element}other{# elements}}⟨/h2⟩... | h1 h2 p p ul(3) table(2x2) p+a img | block_order_change, table_cell_corruption |
| d4-000066 | ca | ⟨html⟩⟨body⟩ ⟨h1⟩MIDI Input on Channel=%s Message=%s⟨/h1⟩ ⟨p⟩at ⟨xliff:g id="time" example="2:33 am"⟩**%s**⟨/xliff:g⟩⟨/p⟩ ⟨h2⟩⟨xliff:g id="extension" example="PDF"⟩`%1$s`⟨/xliff:g⟩ file⟨/h2⟩... | ⟨html⟩⟨body⟩ ⟨h1⟩Entrada de MIDI al Canal=%s Missatge=%s⟨/h1⟩ ⟨p⟩a les ⟨xliff:g id="TIME"⟩**%s**⟨/xliff:g⟩⟨/p⟩ ⟨h2⟩Fitxer ⟨xliff:g id="EXTENSION"⟩`%1$s`⟨/xliff:g⟩⟨/h2⟩... | h1 p h2 p table(2x2) ul(3) p+a img | broken_link_image, block_order_change |

The structure profile column lists the block sequence of the document: the
three documents above share the same building blocks (headings, paragraphs, a
three-item list, a 2x2 table, a link, an image) but arrange them in different
orders, which is exactly what the `block_order` check must track.

## Source data and licenses

| Content | License | Structure |
|---|---|---|
| Human translations (shared with the D1 inline-asset dataset) | per-segment (Apache-2.0 / BSD-3-Clause / MIT, inherited) | templated HTML (headings, paragraphs, list, table, link, image) |

The text is human parallel translation; the structural scaffolding is
templated, and the structure is exactly what this dataset scores. Upstream
attribution notices accompany the release in `THIRD_PARTY_NOTICES.md`.

## Construction method

1. **Segment pool**: human translation segments shared with the D1
   inline-asset dataset; each segment exists in English plus all nine target
   languages.
2. **Composition**: `build_dataset.py` assembles each document from those
   segments on a fixed template - headings, paragraphs, a three-item list, a
   2x2 table, a link, and an image - with the block order varied between
   documents.
3. **Reference labels**: a structural fingerprint of the document tree (node
   types and counts), the block sequence, per-table shapes, and the link and
   image targets are extracted deterministically from the source; the checks
   compare the output against this fingerprint.
4. **Splits**: ~10/70/20, partitioned by `item_id`.

## Dataset-quality checks

Two checks are run on the dataset itself before release. They validate the
benchmark, not any particular MT system.

- **Discrimination check (K1):** can the dataset separate systems that preserve
  the document tree from systems that do not? Contrasting baseline systems are
  scored with the real scoring script, and the damaging baselines must come out
  significantly worse (paired bootstrap, p-value below 0.05 - that is, the gap is too large to be chance).
- **False-positive check (K2):** does the scoring script ever flag a correct
  human translation as an error? The released references and legal variants of
  them are rescored; the target is 0%.

| Check | Result |
|---|---|
| Discrimination (K1) | **PASS** - structure-blind baselines (structure flattener, raw copy) score 0% where a structure-aware system scores 100%, separated on 5 of 5 error categories (paired bootstrap p-value below 0.05). The baselines are simulated corruption operators scored with the real scoring script. |
| False positives (K2) | **PASS** - 0.0% flips over 7,200 legal variants (whitespace, reindent, collapse, doctype, upper-case tags) |
| Reference self-check | 1,440/1,440 - every released reference passes the scoring script |
| Croissant 1.0 | `croissant.json`, mlcroissant-validated |

## Reproducibility

The build is deterministic and seeded; rebuilding produces a bit-identical
package, and `checksums.sha256` (shipped in the archive) verifies a download.
Documents are composed from the D1 translation segments, most of which are
withheld, so the open layer alone does not regenerate the test and hidden
splits.

The scoring script and the full build pipeline are open-source at
https://github.com/Prompsit/prompsit-mdc - the dataset content itself is
distributed here on MDC.

## Scope boundaries

- Reference labels are machine-generated by deterministic parsers rather than
  human task-annotation; all released references pass the checks (self-check
  1,440/1,440).
- HTML documents only.
- Templated structure with human-translated text; structural variety is
  limited to one template family with varied block order.
- Scores structural shape (tree, block order, table dimensions, link and image
  targets, segment count) plus strict round-trip validity. Content-to-node
  alignment (which translated segment landed in which cell or block) is not
  verified - a swap that preserves shape passes.

## Related work

This datasheet follows the structure proposed in Datasheets for Datasets
(Gebru et al., https://arxiv.org/abs/1803.09010). The error categories map to
the locale, terminology and markup branches of the MQM error typology
(https://themqm.org/), turned from human
annotation tags into automated checks.

CzechDocs (https://arxiv.org/abs/2606.20212) targets format-preserving
document translation (HTML/DOCX/PDF) with parallel data and a planned
shared task, and DocHPLT (WMT 2025, https://aclanthology.org/2025.wmt-1.17/)
provides document-level parallel data. This dataset differs in what it
measures: an automatic pass/fail score for whether the document tree
(nodes, block order, table shape, links and images) survives translation.
