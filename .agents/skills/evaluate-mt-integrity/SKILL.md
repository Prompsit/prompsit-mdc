---
name: evaluate-mt-integrity
description: >
  Score a machine-translation output against the Prompsit MT Integrity Benchmark
  using the structural validators in this repository (datasets D1-D5; data on
  Mozilla Data Collective). Use when the user wants to run the validators on an MT
  hypothesis, self-check a system on the open split, or download a benchmark
  dataset. Reference-light: you supply only your MT output, and the validators
  judge it against the benchmark item — no MT vendor and no reference translation
  of your own required.
---

# Score an MT output with the Prompsit MT Integrity Benchmark validators

Follow the steps **in order**. Each step states an **Action**, the exact command
or code to **Run**, and the **Expected result**. Every Expected result below is
the actual output observed on a fresh `git clone` of the public repo — if your
output differs, stop and check the note in that step before continuing.

The five datasets, their validator module (it is `validators.py` only for D1/D2),
and their MDC download page:

| Dataset | Dimension | Validator module (this repo) | Data — MDC page |
| --- | --- | --- | --- |
| D1 | inline assets | `datasets/d1-inline-asset-integrity/build/validators.py` | https://mozilladatacollective.com/datasets/cmr0mng9z01bsmk07cuqltz81 |
| D2 | locale data | `datasets/d2-locale-data-integrity/build/validators.py` | https://mozilladatacollective.com/datasets/cmr0mnoo201bwmk07nh4yc04u |
| D3 | structured resources | `datasets/d3-structured-resource-integrity/build/resources.py` | https://mozilladatacollective.com/datasets/cmr0mny2b01asns073985z0va |
| D4 | document structure | `datasets/d4-document-structure-integrity/build/documents.py` | https://mozilladatacollective.com/datasets/cmr0moi2k01c0mk07eocv137z |
| D5 | linguistic-resource adherence | `datasets/d5-linguistic-resource-adherence/build/lingres.py` | https://mozilladatacollective.com/datasets/cmr0motgu01awns07eeeyiv6m |

The MDC dataset id is the last path segment of each link (D1 =
`cmr0mng9z01bsmk07cuqltz81`, etc.); the SDK in Step 5 downloads by that id.

---

## Step 1 — Clone the repository

- **Action:** get the code; the validators live in `datasets/<id>/build/`.
- **Run:**
  ```bash
  git clone https://github.com/Prompsit/prompsit-mdc.git
  cd prompsit-mdc
  ```
- **Expected result:** `datasets/` contains `d1-inline-asset-integrity` through
  `d5-linguistic-resource-adherence`. There is **no** `datasets/<id>/data/`
  directory yet — the data is not shipped in git; you fetch it from MDC in Step 5.

## Step 2 — Install scoring dependencies

- **Action:** the D1/D3/D4 validators are **stdlib-only** (nothing to install);
  D2 and D5 need **Babel**. The `mlcroissant` line in each `build/requirements.txt`
  is only for *rebuilding* metadata, not for scoring — skip it here.
- **Run:**
  ```bash
  python --version                 # must be >= 3.11
  pip install "Babel==2.18.0"      # only needed for D2 and D5
  ```
- **Expected result:** `python -c "import babel"` exits without error. Scoring
  D1/D3/D4 needs no third-party package at all.

## Step 3 — Score one MT output (no data, no MDC needed) — D1

- **Action:** import D1's `score_item(source, hypothesis)`. It reads the expected
  inline assets straight from the source, so it needs no dataset and no reference.
- **Run:**
  ```python
  import sys
  sys.path.insert(0, "datasets/d1-inline-asset-integrity/build")
  from validators import score_item

  source = "Click <b>here</b> to continue."
  good   = "Haz clic <b>aquí</b> para continuar."   # keeps the <b> tags
  bad    = "Haz clic aquí para continuar."           # dropped the tags
  print(score_item(source, good))
  print(score_item(source, bad))
  ```
- **Expected result:**
  ```
  {'inventory': True,  'placeholder_syntax': True, ..., 'pass': True}
  {'inventory': False, 'placeholder_syntax': True, ..., 'pass': False}
  ```
  A faithful translation passes; dropping the tags fails on `inventory`, so
  `pass` is False.

## Step 4 — Get an MDC API key and accept each dataset's terms

- **Action:** create an API key at `/profile/credentials` on MDC and put it in a
  `.env` file as `MDC_API_KEY=...` (never commit it). Then open each dataset's
  MDC page (links in the table above) and accept its Terms & Conditions. This is
  per dataset and can only be done in the web UI.
- **Run:** (web) accept terms; (shell) make the key available:
  ```bash
  export MDC_API_KEY=...            # or load the .env with python-dotenv
  ```
- **Expected result:** access is granted for that dataset. **If you skip the
  terms step**, Step 5 fails with exactly:
  ```
  PermissionError: Access denied. ... Terms must be accepted before downloading:
  https://mozilladatacollective.com/datasets/<id>
  ```

## Step 5 — Download and unpack the open layer

- **Action:** install the SDK and download by id. `download_dataset` returns the
  path to a **`.tar.gz`** — it does **not** auto-extract, and `load_dataset` is
  **not** supported for these datasets (it raises `RuntimeError: ... not supported
  by load_dataset yet`). So extract the archive's `data/` members yourself.
