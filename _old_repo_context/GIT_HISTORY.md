# Git history of the old repo (ronshtricker1210/NLP_project)

Full commit log of `main` up to `9719fcb` (2026-07-25), newest first, with the
complete commit messages. This history does not exist in the new repo.
Author names are as recorded by git ("unknown" = no author name was configured).

## Pull requests

- **ronshtricker1210/NLP_project#1** `api-setup` → `main`, "api-setup: typo pipeline over HF Inference Providers (no GPU)" (opened 2026-07-24, closed; its commit `21c3e9d` reached `main` through merge commit `c776b9b`).
  Body: *API twin of gcp-setup: same datasets, prompts, JSONL schema and score.py, inference via DeepSeek-R1-Distill-Qwen-7B on Nscale through the HF router. Adds resume, cost tracking, and Hub mirroring of results (results/{dataset}/typo{rate}/real{ratio} + push_to_hub configs).*

The old repo has no issues.

## Commits

### `9719fcb` · 2026-07-25 · unknown

**full_analysis: add n_answered (not-truncated count) to the accuracy table**

```
Table 1 now shows n_answered alongside n, so truncated = n - n_answered is visible;
caption spells out each column.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `46cd701` · 2026-07-25 · Dolev Abudi

**api-setup: reject dropped streams; --file-suffix for budget variants**

```
- streams must deliver a finish_reason to be accepted: under sustained
  high concurrency the server can drop long-lived streams, which
  previously produced silently truncated generations (432/5000 records
  in the first 20k-cap sweep); dropped streams now retry
- records carry finish_reason for diagnostics
- --file-suffix (e.g. 20000) names files gsm8k_<config>_20000.jsonl and
  suffixes Hub paths/configs so runs with different token budgets coexist
- analyze.py --strip-suffix scores suffixed sweeps

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### `43ff679` · 2026-07-25 · unknown

**full_analysis: make the whole pipeline dataset-parameterized; strip result-specific text from the report**

```
- common.py: NLP_DATASET env var selects the dataset (default gsm8k). Reads
  data/<dataset>/, writes tables/<dataset>/, and scores per dataset kind
  (gsm8k=numeric, math500=math_verify on \boxed, gpqa=multiple choice). Friendly
  error if the data isn't downloaded yet.
- all modules: import the dataset-aware TABLES from common; prints use DATASET.
- download_data.py / run_all.py: add --dataset; run_all sets NLP_DATASET for the
  module subprocesses, titles the report with the dataset, and writes
  report_<dataset>.tex; tables land in tables/<dataset>/.
- report notes: removed hard-coded, gsm8k-specific numbers/conclusions (the
  Real-word "key results" now just describes the three views); title is
  parameterized; dropped the stale capped_frac mention in the intro. Captions
  describe method only, so the report stays correct on any dataset.
- moved gsm8k tables to tables/gsm8k/ and report.tex -> report_gsm8k.tex.

Any dataset with the same typo{25,50,75} x real{10,40,70} grid now runs via
  python download_data.py --dataset X && python run_all.py --dataset X

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `3400685` · 2026-07-25 · unknown

**full_analysis: add download_data.py, one-command README workflow, report notes**

```
- download_data.py: one command to fetch the gsm8k result JSONL from
  Dolevabudi/typo-results into data/gsm8k/.
- README: top "Quick start" for a fresh clone (install -> download_data.py ->
  run_all.py -> report.tex); refreshed module table and run list.
- run_all.py: explanatory notes rendered into report.tex (McNemar test, self-doubt
  banks with example, repair categories with sum->sun example, Real-word key-results
  summary); consistent \small + adjustbox formatting, no clearpage; dropped capped_frac
  from the accuracy table.
- report.tex regenerated (14 tables).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `f718cbf` · 2026-07-25 · unknown

**full_analysis: trim/clarify report tables + consistent LaTeX formatting**

