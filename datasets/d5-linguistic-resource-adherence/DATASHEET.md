# D5 - Linguistic-resource Adherence (datasheet)

**Version** 1.0 | **Schema** 0.2 | **Scoring rule:** the output must use the prescribed target term from the supplied glossary or translation memory

Professional translation workflows hand the engine linguistic resources along
with the text: a glossary that prescribes terminology and a translation memory
(TM) of approved past translations. This dataset tests whether machine
translation follows those resources: the prescribed glossary term is used (and
used consistently), banned synonyms stay out, an exact TM match is reused, and
when the glossary and the TM disagree, the glossary wins. Each source string is
paired with human translations into nine languages; glossary terms are CLDR
display names (territories, languages, currencies) rendered with Babel, and the
TM sentences are human translations shared with the D1 dataset.

The translations are human, drawn from real localization catalogs. The
labels on them (asset inventories, positions, expected forms) are derived
automatically and deterministically from the source, so they are reproducible
end to end; the false-positive check below verifies they never flag a correct
human translation. Every
released reference passes the scoring script (4,590/4,590).

## How to use this dataset

1. Download the open layer from this page and unpack it: `data/dev.jsonl`
   (inputs plus reference translations), `data/test.input.jsonl` (inputs
   only), `data/contrastive.dev.jsonl`.
2. Translate the source strings with the MT system you want to evaluate,
   supplying it the glossary entry or TM match carried by each record -
   consuming those resources is exactly what this dataset measures.
3. Score the outputs with the open-source scoring script - `score_item(...)`
   in https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d5-linguistic-resource-adherence/build
   (`lingres.py`).

To verify your harness first, score the dev references themselves: they must
pass 100%.

## Task and scoring

The task: translate each source string from English into the target language
using the glossary entry and TM match supplied with the record.

