# The Silent Tax: How Typos Reshape Reasoning in Thinking LLMs

Code, results and report for our NLP course project (Tel Aviv University, 2025/26):
Shiran Hamami, Dolev Abudi, Ron Shtricker, Ido Azoulay.

We inject keyboard typos into math and science questions and measure how a
reasoning model copes. Two factors are varied independently:

- **typo rate** r ∈ {25, 50, 75}% of the eligible words of a question, and
- **real-word ratio** ρ ∈ {10, 40, 70}%, the target share of typos that form another
  valid English word (`sum → sun`) rather than a non-word (`triangle → trianlge`).

Within one rate the same words of the same question are corrupted at every ρ, so
comparisons across ρ are paired. The subject model is DeepSeek-R1-Distill-Qwen-7B
(temperature 0.6, top-p 0.95, one sample per question) on the first 500 questions
of GSM8K, MATH-500 and ARC-Challenge, clean plus the 3 × 3 grid. On GSM8K we also
test three mitigations: a typo warning, rewrite-the-question-first, and an external
spell checker. We measure accuracy and flips, reasoning length, self-doubt markers,
how each corrupted word is handled in the reasoning, and LLM-judge scores. The
report is [`report/report.pdf`](report/report.pdf).

## Repository

```
data_creation/   build the typo datasets
  generate_variants.py   datasets x (r, rho) grid, optional push to the Hub
  typo_pipeline.py       controlled real-word typo injection for one question
  keyboard_typos.py      QWERTY single-edit typo generator
inference/       run the subject model
  run_typo_api.py        generations through the Hugging Face router
  score.py               answer extraction and correctness
  repair_dropped.py      remove cut-off streams so they can be regenerated
  rerun_manifest.json    every row regenerated that way
  api_smoke.py           one-request check of token, router and model
analysis/        turn generations into tables
  run_all.py             every module below for one run or all runs
  accuracy_flips.py  reasoning_length.py  self_doubt.py  repair_wordlevel.py
  real_word_effect.py  spellcheck_recovery.py  corruption_stats.py
  llm_judge.py           LLM-judge scores (calls an API; run separately)
  download_data.py       fetch the published generations and judge scores
  data_manifest.json     pinned Hub revision and sha256 of every data file
  common.py              shared loading, scoring and statistics
results/<run>/   the analysis tables (CSV) behind every number in the report
report/          report.tex, make_assets.py, generated figures/ and tables/,
                 numbers.txt (every number the prose quotes, with its source)
```

A *run* is one set of generations: `gsm8k`, `math500`, `arc` (main grid) and
`gsm8k_warn`, `gsm8k_rewrite`, `gsm8k_spellcheck` (mitigations). Each run has 10
configurations, `clean` and `typo<r>_real<rho>`.

## Data

