# Prompsit MT Integrity Benchmark

> AI agents: see [AGENTS.md](AGENTS.md) for how to run the validators and score an MT output, or the [`evaluate-mt-integrity`](.agents/skills/evaluate-mt-integrity/SKILL.md) skill for a step-by-step download-and-score walkthrough.

A machine-translation *integrity* benchmark: it measures whether a translation
still works in production, not only whether it reads well. Does the output keep
inline tags and placeholders intact, render numbers and dates in the target
locale, keep resource files parsing, preserve document structure, and honour a
supplied glossary or translation memory? Five dimensions (D1-D5), English into
nine languages (ca, es, fr, it, pt-PT, de, nl, pl, ru).

Such breakages are invisible to fluency metrics: BLEU and COMET score surface
similarity, so an output can read perfectly and still drop a placeholder,
mis-format a date, or break a resource file[^1][^2]. The error categories align
with the formatting, markup and terminology branches of MQM[^3].

This repository holds the **validators and build pipeline** that score those five
dimensions. The dataset content is distributed on Mozilla Data Collective; the
scored test references and a hidden split stay with Prompsit, so evaluation is
contamination-free.

## The five dimensions

| ID | Dimension | What it checks |
|----|-----------|----------------|
| D1 | Inline Asset Integrity | inline tags, placeholders, ICU, Markdown and do-not-translate spans survive |
| D2 | Locale-data Integrity | numbers, dates, currency and units render in the target locale |
| D3 | Structured-resource Integrity | XML/JSON/.properties/ARB keep their keys and schema; only values are translated |
| D4 | Document-structure Integrity | HTML tree, tables and links are preserved and the output round-trips |
| D5 | Linguistic-resource Adherence | supplied glossary terms and translation-memory matches are respected |

The canonical catalog (versions, sizes, classes, sourcing and check status) is the
single source of truth:

➡️ **[docs/MDC_Dataset_Registry.md](docs/MDC_Dataset_Registry.md)** · design
rationale and the per-dimension definitions in
**[docs/Prompsit_MDC_Benchmark_Memo.md](docs/Prompsit_MDC_Benchmark_Memo.md)**.

## Datasets on Mozilla Data Collective

- [Prompsit D1 - Inline Asset Integrity](https://mozilladatacollective.com/datasets/cmr0mng9z01bsmk07cuqltz81)
- [Prompsit D2 - Locale-data Integrity](https://mozilladatacollective.com/datasets/cmr0mnoo201bwmk07nh4yc04u)
- [Prompsit D3 - Structured-resource Integrity](https://mozilladatacollective.com/datasets/cmr0mny2b01asns073985z0va)
- [Prompsit D4 - Document-structure Integrity](https://mozilladatacollective.com/datasets/cmr0moi2k01c0mk07eocv137z)
- [Prompsit D5 - Linguistic-resource Adherence](https://mozilladatacollective.com/datasets/cmr0motgu01awns07eeeyiv6m)

The dataset **content** (open layer: dev reference + test inputs + a contrastive
pack) is downloaded from MDC. This repository ships the **code** (validators and
build pipeline) and the metadata and docs only. To run the validators, fetch the
open layer from MDC into each dataset's `data/`.

## Independent evaluation

The open layer lets anyone self-check an MT system. The scored test references and
a hidden split stay with Prompsit, so a system cannot be tuned to them and a score
reflects performance on unseen inputs rather than memorised answers.

Prompsit built these benchmarks as part of its work on MT quality evaluation. For
an independent, contamination-free evaluation of your MT or LLM translation system
on these integrity dimensions, contact info@prompsit.com.

## How scoring works

Each dataset ships a deterministic scoring script under `datasets/<id>/build/`,
next to the dataset-quality checks (`k1_discrimination.py`,
`k2_false_positives.py`) and an integrity check (`validate.py`). For every
record, the scoring script reports which error categories occur in the system
output; a record passes when none does, and a system's score is its pass rate,
overall and per error category - no human judgement in the loop. Two checks
validate every dataset before release:

- **Discrimination check (K1):** a structure-blind baseline must score
  significantly worse than a structure-aware system, so the benchmark measures the
  behaviour it claims to.
- **False-positive check (K2):** the validators must not flag correct human
  references (target near 0%).

The build is deterministic and seeded, and each archive ships
`checksums.sha256` for download verification. A full rebuild starts from the
reference translations, so the open layer alone does not regenerate the
withheld splits - each DATASHEET states what is reproducible for that dataset.
To sanity-check your setup, score the dev references: they must pass 100%.

```
pip install "Babel==2.18.0"   # needed for D2/D5 only; D1/D3/D4 use the stdlib
# then score data/dev.jsonl references with score_item - see AGENTS.md
```

## License

- **Code** (scoring scripts, build pipeline, tooling): [MPL-2.0](LICENSE).
- **Dataset content** (the open layer): distributed on Mozilla Data Collective
  under **CC-BY-4.0**; not hosted in this repository.
- **Upstream sources**: each dataset's `THIRD_PARTY_NOTICES.md` records per-corpus
  attribution (Apache-2.0 / BSD-3-Clause / MIT) and the Unicode CLDR terms.

## References

[^1]: Mathur et al., *Tangled Up in BLEU: Reevaluating the Evaluation of Automatic Machine Translation Evaluation Metrics*, ACL 2020. https://aclanthology.org/2020.acl-main.448/
[^2]: Challenge sets showing metric failures on targeted error phenomena: ACES (Amrhein et al., WMT 2022, https://aclanthology.org/2022.wmt-1.44/) and DEMETR (Karpinska et al., EMNLP 2022, https://aclanthology.org/2022.emnlp-main.649/).
[^3]: MQM error typology. https://themqm.org/