```
- accuracy_flips.py: drop truncated/truncated_frac/completion from the per-config
  CSV and dropped_unanswered from the flips CSV.
- reasoning_length.py: remove the typo/clean ratio table (kept absolute tokens +
  length-by-outcome).
- self_doubt.py: rank the per-marker table by discrimination (all markers shown).
- run_all.py: drop the accuracy decomposition and ratio tables from the report;
  expand captions to explain how columns are computed (flips, self-doubt outcome,
  word-level buckets, misread rate, real-word tables); note real-word paired table
  is vs the low-real variant, not clean. Report formatting: uniform \small + shrink-
  only adjustbox (no more resizebox stretching), [H] placement, no \clearpage.
- report.tex regenerated (14 tables).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `b0b969f` · 2026-07-25 · unknown

**full_analysis: word-level repair, single runner + LaTeX report, retire keyword repair**

```
- repair_wordlevel.py: primary repair measure, grounded in the ACTUAL corrupted
  words (diff clean vs typo). Per word: silent_fix / flagged / misread / not_used.
  Catches silent misreads that the keyword measure could not.
- marker_banks.py: shared typo-noticing + repair word banks and classify_trace,
  so active modules no longer import from the retired repair file.
- repair_behavior.py -> repair_behavior_old_version.py: retired keyword-based
  repair (superseded; kept for reference, not in the active set).
- run_all.py: runs every active module then builds report.tex, a self-contained
  Overleaf-ready document with a booktabs table per result.
- report.tex: generated report of all result tables.
- README + lexical_grid/real_word_effect imports updated accordingly.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `9859af9` · 2026-07-25 · unknown

**full_analysis: add real_word_effect.py; move real-ratio comparisons out of self_doubt**

```
- real_word_effect.py isolates the real-word axis:
  1. controlled paired real10-vs-real70 within a fixed rate (same question/positions,
     only kind of typo differs) + McNemar — real-word typos are significantly more
     harmful at rate50/75 (-5% / -9%, p<0.05).
  2. per-typo logit correct ~ num_real + num_nonword — a real-word typo does ~2x the
     damage of a non-word one.
  3. silent-failure test: real-word failures are noticed MORE, not less
     ("noticed-but-unrecoverable", not silent).
- self_doubt.py: removed the real-ratio-only sections (silent-failure test, by-real
  outcome table); those belong in real_word_effect.py. self_doubt now stays per-config.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `126aa89` · 2026-07-24 · unknown

**full_analysis: wider typo-robustness analysis (gsm8k)**

```
Adds the four proposal dimensions as standalone, answered-only modules over the
Dolevabudi/typo-results gsm8k runs (clean + typo{25,50,75} x real{10,40,70}):

- accuracy_flips.py: truncation-aware accuracy (strict/answered/completion),
  answered-only flips vs clean + McNemar, drop decomposition.
- reasoning_length.py: absolute tokens + typo/clean ratio (median/mean/p90),
  length by outcome; ratio is censoring-aware (a lower bound).
- self_doubt.py: self-doubt = second_guess + uncertainty marker density,
  per-marker discrimination, by-outcome split; --no-2guess flag.
- repair_behavior.py: repair = typo-noticing + repair words, notice x outcome
  buckets, plus a strict LLM-judge scaffold (--judge, needs HF_TOKEN).
- lexical_grid.py: all four marker families across the rate x real grid.

Correctness reuses api-setup/score.py. Result CSVs included; raw JSONL is
gitignored (reproducible from the Hub, see README).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `63f456a` · 2026-07-24 · Dolev Abudi

**api-setup: stream generations + correct Nscale pricing to $0.15/M**

```
- stream=True with include_usage: HF router's ~10-min gateway timeout killed
  non-streamed long generations (GPQA chains avg 7k tokens at ~50 tok/s were
  stuck in retry loops); streaming keeps the connection alive at any length
- price constants corrected from a stale third-party figure to the official
  router rate (router.huggingface.co/v1/models): $0.15/M input and output

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### `e9ab4b3` · 2026-07-24 · Dolev Abudi

**api-setup/analyze.py: accuracy + token-usage matrices per typo config**

```
Builds on score.py (score_file / majority_correct) and adds per-config
token and cost aggregation, rate x real accuracy and avg-token matrices,
and flip counts vs the clean baseline.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### `c776b9b` · 2026-07-24 · dolev98

