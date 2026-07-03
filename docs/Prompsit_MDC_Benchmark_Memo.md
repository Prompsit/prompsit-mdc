# Prompsit Localization Benchmark Recipes

## 1. Problem

Machine translation and LLM translation systems can produce fluent text while
breaking localization assets required by production workflows. Standard MT
metrics such as BLEU, chrF, COMET, MetricX, and xCOMET measure semantic or
reference-based quality, but they do not reliably answer whether an output can
be imported, rendered, executed, or reused inside a localization pipeline.

The program addresses five families of production failures, each owned by exactly
one dataset (§5, where the correctness logic of each is defined). Standard metrics
miss all of them:

| Failure family | Failure examples |
|---|---|
| Inline string assets | Missing/extra tags or placeholders, invalid nesting, moved paired tags, corrupted variable syntax, wrong placeholder order, broken ICU plural/select, lost attributes, translated do-not-translate spans, UI truncation, encoding corruption. |
| Locale data | Wrong decimal/grouping separator, mis-converted date/time format, wrong units or measures, broken currency format for the locale. |
| Structured resources | JSON/XML keys translated, schema changed, invalid CSV shape, non-value fields modified. |
| Document structure | Lost headings, list/table corruption, changed segment order, broken links/images, invalid round-trip conversion. |
| Linguistic resources | Required term missing, forbidden term used, terminology applied inconsistently, blind copying of bad fuzzy matches, ignored approved matches. |

Existing research benchmarks are relevant references, but the target here is
not a general translation instruction-following benchmark. The target is a set
of reusable localization benchmark datasets and validators for production asset
integrity.

## 2. Solution

The project defines **benchmark recipes**. A recipe is a dataset package plus
validators, scoring rules, baseline outputs, and reporting conventions for one
specific localization risk.

Each recipe answers one concrete production question — for example, "does this
pipeline keep inline tags and placeholders valid and in order?" or "does it
localize numbers, dates, and currency correctly?" The full set, one question per
dataset, is the catalogue in §5.

The program has four technical components:

| Component | Role |
|---|---|
| Dataset package | Provides source items, references where needed, asset annotations, language-pair metadata, schemas, and split manifests. |
| Local validators/scorers | Run deterministic checks for hard failures and produce machine-readable scores. |
| Baseline outputs/reports | Store outputs from selected systems and summarize failure classes for comparison. |
| Prompsit Bench/API integration | Runs extended scoring, alignment-based placement checks, regression comparisons, and HTML/JSON reports. |

`prompsit-word-alignment` is used where placement quality requires word
alignment or similarity matrices. It is not required for every recipe; purely
syntactic validators should stay deterministic and local.

## 3. Access, Licensing, And Monetization

The publication model separates open materials, controlled downloadable data,
and non-downloadable evaluation data.

| Layer | Published contents | Hosted on | Access |
|---|---|---|---|
| Open recipe | Schema, methodology, local validators, dev/sample set (open reference labels), baseline summary, dataset card. | HF / GitHub mirror | Open license (CC-BY-4.0 / Apache-2.0). |
| Gated test pack | Test-split inputs (reference labels withheld), baseline outputs, versioned manifests, checksums. | MDC (canonical card per recipe) | MDC Request to Access; price optional. |
| Premium pack | Expanded test packs, additional baselines, maintained compatibility files, support materials. | MDC (paid) or direct | Commercial terms or the MDC payment flow. |
| Hidden evaluation | Non-downloadable official set and scorer execution (modes A/B/C, §4). | prompsit-bench (off-platform) | Evaluation endpoint or private workflow. |
| Customer-private suite | Customer artifacts, derived private datasets, private baselines, private reports. | Off-platform / customer | Customer agreement. |

Licensing is split by artifact type:

| Artifact | License policy |
|---|---|
| Code, validators, local runners | Open-source license, recommended default Apache-2.0. |
| Public datasets | Dataset license chosen per data provenance, recommended default CC-BY-4.0 when compatible. |
| Gated/premium datasets | Dataset-specific terms, including access conditions and redistribution limits. |
| Hidden sets | Not distributed as dataset files. |
| Customer-private data | Customer agreement; no publication unless explicitly approved. |

