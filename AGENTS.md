# AGENTS.md

Guidance for AI agents working in this repository.

## What this is

The validators and build pipeline for the Prompsit MT integrity benchmark
(D1-D5). Each dataset scores one integrity dimension of a machine translation:
inline assets (D1), locale data (D2), structured resources (D3), document
structure (D4), and glossary / translation-memory adherence (D5). The dataset
**content** lives on Mozilla Data Collective; this repository holds the **code**.

## Repo map

- `datasets/<id>/build/` - validators and the deterministic build pipeline:
  - the scoring functions; entry point `score_item(...)`. The module is
    `validators.py` for D1/D2, `resources.py` (D3), `documents.py` (D4),
    `lingres.py` (D5).
  - `build_dataset.py`, `make_contrastive.py`, `k1_discrimination.py`,
    `k2_false_positives.py`, `validate.py` - the pipeline.
  - `requirements.txt` - dependencies for that dataset.
- `datasets/<id>/{manifest.json, croissant.json, DATASHEET.md}` - metadata; the
  DATASHEET is the per-dataset source of truth.
- `datasets/<id>/data/` - the open layer. NOT shipped here; download it from the
  dataset's MDC page (linked in each DATASHEET) and drop the files in.
- `docs/MDC_Dataset_Registry.md` - the catalog and single source of truth.

## What is and is not in this repo

- After you download from MDC: `data/dev.jsonl` (with reference labels),
  `data/test.input.jsonl` (inputs only), `data/contrastive.dev.jsonl`.
- Never here: the scored test references (`test.ref.jsonl`) and the hidden split.
  They are withheld so evaluation stays contamination-free; official scoring on
  those splits is done by Prompsit (info@prompsit.com).

## Score an MT output (the core task)

The scoring entry point is `score_item(...)`, exported from each dataset's
validator module (`validators.py` for D1/D2; `resources.py`, `documents.py`,
`lingres.py` for D3, D4, D5). You supply only your candidate translation; the
benchmark item comes from the dataset. It returns a dict of per-check booleans
plus an overall `"pass"`. The checks are structural and reference-light — no
reference translation of your own is needed. The call shape differs by dimension:

- **D1:** `score_item(source, hypothesis)` - reads the expected inline assets
  straight from the source markup.
- **D2-D5:** `score_item(record, hypothesis)` - `record` is one line from
  `dev.jsonl`; the expected locale forms / resource structure / required terms
  live in it, so pair each record with your translation of that item.

```python
import sys, json
sys.path.insert(0, "datasets/d1-inline-asset-integrity/build")
from validators import score_item
result = score_item(source_string, mt_output)              # D1: {"pass": bool, ...}

sys.path.insert(0, "datasets/d5-linguistic-resource-adherence/build")
from lingres import score_item as score_d5
rec = json.loads(next(open("datasets/d5-linguistic-resource-adherence/data/dev.jsonl",
                           encoding="utf-8")))
result = score_d5(rec, mt_output)                          # D2-D5: pass the record
```

Read the `score_item` definition in that dataset's module for the exact contract
before calling it (D1 and D2 both name their module `validators`, so import them
in separate processes if you score both).

To self-check a system on a whole split, run it through `score_item` for every
record in `data/dev.jsonl` (the open split, which carries reference labels) and
aggregate the `"pass"` rate.

## Reproduce a dataset

Deterministic and seeded. From the dataset directory:

```
pip install -r datasets/<id>/build/requirements.txt
python datasets/<id>/build/build_dataset.py   # regenerate records from references
python datasets/<id>/build/validate.py        # prints a JSON verdict (PASS/FAIL)
```

`validate.py` checks the schema, the nine-language balance, split partitioning,
that inputs carry no reference labels, and that every reference passes its own
validators (self-consistency).

## Two acceptance checks (per dataset)

- **Discrimination check (K1):** a structure-blind baseline must score
  significantly worse than a structure-aware system, so the benchmark measures the
  behaviour it claims to.
- **False-positive check (K2):** the validators must not flag correct human
  references (target near 0%).

## Conventions

- Python >= 3.10; each dataset pins its own `build/requirements.txt`.
- Build steps are deterministic and seeded; packaged output is bit-identical.
- Keep files ASCII where the surrounding files are ASCII.
- Do not commit dataset content (`data/`) or any archive; fetch data from MDC.

## Getting an official evaluation

The public validators let you self-check on the open split. For an independent,
contamination-free evaluation on the withheld test and hidden splits, contact
Prompsit at info@prompsit.com.