**Merge pull request #1 from ronshtricker1210/api-setup**

```
api-setup: typo pipeline over HF Inference Providers (no GPU)```

### `21c3e9d` · 2026-07-24 · Dolev Abudi

**api-setup: typo pipeline over HF Inference Providers (no GPU)**

```
API twin of gcp-setup: same datasets, prompts, JSONL schema and score.py,
inference via DeepSeek-R1-Distill-Qwen-7B on Nscale through the HF router.
Adds resume, cost tracking, and Hub mirroring of results
(results/{dataset}/typo{rate}/real{ratio} + push_to_hub configs).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

### `359ab10` · 2026-07-24 · Ido Azoulay

**Add gcp-setup: single-L4 GCP port of the inference/scoring pipeline**

```
Port of server-setup for the idonlpinstance1 GCP box (1x NVIDIA L4, no Slurm/conda):
- run_typo_vllm.py: vLLM, tensor_parallel=1, native bf16, cudagraphs; CLI adds
  --dataset ...|all, --configs ...|all, --variant both, --n-samples
- score.py: aggregates multi-sample runs (majority-vote flips)
- run_typo.py: transformers fallback; vllm_smoke.py: single-L4 smoke test
- setup_gcp.sh: toolchain (g++/make/python3-dev) + pip --user deps + cache verify
- env.sh: default HF cache, HF_HUB_OFFLINE, MODEL_PATH resolver
- run.sh: inference->scoring wrapper with --detach (survive SSH disconnect)
- README.md + GCP_RUNBOOK.md: full context, run guide, data locations, troubleshooting

Also add NLP_Project_Proposal.md (markdown copy of the proposal PDF).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

### `089453f` · 2026-07-24 · Ido Azoulay

**Merge branch 'typo-ratio-variants' into main**

```
Add controlled real-word-ratio typo generation and density-sweep variant tooling.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

### `da9c3ac` · 2026-07-21 · IdoAzoulay

**generate_variants: --clean config upload and --rate-in-name for density sweeps**

_(no message body)_

### `da4c6ca` · 2026-07-21 · Shiran Hamami

**scoring fixes: correct math_verify usage + honest MC extraction**

```
- math_verify: wrap answers in $...$ so it parses LaTeX (bare input failed on
  equivalent forms like \frac vs \dfrac, \left(\right) vs (), \text{}).
- multiple-choice: only accept a boxed letter or explicit "answer is X"; do NOT
  fall back to a random A/B/C/D from the reasoning (truncated trace = unanswered).
- report answered-rate and acc(of answered) to separate truncation from wrong answers.
- run_typo_vllm.py: auto-size max_model_len = max_new_tokens + 1536.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `5721abb` · 2026-07-21 · Shiran Hamami

**server-setup: remove 4-bit/AWQ path; keep only the working fp16 setup**

```
- Drop AWQ model download from bootstrap.sh (4-bit AWQ is ~10x slower on the
  RTX 2080 Ti / sm_75 - not usable, so removed to avoid confusion).
- Delete install_vllm.sbatch (unpinned `pip install vllm` pulled the broken
  0.25.1; the vLLM env is now built correctly by bootstrap.sh, pinned to 0.11.0).
- Fix bootstrap.sh step numbering; update README accordingly.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `eccb877` · 2026-07-20 · Shiran Hamami

**bootstrap: also download AWQ 4-bit model for auto-restore after purge**

```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `06eab6e` · 2026-07-20 · Shiran Hamami

**server-setup: add math_verify to bootstrap for accurate MATH500 scoring**

```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `c3df0e3` · 2026-07-20 · Shiran Hamami

**server-setup: bootstrap now rebuilds the vLLM env; vllm sbatch gains variant + fp16/flashinfer flags**

```
So a full rebuild after a /vol/scratch purge reproduces the working vLLM setup
(vllm 0.11.0 + torch cu128 + transformers 4.x) and the clean/typo variant runs.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `d9fe931` · 2026-07-20 · Shiran Hamami