- **Run:**
  ```bash
  pip install datacollective
  ```
  ```python
  import tarfile, pathlib
  from datacollective import download_dataset

  ID   = "cmr0mng9z01bsmk07cuqltz81"                     # D1 (see the table)
  DEST = pathlib.Path("datasets/d1-inline-asset-integrity")

  archive = download_dataset(ID, download_directory="_mdc_downloads")  # -> Path to a .tar.gz
  with tarfile.open(archive) as tar:
      members = [m for m in tar.getmembers() if m.name.startswith("data/")]
      tar.extractall(DEST, members=members, filter="data")
  print(archive.name)
  print(sorted(p.name for p in (DEST / "data").iterdir()))
  ```
- **Expected result:**
  ```
  prompsit-d1-inline-asset-integrity-<hash>.tar.gz
  ['contrastive.dev.jsonl', 'dev.jsonl', 'test.input.jsonl']
  ```
  (The archive also carries `manifest.json`, `croissant.json`, `DATASHEET.md`,
  `README.md`, `THIRD_PARTY_NOTICES.md`, which the clone already has.)

## Step 6 — Sanity-check the validators (self-contained)

- **Action:** with `dev.jsonl` in place, score its shipped human `reference`
  (must pass) and a corrupted copy (must fail). Shown for D1.
- **Run:**
  ```python
  import sys, json, re
  sys.path.insert(0, "datasets/d1-inline-asset-integrity/build")
  from validators import score_item

  rec = json.loads(next(open("datasets/d1-inline-asset-integrity/data/dev.jsonl",
                             encoding="utf-8")))
  src = rec["source"]
  print(score_item(src, rec["reference"])["pass"])              # -> True
  broken = re.sub(r"<[^>]+>", "", rec["reference"], count=1)
  print(score_item(src, broken)["pass"])                        # -> False
  ```
- **Expected result:** `True` then `False`. The reference passes every check; the
  corrupted copy fails on `inventory`.

## Step 7 — Score against D2-D5 (record form)

- **Action:** D2-D5 take the whole benchmark **record** (one line of `dev.jsonl`),
  because the expected locale forms / resource structure / required terms live in
  the record, not in the plain sentence. Import that dataset's module
  (`validators` / `resources` / `documents` / `lingres`) and call
  `score_item(record, hypothesis)`. Shown for D5 (download D5 first, as in Step 5).
- **Run:**
  ```python
  import sys, json
  sys.path.insert(0, "datasets/d5-linguistic-resource-adherence/build")
  from lingres import score_item

  rec = json.loads(next(open("datasets/d5-linguistic-resource-adherence/data/dev.jsonl",
                             encoding="utf-8")))
  print(score_item(rec, rec["reference"]))
  ```
- **Expected result:**
  ```
  {'term_present': True, 'term_consistent': True, 'term_correct': True,
   'forbidden_absent': True, 'pass': True, ...}
  ```
  D1 and D2 both name their module `validators`, so if you score both in one run,
  import them in separate processes to avoid a name clash.

## Step 8 — Self-check a whole system

- **Action:** for each dev record, translate its source with the system under
  test, score the output, and aggregate the pass rate. (Feeding the reference
  itself shows the 100% ceiling; your MT system will score lower.)
- **Run:**
  ```python
  import sys, json
  sys.path.insert(0, "datasets/d1-inline-asset-integrity/build")
  from validators import score_item

  passed = total = 0
  with open("datasets/d1-inline-asset-integrity/data/dev.jsonl", encoding="utf-8") as f:
      for line in f:
          rec = json.loads(line)
          hyp = my_mt_system(rec["source"], rec["target_lang"])   # your system
          passed += score_item(rec["source"], hyp)["pass"]        # D2-D5: score_item(rec, hyp)
          total += 1
  print(f"D1 dev pass rate: {passed}/{total}")
  ```
- **Expected result:** a line like `D1 dev pass rate: 639/639` when you feed the
  shipped references (the D1 dev split has 639 records; references pass 100%, which is
  the K2 property below). Substitute your own system in `my_mt_system` to measure
  it — the rate will be lower.

## Step 9 — Interpret the results

- The test inputs (`test.input.jsonl`) are open but their references are withheld,
  so a self-computed **test** score is not comparable across systems — iterate on
  the open `dev` split, and request an official run for a citable number.
- **Discrimination check (K1):** a structure-blind baseline scores significantly
  worse than a structure-aware system, so the benchmark measures what it claims.
- **False-positive check (K2):** the validators do not flag correct human
  references (Step 8 showed 639/639 for D1 dev).
- For an independent, contamination-free evaluation on the withheld test and
  hidden splits, contact Prompsit at info@prompsit.com.

## Generating MT outputs (any system)

The validators are vendor-neutral — any MT system works, including your own. If
you use the Prompsit CLI, its `prompsit-translate` and `prompsit-score` skills
wire "translate, then score" together for you; that is the natural home for a
hosted translate-then-evaluate loop and is kept separate from this neutral
benchmark.

## More

- `AGENTS.md` (repo root) - orientation and the scoring contract.
- `datasets/<id>/DATASHEET.md` - per-dataset source of truth and MDC link.
- `docs/MDC_Dataset_Registry.md` - the full catalog.