The monetizable surfaces are not limited to selling dataset files. They include
controlled test packs, Prompsit Bench/API execution, private evaluation, custom
benchmark construction, engine-selection reports, regression packs, and
customer-specific localization risk reports.

## 4. Benchmark And Dataset Methodology

### Dataset Unit

Each dataset is bounded by one pain — one notion of what "correct" means (the
four correctness logics in §5) — not by file format or language. Three rules keep
the boundaries clean:

- **Ownership by assertion.** A dataset owns an invariant, not a file. One source
  artifact (e.g. a JSON file) may feed several datasets, each checking a different
  invariant — its keys/schema (D3), inline tags inside values (D1), numbers inside
  values (D2) — with no double-counting. Ambiguous instances are classified by the
  unit under evaluation (inline string/fragment → its inline owner; whole document
  → D4); genuinely cross-cutting conditions (e.g. encoding) are reported by
  non-owners only as non-scoring diagnostics, with one primary scoring owner.
- **Format is a profile, not a dataset.** Formats that share a validator approach
  live as profiles inside one dataset (JSON/CSV/XML in D3), reported per format. A
  format becomes its own dataset only when its approach genuinely differs (document
  round-trip in D4 vs key-diff in D3).
- **Language is a dimension.** A dataset contains multiple language pairs under the
  same pain definition; language pairs are metadata, not separate datasets.

A segment-level recipe uses records with:

- item id;
- source language;
- target language;
- source text or source artifact fragment;
- reference translation where required;
- hypothesis/output field for evaluation input;
- asset annotations;
- expected asset invariants;
- split id;
- provenance metadata.

A resource-level recipe (structured files) uses records with:

- resource id;
- source language;
- target language;
- source resource fragment or file;
- key/path map (translatable vs non-translatable);
- schema or structure descriptor;
- expected value-only invariants;
- split id;
- provenance metadata.

A document-level recipe uses records with:

- document id;
- source document or fragment;
- target language;
- extracted segment map;
- expected structural representation;
- converted output or hypothesis document;
- round-trip validation metadata.

### Language-Pair Structure

Each dataset declares its supported language pairs explicitly (see the
"Language is a dimension" rule above).

Initial language pairs should be selected by:

- availability of qualified reviewers;
- availability of license-clean source material;
- coverage of Prompsit-relevant markets and language expertise;
- ability to exercise the same failure families across languages.

### Segment Count Policy

Segment counts are defined per dataset and split. A dataset size is accepted
only when it supports the intended comparison.

Each dataset specification must state:

- number of source items;
- number of target-language records;
- number of language pairs;
- number of asset instances by class;
- minimum examples per failure class;
- dev/test/hidden split counts;
- baseline systems included.

The size rationale should be based on coverage of failure families, error
classes, language pairs, and baseline comparison needs. A dataset should not be
expanded only to reach a round number.

Default sizing rule: ≥100 instances per error class per language pair give
roughly ±6 pp Wilson half-width around p≈0.9 and roughly ±10 pp near the worst
case p≈0.5; use 150–200 where fine system comparison is expected, and ~200 for
critical classes. Each dataset must
also ship legal-variation positives (correct outputs that resemble edits) to bound
validator false positives, and ≥5 baseline systems including at least one weak on
the target assets for discriminative power.

### Split Policy

| Split | Inputs | Reference | Scored by | Distribution |
|---|---|---|---|---|
| Dev/sample | Open | Open | Client, local validators | Open |
| Test | Open | Withheld | Prompsit | Gated |
| Hidden | Withheld | Withheld | Prompsit | Not downloadable |

Default proportions ~10% dev / ~70% test / ~20% hidden, stratified by asset and
error class, partitioned by source id so all translations of one source stay in
one split (no cross-split source leakage). This prevents leakage between splits,
not external exposure — released test inputs can still reach prompts or training;
the hidden split (Modes B/C) is the guard against that.

### Evaluation Workflow

Withheld reference labels (inputs may be released) are what make an official
score valid: they block teaching-to-the-test, validator gaming, and training
contamination, and make the score attestable rather than self-reported. Purely
deterministic, self-evident checks need no withheld reference — that is the open
dev split.

