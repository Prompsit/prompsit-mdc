# MDC Dataset Registry (SSOT)

> **Single source of truth** for the Prompsit MDC benchmark datasets. Every
> headline number, version, and status below is taken from each dataset's own
> `manifest.json` / `live_k1_report.json`. Other docs (root `README.md`, the
> Benchmark Memo, per-dataset DATASHEETs) **link here** rather than restating the
> catalog — update this file when a dataset version or status changes.
>
> **Last updated:** 2026-06-22 (all datasets v1.0)

The benchmark measures **machine-translation integrity** across five
complementary failure surfaces (D1–D5). Each dataset shares the same
9-language target set, the same split discipline, and the same two acceptance
checks (discrimination check K1, false-positive check K2), so results are
comparable across dimensions.

Reference labels are derived deterministically from the source by an oracle
(not human task-annotation). It is an evaluation benchmark: no training data is
provided; the dev split is an open set for few-shot/tuning, not required.

## Catalog

| ID | Dataset | Ver | Scoring rule | Sources | Records | Splits (sources: test / dev / hidden) | Classes | K1 | K2 |
|----|---------|-----|-------------------|--------:|--------:|---------------------------------------|--------:|----|----|
| **D1** | inline-asset-integrity | 1.0 | A — inline assets preserved byte-exact | 599 | 5 391 | 413 / 71 / 115 | 7 | PASS¹ | PASS |
| **D2** | locale-data-integrity | 1.0 | B — adapt values to target locale | 680 | 6 120 | 474 / 70 / 136 | 5 | PASS | PASS |
| **D3** | structured-resource-integrity | 1.0 | C — preserve skeleton, translate content | 420 | 3 780 | 294 / 42 / 84 | 6 | PASS | PASS |
| **D4** | document-structure-integrity | 1.0 | C — preserve document tree, translate text | 160 | 1 440 | 112 / 16 / 32 | 5 | PASS | PASS |
| **D5** | linguistic-resource-adherence | 1.0 | D — respect provided glossaries / TM | 510 | 4 590 | 357 / 51 / 102 | 6 (4 tracks) | PASS | PASS |

K2 false-positive rate is **0.0 %** for every dataset. All quota/validation
checks PASS.

