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
paper is [`report/report.pdf`](report/report.pdf).

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
  download_data.py       fetch the published datasets, generations and judge scores
  data_manifest.json     pinned Hub revision and sha256 of every data file
  common.py              shared loading, scoring and statistics
results/<run>/   the analysis tables (CSV) behind the numbers in the report, and
                 gsm8k/figure1_example.json (the worked example of Figure 1)
report/          the paper: report.tex, report.pdf, custom.bib and the ACL
                 template files acl.sty and acl_natbib.bst
  make_assets.py         builds generated/ from results/
  generated/     figure PDFs (the paper's Figures 2-5), tables and numbers.txt
                 (quoted numbers with their source files) made by make_assets.py
```

A *run* is one set of generations: `gsm8k`, `math500`, `arc` (main grid) and
`gsm8k_warn`, `gsm8k_rewrite`, `gsm8k_spellcheck` (mitigations). Each run has 10
configurations, `clean` and `typo<r>_real<rho>`.

## Data

| What | Where |
|---|---|
| Typo datasets | [`Dolevabudi/silent-tax-results`](https://huggingface.co/datasets/Dolevabudi/silent-tax-results) (`questions/`; configs `<dataset>_clean`, `<dataset>_rate<r>_real<rho>`; the GSM8K and MATH-500 typo datasets also have ρ = 0, 20, 30, 50, 60 and an older `real<rho>` family, which this study does not use) |
| Model generations and judge scores | [`Dolevabudi/silent-tax-results`](https://huggingface.co/datasets/Dolevabudi/silent-tax-results) (`raw/<run>/`, `judge/`) |

Everything is public. Downloads go to `data/`, which is not committed.

## Setup

Python 3.14. All commands run from the repository root.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The NLTK word list (used by `data_creation/` and `analysis/corruption_stats.py`) is
downloaded automatically on first use. Behind an HTTP proxy, nltk 3.10 refuses that
download unless `NLTK_ALLOW_PROXIED_URLOPEN=1` is set, and the scripts then stop with
`Resource 'words' not found`. Inference and the judge call the Hugging Face router
and need a token with the "Make calls to Inference Providers" permission:
`export HF_TOKEN=hf_...`. Building the paper needs a TeX distribution with
`pdflatex` and `bibtex` (it was built with TeX Live 2023; on Ubuntu 24.04 the
packages `texlive-latex-extra`, `texlive-fonts-recommended` and
`texlive-fonts-extra` are enough); the ACL template typesets in Times through the
`times` package.

## Reproducing the results

Every stage can start from the published output of the previous one; steps 1, 2
and a fresh judge run cost API credits or time and can be skipped by downloading
(step 3).

**1. Typo datasets** (deterministic: seed 42, row *i* uses seed 42 + *i*)

```bash
python data_creation/generate_variants.py --clean     # the clean configs
python data_creation/generate_variants.py             # 3 datasets x 9 configs -> data/typo_variants/
python data_creation/generate_variants.py --datasets arc --subset 20 --out data/typo_check   # quick check
```

Each config is saved to `data/typo_variants/<dataset>/<config>` (`--out` changes the
root, so the quick check does not overwrite the full ARC configs). With the defaults
they reproduce the published datasets, which hold all 1,319 GSM8K and 500 MATH-500
test questions and the first 500 four-option ARC-Challenge test questions; the runs
use the first 500 of each. Step 2 always reads the published datasets (`HUB_REPO` in
`run_typo_api.py`), not `data/typo_variants/`. `--push --namespace <hf-user>`
publishes new ones, but as separate repos `<hf-user>/<dataset>-typos` with configs
`<config>`, not in the layout `run_typo_api.py` reads.

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

The model defaults to `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B:nscale`, which pins
the Nscale provider (`--model` or `MODEL` overrides it). The generation cap defaults
to 20,000 tokens for GSM8K and 17,000 for MATH-500 and ARC. Interrupted runs resume
where they stopped. Use `--limit 5` instead of `--limit 500` for a smoke test (a few
cents). The spell-check arm needs the pinned pyspellchecker 0.8.3, which rebuilds every
spell-checked question of the published run; 0.8.4 and later prefer accented words
(`fete` → `fête`) and break frequency ties differently, which changes the question
sent to the model for about 70 of the 4,500 typo questions.

**3. Or download the paper's typo datasets, generations and judge scores**

```bash
python analysis/download_data.py --all       # ~570 MB, checked against data_manifest.json
```

`--run <run>`, `--judge` or `--questions` downloads only one run's generations, the
judge scores or the typo datasets.

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

**6. Generated tables and figures**

```bash
python report/make_assets.py                 # -> report/generated/
```

Starting from step 3, steps 4, 5 and 6 regenerate every committed file in `results/`
and `report/generated/` byte for byte (checked on Linux; on Windows, Python writes the
LaTeX tables, `numbers.txt` and `figure1_example.json` with Windows line endings; the
CSVs have Windows line endings on every platform). The figure PDFs come out with the
same content; their bytes depend on the fonts installed (they use Times New Roman
when it is available).

**7. The paper**

```bash
cd report && mkdir -p build
pdflatex -output-directory build report && bibtex build/report
pdflatex -output-directory build report && pdflatex -output-directory build report
```

The PDF is written to `report/build/report.pdf`, so the committed `report/report.pdf`
stays as it is.

The paper was edited in the team's review document and then set in the ACL
template, so its tables are typed in; its figures are the vector PDFs in
`report/generated/figures/`. Tables 1–8 hold
the values of `report/generated/tables/` except two cells. The ARC `typo25_real10` p-value in
Table 4 is 0.688, the exact value (0.68849974; `make_assets.py` rounds the stored
0.6885 a second time and prints 0.689). Table 5 gives no ARC interval for the
relative loss (n/a), because the ARC non-word coefficient's interval includes 0, so
the ratio has no finite interval. Four things in the paper are not made by
`make_assets.py`: Table 9, the number of responses that reached the token cap
(`NLP_RUN=<run> python analysis/accuracy_flips.py` prints it per condition as
`capped%` of 500); the coefficient difference in the Table 5 caption, computed
outside the pipeline; the GPQA-Diamond accuracy in the Limitations, from a pilot
run that is not part of the published data; and the self-doubt marker lists in
Appendix D, which are the patterns in `analysis/self_doubt.py`. With TeX Live 2023
and `SOURCE_DATE_EPOCH=1790715722 FORCE_SOURCE_DATE=1`, the build reproduces the
committed `report.pdf` byte for byte.

## Method notes

- **Typo generator.** `keyboard_typos.py` is a small reimplementation of the four
  edit operations of MulTypo (Zhao et al., 2026; https://github.com/cisnlp/multypo):
  adjacent-key replacement, deletion, insertion and transposition on a plain QWERTY
  adjacency graph. It keeps MulTypo's interface but none of its code or its
  hand-aware key weighting. A typo is a real word if it is in `nltk.corpus.words`.
- **Scoring.** Answers are read only from the final section (after `</think>`).
  A trace with no extractable answer there is *unanswered* and excluded from
  answered-only accuracy; strict accuracy counts it as wrong. GSM8K answers are the
  last `\boxed{}`, else the last number, compared numerically; inside the box, LaTeX
  thousands separators (`1,\!210`, `2{,}050`) are read as part of the number, and a
  fraction or mixed number (`\frac{11}{3}`, `5\frac{1}{3}`) by its value. MATH-500 answers are
  the last `\boxed{}`, compared by symbolic equivalence with math-verify. ARC answers
  are the boxed letter, else the last explicit answer statement ("The correct answer
  is B)"), else the last bare "option B" or "choice B", else an answer keyword
  followed by a letter in the last 400 characters.
- **Statistics.** Flips use a continuity-corrected McNemar test on questions
  answered in both conditions; tables also give Holm-corrected p-values over the
  nine typo configurations of a run (for the paired real-word contrasts, over their
  nine rate × ρ-pair contrasts). Confidence intervals for the per-typo logistic fit
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
  answer (31 in `clean`, 26 in `typo50_real40`; August 2026) and 50 rows whose final
  answer was cut off (GSM8K `clean` 6, `typo75_real10` 6, `typo75_real70` 28; ARC
  `clean` 6, `typo50_real40` 4; September 2026). `inference/rerun_manifest.json`
  lists them; every other row is as generated. Two regenerated rows ran to the token
  cap: GSM8K `typo75_real70` question 477 (20,000 tokens) and ARC `clean` question 73
  (17,000).
- **Runner revisions.** The main-grid runs (GSM8K, MATH-500, ARC) were made with
  earlier revisions of `run_typo_api.py` that did not yet store the `fix`,
  `typo_originals`/`typo_replacements` and spell-check fields, and mostly not
  `finish_reason`; their prompts and decoding match the current script. The warn and
  rewrite runs were made with a later revision that stores `fix` and `finish_reason`
  but not `typo_originals`/`typo_replacements` or the spell-check fields. The 50 rows
  regenerated in September 2026 carry the current fields; the 57 ARC rows
  regenerated in August add only `finish_reason`. The MATH-500 and ARC `cost_usd`
  values used an older price table and understate the cost about 5x. A comment in
  `run_typo_api.py` records a fixed bug that sent the bare question instead of the
  built prompt; it affected no published row: every stored `prompt` equals the one
  `build_prompt` rebuilds, and every `n_prompt_tokens` equals that prompt's length
  under the model's chat template.
- **Judge.** Scores were produced in August 2026 with `analysis/llm_judge.py` (prompt
  `v1`, Llama-3.3-70B-Instruct via the Hugging Face router, temperature 0; the
  router's provider was not recorded). The prompt lists the corrupted words from a
  difflib alignment of the clean and typo question, which `llm_judge.py` keeps so
  that it rebuilds the same prompts. Coverage of the answered traces: GSM8K 4,827 of
  4,960, MATH-500 4,564 of 4,962, ARC 4,741 of 4,916. The rest have no score:
  the judge's reply could not be parsed (GSM8K 94, MATH-500 398, ARC 64; mostly
  LaTeX backslashes in quoted evidence), the trace was regenerated after judging
  (GSM8K 39, ARC 66), or the trace counts as answered only under the corrected ARC
  answer reading (ARC 45). They were not re-judged: in September 2026 the same
  prompt through the router scored self-doubt about 0.5 points higher on 30
  already-scored traces (repair unchanged), so mixing the two would bias exactly
  these traces. The current `llm_judge.py` parses such replies, retries failures and
  stores the judge model, prompt version and a hash of the judged trace with every
  row.

## License

The code is MIT (see `LICENSE`). The data we publish are derived from GSM8K (MIT),
MATH-500 (MIT) and ARC-Challenge (CC BY-SA 4.0) and follow their licenses: the ARC
typo dataset and the ARC generations are CC BY-SA 4.0. `report/acl.sty` and
`report/acl_natbib.bst` are the ACL template files and keep their own licenses.