Scoring is fully automatic; no human judges are involved. For every record, a
deterministic scoring script (open-source:
https://github.com/Prompsit/prompsit-mdc/tree/main/datasets/d5-linguistic-resource-adherence/build)
inspects the system output and reports which error categories occur (see the
Error categories table below). A record **passes** if no error category occurs.
The score of a system is its **pass rate**: the fraction of records that pass,
reported overall and per error category. The checks compare the term slot in
the output against the glossary or TM entry supplied with the record, so no
reference translation of the output is needed.

The scoring entry point is `score_item(...)` in `lingres.py` there; the `README` and `AGENTS.md` at the repository root
walk through scoring your own outputs.

The rule is uniform across records: the term slot in the output must contain
the prescribed target term (`ref_term`). D5 evaluates systems and pipelines
that can consume supplied resources - a CAT/TMS pipeline, a glossary-aware LLM,
or an explicit wrapper. Engines that cannot accept external resources are out
of scope and reported `not_applicable`.

## MDC technical summary

- Domain: machine-translation quality evaluation for adherence to supplied
  linguistic resources - glossary terminology and translation-memory matches.
- Size: 4,590 records; the open archive contains the dev split (with
  references), the test inputs, the contrastive pairs, README, this datasheet,
  third-party notices, manifest, and Croissant metadata.
- Structure: JSONL records with source and target text, target language,
  resource profile, glossary and TM payloads, the prescribed term (`ref_term`),
  forbidden terms, expected invariants, error-category tags, split, and
  provenance.
- License: CC-BY-4.0 open layer; upstream attributions in
  `THIRD_PARTY_NOTICES.md`.
- Dataset on MDC (download the open layer): https://mozilladatacollective.com/datasets/cmr0motgu01awns07eeeyiv6m

## Independent evaluation

The test references and the hidden split are withheld, so a score on those
splits reflects performance on unseen inputs rather than answers a system could
have memorised. For an independent evaluation of an MT or LLM system on the
withheld splits, contact Prompsit at info@prompsit.com.

## Contents and splits

| Split | File | Records | What it contains |
|---|---|---|---|
| Open dev | `data/dev.jsonl` | 459 | inputs plus the reference translation and labels |
| Test inputs | `data/test.input.jsonl` | 3,213 | inputs only; references withheld |
| Test references | `data/test.ref.jsonl` | 3,213 | withheld, retained by Prompsit |
| Hidden | - | 918 | never distributed |
| Contrastive | `data/contrastive.dev.jsonl` | 729 | verification records for (correct, damaged) minimal pairs; the damaged variants are regenerated bit-identically from the dev split by the open build pipeline, and each pair is separated by the scoring script |

510 sources x 9 languages = **4,590 records**. Split ~10% dev / 70% test / 20%
hidden, stratified by resource profile and partitioned by `item_id`, so a
source and its nine translations never cross splits.

No training set is shipped. The dev split is a small labelled set for optional
few-shot prompting or sanity checks; it is not required to run the benchmark.

## Languages

`en` into `ca, es, fr, it, pt-PT, de, nl, pl, ru`. Every source is present in
all nine languages with the same resource profile, so per-language scores are
directly comparable.

## Error categories

Every record is tagged with the error categories it can expose; the scoring
script detects each category with a dedicated automated check. Severity is
reported alongside a failure for error analysis; it does not change the
pass/fail rule.

Categories are grouped by resource type: glossary, TM, and a conflict case
where the glossary takes precedence over the TM. Categories are reported
separately and never collapsed into one number; each record names its group in
a `track` field. `fuzzy_discernment` is the one category that rewards not
reusing a match: copying the stale term from an 85% fuzzy match is the error.

| Error category | What it means | Severity | Records |
|---|---|---|---|
| `required_term_missing` | the prescribed term is absent from the output | Major | 1,080 |
| `forbidden_term_used` | a banned synonym appears anywhere in the output | Major | 1,080 |
| `inconsistent_term` | the term is rendered two different ways in one output | Major | 1,080 |
| `approved_tm_ignored` | an exact TM match was not reused | Major | 864 |
| `conflict_mishandled` | when the glossary and the TM disagree, the glossary must win | Major | 864 |
| `fuzzy_discernment` | a stale term was copied from a fuzzy TM match instead of using the current glossary term | Major | 864 |

At least 400 records per error category (our minimum for a reliable
per-category estimate). The source profile of each category - the record kind
that exercises it - is: `required_term_missing`, `forbidden_term_used` and
`inconsistent_term` come from glossary records; `approved_tm_ignored` from
exact-TM records; `fuzzy_discernment` from fuzzy-TM records;
`conflict_mishandled` from conflict records. The dev split contains every
profile.

## Sample records

Real records from the open dev split, truncated for width. Angle brackets in
markup are shown as ⟨ ⟩ because this platform strips raw HTML-like tags; the
data files contain the ordinary characters.

| item_id | target | source text | target text | resource kind + prescribed term | error categories |
|---|---|---|---|---|---|
| d5-000000 | ca | Y: %1 M: %2 D: %3 H: %4 M: %5 S: %6 [world \| world] | A: %1 M: %2 D: %3 H: %4 M: %5 S: %6 [Món \| Món] | glossary: Món (forbidden: Amèrica del Nord) | required_term_missing, forbidden_term_used, inconsistent_term |
| d5-000154 | ca | at ⟨xliff:g id="time" example="2:33 am"⟩**%s**⟨/xliff:g⟩ [Bosnian] | a les ⟨xliff:g id="TIME"⟩**%s**⟨/xliff:g⟩ [bosnià] | tm_exact: bosnià (100% match) | approved_tm_ignored |
| d5-000270 | ca | ⟨xliff:g id="count"⟩`%d`⟨/xliff:g⟩d [Manchu] | ⟨xliff:g id="COUNT"⟩`%d`⟨/xliff:g⟩ d [manxú] | tm_fuzzy: manxú (the 85% match holds stale "malai") | fuzzy_discernment |
| d5-000395 | ca | Revoke access to Modes for ⟨xliff:g id="app" example="Tasker"⟩%1`$s`⟨/xliff:g⟩? [Argentine Peso] | Vols revocar l'accés als modes per a ⟨xliff:g id="APP"⟩%1`$s`⟨/xliff:g⟩? [peso argentí] | conflict: peso argentí (the TM offers "dòlar australià") | conflict_mishandled |

## Source data and licenses

| Resource | Source | License |
|---|---|---|
| Glossary terminology | CLDR display names (territories / languages / currencies) via Babel | Unicode-3.0 |
| TM sentences | human translations shared with the D1 dataset | per-segment (Apache-2.0 / BSD-3-Clause / MIT, inherited) |

Glossary terms come from CLDR; the TM sentences are human translations shared
with the D1 dataset. The term sits in a neutral `[...]` slot of a
human-translated sentence. No synthetic translations are used. All upstream
licenses are permissive and compatible with a CC-BY-4.0 open layer; upstream
attribution notices accompany the release in `THIRD_PARTY_NOTICES.md`.

## Construction method

1. **Term selection**: glossary terms are CLDR display names (territories,
   languages, currencies), rendered per target language with Babel 2.18.0.
   Each entry pairs the English display name with the prescribed
   target-language form (`ref_term`); the forbidden terms are other display
   names from the same CLDR category in the same language.
2. **Sentence selection**: sentence pairs are human translations reused from
   the D1 dataset (license inherited per segment). A bracketed `[...]` slot in
   the sentence holds the English term in the source and the prescribed term in
   the reference. In glossary records the slot holds the term twice
   (`[world | world]`), so the consistency check has two positions to compare.
3. **Resource payloads**: each record ships the resources the system must
   consume. Glossary records supply a glossary entry (required term plus
   forbidden synonyms). Exact-TM records supply a 100% match whose reuse is
   required. Fuzzy-TM records supply an 85% match whose target holds a stale
   term; copying it is the error. Conflict records supply a glossary entry and
   a 100% TM match that disagree; the glossary must win.
4. **Splits**: ~10/70/20, stratified by resource profile, partitioned by
   `item_id`.

## Dataset-quality checks

Two checks are run on the dataset itself before release. They validate the
benchmark, not any particular MT system.

- **Discrimination check (K1):** can the dataset separate systems that follow
  the supplied resources from systems that do not? Contrasting baseline systems
  are scored with the real scoring script, and the damaging baselines must come
  out significantly worse (paired bootstrap, p-value below 0.05 - that is, the gap is too large to be chance).
- **False-positive check (K2):** does the scoring script ever flag a correct
  human translation as an error? The released references and legal variants of
  them are rescored; the target is 0%.

| Check | Result |
|---|---|
| Discrimination (K1) | **PASS** - resource-ignoring baselines score 0% where a resource-aware system scores 100%, separated on 6 of 6 error categories (paired bootstrap p-value below 0.05); targeted violators (a glossary violator at 70.6%, a fuzzy-match copier at 76.5%) are caught on their target categories. The baselines are simulated corruption operators scored with the real scoring script. |
| False positives (K2) | **PASS** - 0.0% flips over 13,770 legal variants |
| Reference self-check | 4,590/4,590 - every released reference passes the scoring script |
| Croissant 1.0 | `croissant.json`, mlcroissant-validated |

## Reproducibility

The build is deterministic and seeded; rebuilding produces a bit-identical
package, and `checksums.sha256` (shipped in the archive) verifies a download.
The glossary terms come from public CLDR, but the TM sentences are shared
with D1 and largely withheld, so the open layer alone does not regenerate
the test and hidden splits.

The scoring script and the full build pipeline are open-source at
https://github.com/Prompsit/prompsit-mdc - the dataset content itself is
distributed here on MDC.

## Scope boundaries

- Term adherence is checked as an exact surface match of the prescribed term
  (`ref_term`).
- The term sits in a neutral `[...]` slot of a human-translated sentence; the
  surrounding prose is not scored.
- The baselines are simulated corruption operators; results from a live MT
  engine that consumes the resources are not included in this package.

## Related work

This datasheet follows the structure proposed in Datasheets for Datasets
(Gebru et al., https://arxiv.org/abs/1803.09010). The error categories map to
the locale, terminology and markup branches of the MQM error typology
(https://themqm.org/), turned from human
annotation tags into automated checks.

IFMTBench (https://arxiv.org/abs/2605.28218) scores joint
constraint-following with a single multiplicative index; this dataset
isolates glossary and TM adherence as per-category pass rates. Bulte &
Tezcan (ACL 2019, https://aclanthology.org/P19-1175/) reuse fuzzy TM matches
to improve MT output; here, adherence to the supplied fuzzy match is what
gets measured.