The system under test reaches the scorer in one of three intake modes. Reference
labels, scorer, and report are identical across them; they differ only in how
outputs are obtained and how trusted the result is:

| Mode | How outputs are produced | Use when | Assurance |
|---|---|---|---|
| A — Submission | Client runs its system, submits output JSONL | Default; engine anywhere (WMT/GLUE style) | Self-run |
| B — Endpoint | Prompsit calls the client's MT API on hidden inputs | Certified/controlled run; engine reachable | We-ran |
| C — Sealed run | Client model runs in an isolated/sealed runner | On-prem or full-secrecy engines | Sealed |

Modes are complementary, not exclusive; the client's setup usually dictates the
choice. They ladder (dev self-check → A → B/C) onto the access tiers (§3). Each
result carries its assurance tag, and an official ranking fixes one mode.

### Scoring Policy

Scoring is separated into layers:

| Layer | Purpose | Examples |
|---|---|---|
| Invariant checks | Determine whether the output violates required asset invariants. | Parseability, inventory preservation, placeholder/ICU syntax, nesting validity, schema/key preservation, locale-form conformance. |
| Severity | Classify production impact. | Critical, Major, Minor. |
| Placement quality | Measure whether preserved assets are placed correctly. | Alignment-based drift, span overlap, tag-position quality. |
| Semantic quality | Measure translation quality separately from asset integrity. | COMET, MetricX, xCOMET, or other MT quality scores where available. |
| Regression comparison | Compare two pipeline versions. | Failure deltas by class, severity, language pair, and asset family. |

Invariant-check failures must not be hidden by high semantic scores.

Invariant-check metrics are official for all pairs. Placement-quality metrics depend on
aligner accuracy, so they are official only for pairs with a calibrated alignment
threshold — calibrated on the XL-WA human-annotated word-alignment set for es, it, pt. For
pairs XL-WA does not cover (fr, ca), placement is reported as an experimental
diagnostic until separately calibrated, and is not a publication blocker.

### Severity Classes

| Severity | Definition |
|---|---|
| Critical | Output cannot be parsed, imported, rendered, executed, or round-tripped. |
| Major | Output remains usable but changes meaning, UI behavior, variable binding, terminology, or required asset position. |
| Minor | Output preserves required function but introduces harmless formatting movement or low-risk inconsistency. |

### Provenance And Reproducibility

Each dataset must include:

- source data provenance;
- license notes;
- generation or selection rules;
- annotation guidelines;
- validation evidence matched to the label type. Reference labels are derived
  deterministically from the source by an oracle (not human task-annotation).
  Machine-checkable labels use a deterministic oracle plus reference
  self-consistency, the discrimination check (K1), and the false-positive check
  (K2). Native-speaker double annotation and inter-annotator agreement are
  required only for non-deterministic judgment labels;
- schema version;
- split manifest;
- checksums;
- baseline configuration: exact model/endpoint, run date, API version, prompt template, decoding parameters, tag/glossary/format modes, retry policy, and any post-processing (so cloud-engine baselines stay reproducible);
- validator version;
- known limitations.

## 5. Dataset Catalogue

The catalogue is five datasets, each closing one pain. Pains are grouped by four
**correctness logics** — what it means for an output to be correct for that
asset:

- **A — preserve identity, syntax, pairing and legal placement** (the asset keeps its identity and validity; position changes only within annotated legal-movement rules, and translatable text inside ICU branches is still translated): D1.
- **B — adapt to the target locale** (the value must change to the locale form): D2.
- **C — preserve the skeleton, translate only content**: D3, D4.
- **D — respect provided linguistic resources**: D5.

Logics A and B are deliberately separate datasets: a validator that enforces
asset preservation would wrongly penalise a correctly localised number, so
preserve-the-asset (A) and transform-the-value (B) can never share a dataset.

Each dataset spans all declared language pairs (language is a dimension, §4) and
may hold several format profiles (format is a profile while the validator
approach is shared, §4).