**On Mozilla Data Collective:** [D1](https://mozilladatacollective.com/datasets/cmr0mng9z01bsmk07cuqltz81) · [D2](https://mozilladatacollective.com/datasets/cmr0mnoo201bwmk07nh4yc04u) · [D3](https://mozilladatacollective.com/datasets/cmr0mny2b01asns073985z0va) · [D4](https://mozilladatacollective.com/datasets/cmr0moi2k01c0mk07eocv137z) · [D5](https://mozilladatacollective.com/datasets/cmr0motgu01awns07eeeyiv6m)

¹ D1 K1 verified twice — offline simulation **and** a live Prompsit API run (see
the D1 section).

**Definitions.** *Validators* are automated checks, not human reviewers.
**Discrimination check (K1):** a structure-/locale-/resource-blind baseline
scores significantly worse than a structure-aware system (paired bootstrap,
p<0.05). **False-positive check (K2):** validators do not wrongly flag correct
human references (target ~0 %).

## Shared conventions

- **Target languages (9):** `ca, es, fr, it, pt-PT, de, nl, pl, ru` (source
  `en`). D2 is keyed by **locale** (`en_US → ca_ES, es_ES, fr_FR, it_IT, pt_PT,
  de_DE, nl_NL, pl_PL, ru_RU`) because separators/dates/currency are
  underspecified by language alone.
- **Splits:** `test` (scored), `dev` (open set for few-shot/tuning, not
  required), `hidden` (withheld; committed under `private/` in this private
  repo; rebuildable open archives stay untracked).
- **Discrimination check (K1):** a tag-/locale-/resource-blind baseline must be
  statistically separated from the best system on ≥ half the classes
  (paired bootstrap, p<0.05; iteration count is recorded in each K1 report).
  Confirms the benchmark measures the intended behavior.
- **False-positive check (K2):** the validators (automated checks, not human
  reviewers) must not flag clean, correct references. Target ~0 %; all datasets
  at 0.0 %.
- **Annotation status:** all datasets are oracle-validated; human review is not
  required because reference labels are deterministically derivable.
- **Packaging:** each dataset ships `manifest.json`, `dataset.yaml` (MDC card),
  `croissant.json` (Croissant 1.0), `DATASHEET.md` (the per-dataset single source
  of truth), `THIRD_PARTY_NOTICES.md`, `README.md`, `checksums.sha256`, and a
  deterministic `build/` pipeline.

## D1 — inline-asset-integrity

**What it tests:** inline localization assets survive translation **structurally
intact** — HTML/XLIFF markup, software placeholders (`%1$s`, `{0}`), template
variables (`{{name}}`), ICU MessageFormat, inline Markdown, do-not-translate
spans. Scored by 8 binary checks (all must pass).

- **Classes (7):** `xliff`, `html_tag`, `software_placeholder`,
  `template_variable`, `icu_messageformat`, `markdown_inline`,
  `do_not_translate`.
- **Sourcing:** real localization corpora — Chromium, AOSP, Apache OpenOffice,
  Godot, Flutter Gallery, and DSpace (licenses inherited per record); injected
  HTML/Markdown for floor coverage.
- **K1:** **PASS** — a structure-blind baseline is statistically separated from a
  tag-aware system on **7 / 7** classes offline and **6 / 7** on a live run
  (paired bootstrap, p<0.05); ICU is the lone non-separated live class.
- **Datasheet (SSOT):** [../datasets/d1-inline-asset-integrity/DATASHEET.md](../datasets/d1-inline-asset-integrity/DATASHEET.md)
  · **Dir:** `datasets/d1-inline-asset-integrity/`

## D2 — locale-data-integrity

**What it tests:** numeric / date / unit / currency values are **adapted to the
target locale**, not copied through. Oracle is CLDR via
**Babel 2.18.0**.

- **Format track (headline, 5):** `wrong_decimal_separator`, `wrong_grouping`,
  `mis_converted_datetime`, `broken_currency_format`, `wrong_unit_format`
  (localize the unit symbol; value unchanged).
- **Sourcing:** carrier sentences from D1 (human translations); license
  inherited per record. Currency amounts quantized to CLDR fraction digits so the
  surface faithfully renders `semantic.amount`.
- **K1/K2:** **PASS** / 0.0% false positives. Per-class floor ≥400 records (K1
  set); all five headline classes PASS.
- **Datasheet (SSOT):** [../datasets/d2-locale-data-integrity/DATASHEET.md](../datasets/d2-locale-data-integrity/DATASHEET.md)
  · **Dir:** `datasets/d2-locale-data-integrity/`

## D3 — structured-resource-integrity

**What it tests:** in structured i18n resource files, the **skeleton is
preserved and only values are translated** — keys, paths,
and non-value syntax must stay intact.

- **Format profiles (4):** `xml`, `json`, `properties`, `arb`.
- **Classes (6):** `parser_break`, `key_path_translated`, `schema_changed`,
  `value_untranslated`, and the tiered DNT check `nonvalue_modified_literal`
  (Tier-1, letterless tokens, all formats, no signal) + `nonvalue_modified_marked`
  (Tier-2, any alphabetic token incl. acronyms, XML-only via the explicit
  `translatable="false"` marker).
- **Sourcing:** real **AOSP Settings** resources (Apache-2.0, ref `7c598253ff60`).
- **K1/K2:** **PASS** / 0.0% false positives. Per-class floor ≥400 records (K1 set).
- **Datasheet (SSOT):** [../datasets/d3-structured-resource-integrity/DATASHEET.md](../datasets/d3-structured-resource-integrity/DATASHEET.md)
  · **Dir:** `datasets/d3-structured-resource-integrity/`

## D4 — document-structure-integrity

**What it tests:** rich document structure (the DOM/tree) survives translation —
no lost/duplicated nodes, no block reordering, tables and links/images intact,
round-trip safe.

- **Structure profiles:** `html`.
- **Classes (5):** `lost_or_duplicated_node`, `block_order_change`,
  `table_cell_corruption`, `broken_link_image`, `roundtrip_failure`.
- **Sourcing:** templated HTML (headings/list/table/link/image) over D1
  sentences; licenses inherited per segment.
- **K1/K2:** **PASS** / 0.0% false positives. Per-class floor ≥400 records (K1 set).
- **Datasheet (SSOT):** [../datasets/d4-document-structure-integrity/DATASHEET.md](../datasets/d4-document-structure-integrity/DATASHEET.md)
  · **Dir:** `datasets/d4-document-structure-integrity/`

## D5 — linguistic-resource-adherence

**What it tests:** the engine **respects provided linguistic resources**
glossary terms, exact/fuzzy translation-memory matches,
and conflicting guidance handled correctly.

- **Resource profiles (4):** `glossary`, `tm_exact`, `tm_fuzzy`, `conflict`.
- **Classes (6) in 4 tracks:** glossary — `required_term_missing`,
  `forbidden_term_used`, `inconsistent_term`; tm — `approved_tm_ignored`;
  conflict — `conflict_mishandled` (reported apart); quality — `fuzzy_discernment`
  (anti-correlated with adherence). **glossary + tm** are the headline adherence
  tracks; conflict and quality are reported apart. A
  system that cannot consume a given resource is `N/A` for that track (per-system
  applicability), not folded in as 0%.
- **Sourcing:** CLDR terminology (Babel, Unicode license); carrier TM from D1
  sentences.
- **K1/K2:** **PASS** / 0.0% false positives. Per-class floor ≥400 records (K1 set).
- **Datasheet (SSOT):** [../datasets/d5-linguistic-resource-adherence/DATASHEET.md](../datasets/d5-linguistic-resource-adherence/DATASHEET.md)
  · **Dir:** `datasets/d5-linguistic-resource-adherence/`

## See also

- [Prompsit_MDC_Benchmark_Memo.md](Prompsit_MDC_Benchmark_Memo.md) — design
  rationale and the §5.1–5.5 dimension definitions.
- [REVIEW.md](REVIEW.md) — internal review handover (full archives, all splits)
  with the one-page D1–D5 overview built in.
- Per-dataset K1/K2 detail: each dataset's `k1_report.json` / `k2_report.json`
  (D1 also `live_k1_report.json`).
- Per-dataset `DATASHEET.md` and `manifest.json` under each `datasets/<id>/`.