| What | Where |
|---|---|
| Typo datasets | [`idoazou/gsm8k-typos`](https://huggingface.co/datasets/idoazou/gsm8k-typos), [`idoazou/math500-typos`](https://huggingface.co/datasets/idoazou/math500-typos), [`idoazou/arc-typos`](https://huggingface.co/datasets/idoazou/arc-typos) (configs `clean`, `rate<r>_real<rho>`) |
| Model generations and judge scores | [`Dolevabudi/silent-tax-results`](https://huggingface.co/datasets/Dolevabudi/silent-tax-results) (`raw/<run>/`, `judge/`) |

Everything is public. Downloads go to `data/`, which is not committed.

## Setup

Python 3.14. All commands run from the repository root.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The NLTK word list is downloaded automatically on first use. Inference and the
judge call the Hugging Face router and need a token with the "Make calls to
Inference Providers" permission: `export HF_TOKEN=hf_...`. Building the PDF needs
a TeX distribution with `pdflatex` and `bibtex` (tested with TeX Live 2026); the
ACL template typesets in Times through the `times` package.

## Reproducing the results

Every stage can start from the published output of the previous one; steps 1, 2
and a fresh judge run cost API credits or time and can be skipped by downloading
(step 3).

**1. Typo datasets** (deterministic: seed 42, row *i* uses seed 42 + *i*)

```bash
python data_creation/generate_variants.py --clean     # the clean configs
python data_creation/generate_variants.py             # 3 datasets x 9 configs -> data/typo_variants/
python data_creation/generate_variants.py --datasets arc --subset 20   # quick check
```

`--push --namespace <hf-user>` publishes them. The published datasets hold all
1,319 GSM8K and 500 MATH-500 test questions and the first 500 four-option
ARC-Challenge test questions; the runs use the first 500 of each.

**2. Generations** (sampling at temperature 0.6: a new run gives new samples, not the paper's)

```bash
python inference/api_smoke.py
python inference/run_typo_api.py --dataset gsm8k   --variant both --limit 500   # -> data/raw/gsm8k/
python inference/run_typo_api.py --dataset math500 --variant both --limit 500
python inference/run_typo_api.py --dataset arc     --variant both --limit 500
for fix in warn rewrite spellcheck; do
  python inference/run_typo_api.py --dataset gsm8k --variant both --limit 500 --fix $fix
done
```

The generation cap defaults to 20,000 tokens for GSM8K and 17,000 for MATH-500
and ARC. Interrupted runs resume where they stopped. Add `--limit 5` for a smoke
test (a few cents).

**3. Or download the paper's generations and judge scores**

```bash
python analysis/download_data.py --all       # ~510 MB, checked against data_manifest.json
```

**4. Analysis tables**

```bash
python analysis/run_all.py --all             # -> results/<run>/*.csv
```

**5. LLM-judge tables** (from the stored scores; no API calls)

```bash
for run in gsm8k math500 arc; do
  NLP_RUN=$run python analysis/llm_judge.py --all --report-only
done
```

Dropping `--report-only` calls the judge (Llama-3.3-70B-Instruct, temperature 0)
for every answered trace that has no stored score, and adds the new scores to the
stored ones. The router may serve a different provider than in August 2026, so
mixing old and new scores is not recommended: for a fresh judge run, pin a
provider and start an empty cache, e.g.
`JUDGE_MODEL=meta-llama/Llama-3.3-70B-Instruct:<provider> NLP_RUN=gsm8k python analysis/llm_judge.py --all --cache data/judge/new_gsm8k.jsonl`.

**6. Report**

```bash
python report/make_assets.py                 # figures/, tables/, numbers.txt
cd report && pdflatex report && bibtex report && pdflatex report && pdflatex report
```

Starting from step 3, steps 4, 5 and 6 regenerate every committed table, figure
and number exactly.

## Method notes

- **Typo generator.** `keyboard_typos.py` is a small reimplementation of the four
  edit operations of MulTypo (Zhao et al., 2026; https://github.com/cisnlp/multypo):
  adjacent-key replacement, deletion, insertion and transposition on a plain QWERTY
  adjacency graph. It keeps MulTypo's interface but none of its code or its
  hand-aware key weighting. A typo is a real word if it is in `nltk.corpus.words`.
- **Scoring.** Answers are read only from the final section (after `</think>`).
  A trace with no extractable answer there is *unanswered* and excluded from
  answered-only accuracy; strict accuracy counts it as wrong. ARC answers are the
  boxed letter, else the last explicit answer statement ("The correct answer is B)").
- **Statistics.** Flips use a continuity-corrected McNemar test on questions
  answered in both conditions; tables also give Holm-corrected p-values over the
  nine configurations of a run. Confidence intervals for the per-typo logistic fit
  come from 1,000 bootstrap resamples of questions.
- **Word-level repair.** A corrupted word counts as silently fixed, flagged,
  misread or not used depending on which of its two forms the reasoning contains.
  A word is left out when its corrupted form also appears in the model's reasoning
  on the clean version of the same question, since then its presence says nothing
  about the typo. Corrupted words are found by aligning the clean and typo question
  word by word.
- **Self-doubt markers** are counted once per expression: overlapping matches of
  different patterns ("but wait" / "wait") count as one.

## Provenance

- **Cut-off streams.** Before the runner rejected them, the router sometimes closed
  a stream mid-generation, leaving a partial trace far below the token cap. These
  rows were removed with `inference/repair_dropped.py` and regenerated with
  identical prompts through the runner's resume mode: 57 ARC rows with no final
  answer (31 in `clean`, 26 in `typo50_real40`; August 2026) and 44 rows whose final
  answer stopped mid-sentence (GSM8K `clean` 6, `typo75_real10` 6, `typo75_real70` 25;
  ARC `clean` 4, `typo50_real40` 3; September 2026). `inference/rerun_manifest.json`
  lists them; every other row is as generated. One regenerated GSM8K row
  (`typo75_real70`, question 477) ran to the 20,000-token cap.
- **Runner revisions.** The main-grid runs (GSM8K, MATH-500, ARC) were made with
  earlier revisions of `run_typo_api.py` that did not yet store the `fix`,
  `typo_originals`/`typo_replacements` and spell-check fields, and mostly not
  `finish_reason`; their prompts and decoding match the current script, and the
  regenerated rows carry the current fields. The MATH-500 and ARC `cost_usd` values
  used an older price table and understate the cost about 5x.
- **Judge.** Scores were produced in August 2026 with `analysis/llm_judge.py` (prompt
  `v1`, Llama-3.3-70B-Instruct via the Hugging Face router, temperature 0; the
  router's provider was not recorded). The prompt lists the corrupted words from a
  difflib alignment of the clean and typo question, which `llm_judge.py` keeps so
  that it rebuilds the same prompts. Coverage of the answered traces: GSM8K 4,830 of
  4,960, MATH-500 4,564 of 4,962, ARC 4,742 of 4,914. The rest have no score:
  the judge's reply could not be parsed (GSM8K 94, MATH-500 398, ARC 64; mostly
  LaTeX backslashes in quoted evidence), the trace was regenerated after judging
  (GSM8K 36, ARC 63), or the trace counts as answered only under the corrected ARC
  answer reading (ARC 45). They were not re-judged: in September 2026 the same
  prompt through the router scored self-doubt about 0.5 points higher on 30
  already-scored traces (repair unchanged), so mixing the two would bias exactly
  these traces. The current `llm_judge.py` parses such replies, retries failures and
  stores the judge model, prompt version and a hash of the judged trace with every
  row.

## License

MIT (see `LICENSE`), for the code and for the data we publish. `report/acl.sty`
and `report/acl_natbib.bst` are the ACL template files and keep their own licenses.