**Add server-setup: TAU cluster setup + inference pipeline backup**

```
Cluster runbook, bootstrap/env scripts, transformers + vLLM inference
pipelines, scorer, and smoke tests for running DeepSeek-R1-Distill-Qwen-7B
on the TAU Slurm cluster.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

### `381cf99` · 2026-07-18 · IdoAzoulay

**Update docs for the controlled-ratio variant scheme**

_(no message body)_

### `b3ef291` · 2026-07-18 · IdoAzoulay

**Add controlled real-word-ratio typo generation**

```
- multypo/typo_generator: candidate_distribution() enumerates all 1-edit
  typos of a word with their natural sampling probabilities
- typo_pipeline: target_real_fraction mode - per-problem real-word quota
  (probabilistic rounding), 1-or-2-edit typos (two_edit_prob), non-word
  redraws, per-typo metadata columns; natural mode unchanged
- generate_variants.py: CLI driver for the dataset matrix (real0..real70
  x math500/gsm8k/gpqa), local save + HF push (gpqa always private)
```

### `bed8a10` · 2026-07-18 · Ron Shtricker

**Organize data creation pipeline**

_(no message body)_

### `7ddb871` · 2026-07-18 · Stricker

**Initial clean setup**

_(no message body)_


## Files touched per commit

```
9719fcb 2026-07-25 full_analysis: add n_answered (not-truncated count) to the accuracy table

M	full_analysis/accuracy_flips.py
M	full_analysis/report_gsm8k.tex
M	full_analysis/run_all.py
M	full_analysis/tables/gsm8k/accuracy_per_config.csv
46cd701 2026-07-25 api-setup: reject dropped streams; --file-suffix for budget variants

M	api-setup/analyze.py
M	api-setup/run_typo_api.py
43ff679 2026-07-25 full_analysis: make the whole pipeline dataset-parameterized; strip result-specific text from the report

M	full_analysis/README.md
M	full_analysis/accuracy_flips.py
M	full_analysis/common.py
M	full_analysis/download_data.py
M	full_analysis/lexical_grid.py
M	full_analysis/real_word_effect.py
M	full_analysis/reasoning_length.py
M	full_analysis/repair_behavior_old_version.py
M	full_analysis/repair_wordlevel.py
R094	full_analysis/report.tex	full_analysis/report_gsm8k.tex
M	full_analysis/run_all.py
M	full_analysis/self_doubt.py
R100	full_analysis/tables/accuracy_decomposition.csv	full_analysis/tables/gsm8k/accuracy_decomposition.csv
R100	full_analysis/tables/accuracy_per_config.csv	full_analysis/tables/gsm8k/accuracy_per_config.csv
R100	full_analysis/tables/flips_vs_clean.csv	full_analysis/tables/gsm8k/flips_vs_clean.csv
R100	full_analysis/tables/length_by_outcome.csv	full_analysis/tables/gsm8k/length_by_outcome.csv
R100	full_analysis/tables/lexical_grid.csv	full_analysis/tables/gsm8k/lexical_grid.csv
R100	full_analysis/tables/realword_paired.csv	full_analysis/tables/gsm8k/realword_paired.csv
R100	full_analysis/tables/realword_pertypo_logit.csv	full_analysis/tables/gsm8k/realword_pertypo_logit.csv
R100	full_analysis/tables/realword_silent_failure.csv	full_analysis/tables/gsm8k/realword_silent_failure.csv
R100	full_analysis/tables/reasoning_length_absolute.csv	full_analysis/tables/gsm8k/reasoning_length_absolute.csv
R100	full_analysis/tables/repair_wordlevel_by_outcome.csv	full_analysis/tables/gsm8k/repair_wordlevel_by_outcome.csv
R100	full_analysis/tables/repair_wordlevel_by_real.csv	full_analysis/tables/gsm8k/repair_wordlevel_by_real.csv
R100	full_analysis/tables/repair_wordlevel_per_config.csv	full_analysis/tables/gsm8k/repair_wordlevel_per_config.csv
R100	full_analysis/tables/self_doubt_by_marker.csv	full_analysis/tables/gsm8k/self_doubt_by_marker.csv
R100	full_analysis/tables/self_doubt_by_outcome.csv	full_analysis/tables/gsm8k/self_doubt_by_outcome.csv
R100	full_analysis/tables/self_doubt_per_config.csv	full_analysis/tables/gsm8k/self_doubt_per_config.csv
D	full_analysis/tables/repair_notice_outcome.csv
D	full_analysis/tables/repair_notice_vs_realratio.csv
D	full_analysis/tables/repair_words_per_config.csv
3400685 2026-07-25 full_analysis: add download_data.py, one-command README workflow, report notes