| Dataset | Pain it closes (correctness logic) | Format profiles inside | Labels / expected invariants | Metrics / validators |
|---|---|---|---|---|
| **D1 — Inline asset integrity** | Inline machine tokens keep identity, syntax and pairing; position only within legal-movement rules; protected spans verbatim (A). | XLIFF, HTML/XML inline, ICU, printf/placeholders, Markdown inline, do-not-translate; **diagnostics (non-scoring):** length/truncation, encoding. | Asset inventory, type, pairing, nesting, attributes, syntax, order, ICU branch integrity, legal movement, verbatim spans. | Inventory F1, parseability, nesting validity, placeholder/ICU syntax validity, order validity, alignment-based placement drift, severity. |
| **D2 — Locale-data integrity** | Numeric, temporal and measure values must adapt to the target locale (B). | numbers, dates/times, units/measures, currency (entity types). | Expected locale form per entity, accepted locale variants, unacceptable corruptions, severity. | Entity-extraction recall, locale-rule conformance, format match, severity. |
| **D3 — Structured-resource integrity** | The resource skeleton stays; only values are translated (C). | JSON, CSV, XML / YAML / .properties. | Key/path preservation, schema preservation, value-only translation, parser validity. | Parser validation, key-path match, schema diff, value coverage. |
| **D4 — Document-structure integrity** | The document tree is preserved and round-trips (C). | HTML. | Structural tree, block order, table-cell mapping, link/image references, segment map. | Round-trip validity, tree match, block-order accuracy, table-cell preservation, link/image preservation. |
| **D5 — Linguistic-resource adherence** | Provided glossary and translation memory must be respected (D). | termbase, TM (exact/fuzzy). | Required/forbidden terms, consistency, reuse decision, known bad-match traps. | Term presence/forbidden detection, consistency over repetitions, reuse-decision accuracy, conflict handling. |

Within those five families, every machine-checkable failure class has one
**primary scoring owner** — no double-counting. The same source may exhibit
several classes, each scored by its owner (ownership by assertion, §4);
cross-cutting conditions (e.g. encoding) may be surfaced by other datasets as
non-scoring diagnostics, never as a second official score.

| Failure class | D1 | D2 | D3 | D4 | D5 |
|---|:--:|:--:|:--:|:--:|:--:|
| Inline tags + formatting | ✓ | | | | |
| Markdown inline (links / code) | ✓ | | | | |
| Placeholders / template vars | ✓ | | | | |
| ICU plural / select | ✓ | | | | |
| Do-not-translate / verbatim spans (class) | ✓ | | | | |
| Length / truncation, UI (class) | ✓ | | | | |
| Encoding / off-codepage (class) | ✓ | | | | |
| Numbers (decimal, grouping) | | ✓ | | | |
| Dates / times | | ✓ | | | |
| Units / measures / currency | | ✓ | | | |
| Structured schema & keys (value-only) | | | ✓ | | |
| Document structure (tables, round-trip) | | | | ✓ | |
| Terminology / glossary | | | | | ✓ |
| TM reuse (fuzzy / bad-match) | | | | | ✓ |

D1 carries the most classes and is the heaviest dataset; if a single annotation
effort cannot cover it, the first split is tags vs variables — kept together here
because they share one validator approach.

Regression testing is not a separate dataset category. It is an evaluation mode
that can be applied to any dataset above by comparing outputs from two pipeline
versions on the same items.

Per-dataset specs follow. They state only what is specific to each dataset; the
sizing rule, split proportions, validation policy, and baseline policy are
inherited from §4.
Full numbers and provenance live in `MDC_Dataset_Registry.md` and each
dataset's `DATASHEET.md`, `manifest.json`, and `THIRD_PARTY_NOTICES.md`.

> **Canonical catalog (SSOT):** versions, sizes, classes, sourcing, and K1/K2
> status for every dataset live in [MDC_Dataset_Registry.md](MDC_Dataset_Registry.md).
> The sections below give design rationale, not the live numbers.

### 5.1 D1 — Inline asset integrity