M	full_analysis/README.md
M	full_analysis/accuracy_flips.py
A	full_analysis/download_data.py
M	full_analysis/report.tex
M	full_analysis/run_all.py
M	full_analysis/tables/accuracy_per_config.csv
f718cbf 2026-07-25 full_analysis: trim/clarify report tables + consistent LaTeX formatting

M	full_analysis/accuracy_flips.py
M	full_analysis/reasoning_length.py
M	full_analysis/report.tex
M	full_analysis/run_all.py
M	full_analysis/self_doubt.py
M	full_analysis/tables/accuracy_per_config.csv
M	full_analysis/tables/flips_vs_clean.csv
D	full_analysis/tables/reasoning_length.csv
M	full_analysis/tables/self_doubt_by_marker.csv
b0b969f 2026-07-25 full_analysis: word-level repair, single runner + LaTeX report, retire keyword repair

M	full_analysis/README.md
M	full_analysis/lexical_grid.py
A	full_analysis/marker_banks.py
M	full_analysis/real_word_effect.py
R076	full_analysis/repair_behavior.py	full_analysis/repair_behavior_old_version.py
A	full_analysis/repair_wordlevel.py
A	full_analysis/report.tex
A	full_analysis/run_all.py
A	full_analysis/tables/repair_wordlevel_by_outcome.csv
A	full_analysis/tables/repair_wordlevel_by_real.csv
A	full_analysis/tables/repair_wordlevel_per_config.csv
9859af9 2026-07-25 full_analysis: add real_word_effect.py; move real-ratio comparisons out of self_doubt

M	full_analysis/README.md
A	full_analysis/real_word_effect.py
M	full_analysis/self_doubt.py
A	full_analysis/tables/realword_paired.csv
A	full_analysis/tables/realword_pertypo_logit.csv
A	full_analysis/tables/realword_silent_failure.csv
D	full_analysis/tables/self_doubt_vs_realratio.csv
126aa89 2026-07-24 full_analysis: wider typo-robustness analysis (gsm8k)

M	.gitignore
A	full_analysis/README.md
A	full_analysis/accuracy_flips.py
A	full_analysis/common.py
A	full_analysis/lexical_grid.py
A	full_analysis/reasoning_length.py
A	full_analysis/repair_behavior.py
A	full_analysis/self_doubt.py
A	full_analysis/tables/accuracy_decomposition.csv
A	full_analysis/tables/accuracy_per_config.csv
A	full_analysis/tables/flips_vs_clean.csv
A	full_analysis/tables/length_by_outcome.csv
A	full_analysis/tables/lexical_grid.csv
A	full_analysis/tables/reasoning_length.csv
A	full_analysis/tables/reasoning_length_absolute.csv
A	full_analysis/tables/repair_notice_outcome.csv
A	full_analysis/tables/repair_notice_vs_realratio.csv
A	full_analysis/tables/repair_words_per_config.csv
A	full_analysis/tables/self_doubt_by_marker.csv
A	full_analysis/tables/self_doubt_by_outcome.csv
A	full_analysis/tables/self_doubt_per_config.csv
A	full_analysis/tables/self_doubt_vs_realratio.csv
63f456a 2026-07-24 api-setup: stream generations + correct Nscale pricing to $0.15/M

M	api-setup/run_typo_api.py
e9ab4b3 2026-07-24 api-setup/analyze.py: accuracy + token-usage matrices per typo config

A	api-setup/analyze.py
c776b9b 2026-07-24 Merge pull request #1 from ronshtricker1210/api-setup
21c3e9d 2026-07-24 api-setup: typo pipeline over HF Inference Providers (no GPU)

A	api-setup/README.md
A	api-setup/api_smoke.py
A	api-setup/env.sh
A	api-setup/requirements.txt
A	api-setup/run.sh
A	api-setup/run_typo_api.py
A	api-setup/score.py
359ab10 2026-07-24 Add gcp-setup: single-L4 GCP port of the inference/scoring pipeline

A	NLP_Project_Proposal.md
A	gcp-setup/GCP_RUNBOOK.md
A	gcp-setup/README.md
A	gcp-setup/env.sh
A	gcp-setup/run.sh
A	gcp-setup/run_typo.py
A	gcp-setup/run_typo_vllm.py
A	gcp-setup/score.py
A	gcp-setup/setup_gcp.sh
A	gcp-setup/vllm_smoke.py
089453f 2026-07-24 Merge branch 'typo-ratio-variants' into main
da9c3ac 2026-07-21 generate_variants: --clean config upload and --rate-in-name for density sweeps

M	data_creation/generate_variants.py
da4c6ca 2026-07-21 scoring fixes: correct math_verify usage + honest MC extraction

M	server-setup/run_typo_vllm.py
M	server-setup/score.py
5721abb 2026-07-21 server-setup: remove 4-bit/AWQ path; keep only the working fp16 setup

M	server-setup/README.md
M	server-setup/bootstrap.sh
D	server-setup/install_vllm.sbatch
eccb877 2026-07-20 bootstrap: also download AWQ 4-bit model for auto-restore after purge

M	server-setup/bootstrap.sh
06eab6e 2026-07-20 server-setup: add math_verify to bootstrap for accurate MATH500 scoring

M	server-setup/bootstrap.sh
c3df0e3 2026-07-20 server-setup: bootstrap now rebuilds the vLLM env; vllm sbatch gains variant + fp16/flashinfer flags

M	server-setup/bootstrap.sh
M	server-setup/run_typo_vllm.sbatch
d9fe931 2026-07-20 Add server-setup: TAU cluster setup + inference pipeline backup

A	server-setup/CLUSTER_RUNBOOK.md
A	server-setup/README.md
A	server-setup/ask_local.py
A	server-setup/ask_local.sbatch
A	server-setup/bootstrap.sh
A	server-setup/env.sh
A	server-setup/install_vllm.sbatch
A	server-setup/run_inference.py
A	server-setup/run_inference.sbatch
A	server-setup/run_typo.py
A	server-setup/run_typo.sbatch
A	server-setup/run_typo_vllm.py
A	server-setup/run_typo_vllm.sbatch
A	server-setup/score.py
A	server-setup/setup_and_download.sh
A	server-setup/vllm_smoke.py
381cf99 2026-07-18 Update docs for the controlled-ratio variant scheme

M	AGENTS.md
M	DATASET_USAGE.md
b3ef291 2026-07-18 Add controlled real-word-ratio typo generation

M	.gitignore
A	data_creation/generate_variants.py
M	data_creation/multypo/__init__.py
M	data_creation/typo_generator.py
M	data_creation/typo_pipeline.py
bed8a10 2026-07-18 Organize data creation pipeline

A	.gitignore
M	AGENTS.md
M	DATASET_USAGE.md
A	data_creation/__init__.py
A	data_creation/interactive_slurm_hf_run.py
A	data_creation/multypo/__init__.py
R100	requirements.txt	data_creation/requirements.txt
R098	run_pipeline.slurm	data_creation/run_pipeline.slurm
A	data_creation/run_smoke.slurm
A	data_creation/typo_generator.py
R089	typo_pipeline.py	data_creation/typo_pipeline.py
D	multypo
7ddb871 2026-07-18 Initial clean setup

A	AGENTS.md
A	DATASET_USAGE.md
A	NLP_Project_Proposal_207487026_323096099_209524552_212710958.pdf
A	multypo
A	requirements.txt
A	run_pipeline.slurm
A	typo_pipeline.py
```