**Failure classes (per §4):** missing/extra asset, broken nesting, moved paired tag, corrupted placeholder syntax, wrong order, broken ICU branch, lost attribute, do-not-translate violation; critical classes (missing, nesting, ICU) ~200/class/pair, others ~150.
**Diagnostics (non-scoring):** length/truncation and encoding — reported as string-compatibility diagnostics, not in the official D1 score (different validator approach).
**Languages & size:** EN→{ca, es, fr, it, pt-PT, de, nl, pl, ru}; a single balanced clean-positive set of 599 sources × 9 = 5,391 records.
**Baselines:** NLLB-200, MADLAD-400, GPT-4o, Claude, DeepL + one tag-blind NMT.
**Key risk:** sourcing license-clean strings rich in tags/ICU; heaviest dataset (most classes).
**Realized build (v1.0):** see the [Dataset Registry](MDC_Dataset_Registry.md) and `datasets/d1-inline-asset-integrity/DATASHEET.md` (the per-dataset SSOT).

### 5.2 D2 — Locale-data integrity

**Correctness:** **formatting adaptation** (decimal/grouping, date/time, currency and unit *rendering*) is deterministic from CLDR. The semantic value is preserved. Corruption or wrong-locale rendering is a failure; locale-legal variants are not.
**Reference per item:** source value, intended target locale, expected normalized semantic value, accepted rendered variants, unacceptable corruptions.
**Failure classes (per §4):** wrong decimal separator, wrong grouping, mis-converted date/time, wrong unit format, broken currency format; ≥100–150/class/pair.
**Locales (the D2 dimension):** v1.0 covers en-US -> es-ES, fr-FR, pt-PT, it-IT, ca-ES, de-DE, nl-NL, pl-PL, ru-RU (9 locales, matching D1). D2 is keyed by locale, not language - `es` alone underspecifies separators/dates/currency. Size from the per-class floor.
**Baselines:** same set + one engine that passes values through unlocalized.
**Key risk:** fixing each target-locale profile and its accepted variants; keeping formatting separate from policy conversion.
**Realized build (v1.0):** `datasets/d2-locale-data-integrity/DATASHEET.md` — 680 sources x 9 locales; a single headline format track; currency surface/semantic invariant; K1/K2 PASS.

### 5.3 D3 — Structured-resource integrity

**Failure classes (per §4):** key/path translated, schema changed, value skipped or over-translated, parser break, non-value field modified; ≥100/class/pair.
**Unit:** resource file/fragment; instances counted across keys.
**Languages & size:** nine languages (ca/es/fr/it/pt-PT/de/nl/pl/ru in v1.0); size from the per-class floor.
**Baselines:** same set + one engine that translates keys.
**Key risk:** mapping "file → instances per class"; choosing representative resource shapes.
**Realized build (v1.0):** `datasets/d3-structured-resource-integrity/DATASHEET.md` — 420 sources x 9 langs, 4 format profiles; tiered DNT check (literal/letterless all-formats / marked alphabetic incl. acronyms XML-only via `translatable="false"`); K1/K2 PASS.

### 5.4 D4 — Document-structure integrity

**Failure classes (per §4):** lost/duplicated structural node, block-order change, table-cell corruption, broken link/image reference, round-trip failure; ≥100/class/pair.
**Unit & splits:** whole document — fewer, structurally rich documents (not 1000), enough to reach the per-class floor; splits stratified, partitioned by document id.
**Languages & size:** nine languages (ca/es/fr/it/pt-PT/de/nl/pl/ru in v1.0).
**Baselines:** same set + one engine that flattens structure.
**Key risk:** heaviest infra is preserving document structure while using license-clean rich HTML.
**Realized build (v1.0):** `datasets/d4-document-structure-integrity/DATASHEET.md` — 160 documents x 9 langs, HTML profile; document-contract baseline; K1/K2 PASS.

### 5.5 D5 — Linguistic-resource adherence

**Failure classes (per §4):** required term missing, forbidden term used, inconsistent term, approved TM ignored, conflict mishandled, fuzzy discernment; ≥400 records/class in the K1 set.
**Applicability:** D5 evaluates systems or pipelines that can consume the supplied linguistic resources — directly (CAT/TMS, glossary-aware LLM) or through an explicit wrapper (pre-processing, prompt, constrained decoding, terminology injection, post-editing). Engines with no resource input are reported `not applicable` for native D5, but may be evaluated as a configured pipeline.
**Languages & size:** nine languages (ca/es/fr/it/pt-PT/de/nl/pl/ru in v1.0).
**Baselines:** resource-consuming engines + one that ignores the supplied resources.
**Key risk:** curating termbases and planted bad-fuzzy TM; overlaps IFMTBench glossary — differentiated by production reuse-decision, not prompt glossary.
**Realized build (v1.0):** `datasets/d5-linguistic-resource-adherence/DATASHEET.md` — 510 sources x 9 langs, 4 resource profiles in glossary/tm/conflict/quality tracks; glossary + tm are the headline adherence tracks, conflict/quality reported apart; K1/K2 PASS.

## 6. Competitor Analysis

| Reference | What it does | Overlap | Prompsit difference |
|---|---|---|---|
| IFMTBench | LLM translation instruction-following benchmark: glossary, layout, structured data, code/tag preservation, mixed constraints. | D1, D3, D5; partial D4 | Production localization pipeline integrity across MT/LLM/TMS; reusable deterministic validators, hidden/certified evaluation, MDC distribution, customer-private suites, API-backed reports — not LLM-prompt-constraint following. |
| TildeBench robustness | Tagged-content robustness for MT/LLM/commercial services; narrow language coverage. | D1 | More localization formats; full recipe (validators + baselines + hidden eval) and customer-private workflows. |
| WMT/Amazon markup-tags | XLIFF 1.2 markup tag test sets. | D1 | Packaged recipes, deterministic validators, baselines, API, MDC, hidden evaluation. |
| TMS QA tools | In-tool QA inside a TMS (tags, placeholders, numbers, terminology). | D1, D2, D5; partial D3 | Vendor-neutral cross-engine benchmark with certified/hidden scoring, not in-tool QA tied to one CAT. |
| XL-WA (SapienzaNLP) | Human-annotated word-alignment benchmark, 14 EN-X pairs; CC BY-NC-SA. | none (upstream aligner) | Adjacent/upstream — evaluates aligners, not pipeline integrity. Used to validate our aligner (es, it, pt); commercial-clean licensing. |

## 7. Acceptance checks

The v1.0 datasets are released only when the following checks pass. These are
publication checks for the completed release.

| Check | Requirement | v1.0 status |
|---|---|---|
| Discrimination check (K1) | A deliberately weak baseline is statistically separated from the best baseline on at least half the reported classes (`p<0.05`, paired bootstrap; iteration count stored in each K1 report). | **PASS** for D1-D5 |
| False-positive check (K2) | Validators (automated checks, not human reviewers) do not reject clean oracle references or curated legal variants. | **PASS**, 0.0% false positives for D1-D5 |
| Reference reliability | Deterministic labels self-pass the invariant checks; judgment labels are not used in the released scoring surface. | **PASS**, all records are `oracle_validated` |
| License/provenance | Public layer is CC-BY-4.0 with per-record provenance and third-party notices for inherited sources. | **PASS** |
| Publication packaging | Open archives contain dev reference, test inputs, contrastive dev, metadata, datasheet, notices, README, manifest, Croissant, and no hidden/held-out-reference files. | **PASS** |

## 8. Source Notes

**Primary references** (methodology and prior art):

- MDC standalone launch, Request to Access, and Payments/Compensation direction:
  <https://www.mozillafoundation.org/en/meet-mozilla/press-center/mozilla-data-collective-standalone-launch-new-features/>
- MDC API reference:
  <https://mozilladatacollective.com/api-reference>
- IFMTBench:
  <https://arxiv.org/abs/2605.28218>
- IFMTBench repository:
  <https://github.com/Tencent-Hunyuan/Hy-MT2/blob/main/IFMTBench/README.md>
- WMT/Amazon markup-tags data:
  <https://github.com/amazon-science/mt-markup-tags>
- TildeBench:
  <https://tilde-nlp.github.io/one-shot-empty-robustness-bench.html>
- MQM (Multidimensional Quality Metrics) error typology, used to ground the failure families:
  <https://themqm.org/the-mqm-typology/>
- memoQ automated QA check categories, used to confirm machine-checkable failure families:
  <https://docs.memoq.com/current/en/Concepts/concepts-quality-assurance-qa-warnings.html>
- XL-WA human-annotated word-alignment benchmark, used to validate the aligner (CC BY-NC-SA — internal validation only, not a data source):
  <https://github.com/SapienzaNLP/XL-WA>
