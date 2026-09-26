# Old path → new path

Every file of the old repo (`ronshtricker1210/NLP_project` @ `9719fcb`) and where
it went in the new repo (`dolev98/NLP_project` @ `f5d6c41`). The old file itself
is in [`snapshot/`](snapshot/) at the same relative path. A diff is listed where
the file was ported; see [`diffs/`](diffs/).

Status:
- **ported**: same role in the new repo, code changed (see the diff).
- **merged**: its content now lives inside another new file.
- **dropped**: no counterpart in the new repo.

## Top level

| Old | New | Status | Notes |
|---|---|---|---|
| `AGENTS.md` | – | dropped | Agent instructions for the old repo. Describes the old *natural/binned* mode (`real_token_groups`, `pandas.cut` bins) and the `real0`..`real70` variants, neither of which exists in the new repo. |
| `DATASET_USAGE.md` | `README.md` → "Data" | merged | Old version documents 8 variants `real0`..`real70` at ~30% density, GPQA, private repos. The new README lists public `idoazou/{gsm8k,math500,arc}-typos` with configs `clean`, `rate<r>_real<rho>`. |
| `NLP_Project_Proposal.md` | – | dropped | Markdown copy of the proposal. Useful for checking the report against what was promised (see `CONTEXT.md` §6). |
| `NLP_Project_Proposal_207487026_…_212710958.pdf` | – | dropped | The submitted proposal PDF. |
| `.gitignore` | `.gitignore` | rewritten | New one ignores `data/`, LaTeX build files. |

## `data_creation/`

| Old | New | Status | Notes |
|---|---|---|---|
| `generate_variants.py` | `data_creation/generate_variants.py` | ported | Old: `real0..real70` × {math500, gsm8k, gpqa}; `--rate-in-name` for density sweeps; GPQA always private. New: `rate{25,50,75}` × `real{10,40,70}` grid + `--clean`, ARC replaces GPQA (`_prepare_arc` keeps 4-option questions). Diff: `diffs/data_creation__generate_variants.py.diff`. |
| `typo_pipeline.py` | `data_creation/typo_pipeline.py` | ported | 866 → 406 lines. The natural/binned mode (`target_real_fraction=None`, `real_token_groups`, `pandas.cut`, `bin_<range>/` output, mock dataset/offline fallbacks) was removed; only the controlled real-word-ratio mode is kept. Diff: `diffs/data_creation__typo_pipeline.py.diff`. |
| `multypo/__init__.py` | `data_creation/keyboard_typos.py` | ported | Same QWERTY generator; the new docstring says it is a reimplementation of MulTypo's four edit operations, not MulTypo code. Diff: `diffs/data_creation__multypo__init__.py.diff`. |
| `typo_generator.py` | `data_creation/keyboard_typos.py` | merged | Old fallback copy of `multypo/__init__.py` (differs only in the docstring and one import). |
| `__init__.py` | – | dropped | |
| `interactive_slurm_hf_run.py` | – | dropped | Interactive runner: prompts, stages the job to Slurm, downloads the output, uploads to the Hub. |
| `run_pipeline.slurm`, `run_smoke.slurm` | – | dropped | Slurm templates for dataset creation on the TAU cluster. |
| `requirements.txt` | `requirements.txt` (root) | merged | New one pins versions for Python 3.14. |

## `server-setup/` (TAU Slurm cluster, 2× RTX 2080 Ti)

Whole folder **dropped**; generation moved to the HF router API. Files:
`CLUSTER_RUNBOOK.md` (full cluster guide + troubleshooting), `README.md`,
`bootstrap.sh` (rebuild conda envs + model after a `/vol/scratch` purge),
`env.sh`, `setup_and_download.sh`, `run_typo.py`/`.sbatch` (transformers),
`run_typo_vllm.py`/`.sbatch` (vLLM 0.11.0, fp16, TP=2), `score.py`,
`vllm_smoke.py`, `ask_local.py`/`.sbatch` (one question, node-local model copy),
`run_inference.py`/`.sbatch` (early smoke test).

## `gcp-setup/` (one NVIDIA L4 on GCP, instance `idonlpinstance1`)

Whole folder **dropped**. Files: `GCP_RUNBOOK.md` (full context, timing, first
sanity result, troubleshooting), `README.md` (flag table), `setup_gcp.sh`,
`env.sh`, `run.sh` (with `--detach`), `run_typo_vllm.py` (bf16, TP=1),
`run_typo.py`, `score.py` (multi-sample majority vote), `vllm_smoke.py`.

## `api-setup/` (HF Inference Providers router → Nscale)

| Old | New | Status | Notes |
|---|---|---|---|
| `run_typo_api.py` | `inference/run_typo_api.py` | ported | New adds `--fix {warn,rewrite,spellcheck}`, per-dataset caps (20,000 GSM8K / 17,000 MATH-500 & ARC; old default 4,096), output under `data/raw/`, ARC. `--n-samples` and `--hub-repo` mirroring are not in the new flag list. Diff: `diffs/api-setup__run_typo_api.py.diff`. |
| `score.py` | `inference/score.py` | ported | Diff: `diffs/api-setup__score.py.diff`. |
| `api_smoke.py` | `inference/api_smoke.py` | ported | Near-identical. |
| `analyze.py` | – | dropped | Accuracy + token/cost matrices per config, flips vs clean; `--strip-suffix`. Superseded by `analysis/accuracy_flips.py`. |
| `run.sh`, `env.sh` | – | dropped | Inference → scoring wrapper with `--detach`. |
| `requirements.txt` | `requirements.txt` (root) | merged | |
| `README.md` | `README.md` → "Setup", "Generations" | merged | Old one has the Hub mirroring layout, the HF billing-bug caveat and the MATH-500 API verification run. |

## `full_analysis/` → `analysis/` + `results/`

| Old | New | Status | Notes |
|---|---|---|---|
| `common.py` | `analysis/common.py` | ported | Old: `NLP_DATASET` env var, `data/<ds>/`, `tables/<ds>/`, `MAX_NEW_TOKENS=4096`, gpqa scoring. New: `NLP_RUN` env var (runs incl. `gsm8k_warn` …), `data/raw/<run>/`, `results/<run>/`, Holm correction. |
| `accuracy_flips.py` | `analysis/accuracy_flips.py` | ported | |
| `reasoning_length.py` | `analysis/reasoning_length.py` | ported | typo/clean *ratio* table had already been removed in the old repo (`f718cbf`). |
| `self_doubt.py` | `analysis/self_doubt.py` | ported | Old `self_doubt_by_marker` table and `--no-2guess` flag are gone. |
| `repair_wordlevel.py` | `analysis/repair_wordlevel.py` | ported | New excludes words whose corrupted form also appears in the clean-question reasoning. Old `repair_wordlevel_by_real` table is gone. |
| `real_word_effect.py` | `analysis/real_word_effect.py` | ported | Old `realword_silent_failure` table is gone. |
| `run_all.py` | `analysis/run_all.py` | ported | Old one also generated the LaTeX report (225 → 43 lines); the report now comes from `report/make_assets.py`. |
| `download_data.py` | `analysis/download_data.py` | ported | Old source `Dolevabudi/typo-results` (`results/<ds>/typo<r>/real<rho>.jsonl`); new source `Dolevabudi/silent-tax-results` with sha256 manifest. |
| `marker_banks.py` | – | dropped | Typo-noticing and repair word banks + `classify_trace`; used by `lexical_grid.py`, `real_word_effect.py` (silent-failure test) and the retired keyword repair. |
| `lexical_grid.py` | – | dropped | All four marker families across the rate × real grid. |
| `repair_behavior_old_version.py` | – | dropped | Retired keyword-based repair + an LLM-judge scaffold. The new `analysis/llm_judge.py` is a separate implementation. |
| `README.md` | `README.md` → "Method notes" | merged | Old one has the answered-only policy and the old real-word findings. |
| `report_gsm8k.tex` | `report/report.tex` | superseded | Old: auto-generated table dump (14 tables) for GSM8K. New: ACL-format paper. |
| `tables/gsm8k/*.csv` (15 files) | `results/gsm8k/*.csv` | superseded | 11 names exist in both, but the numbers differ: the old tables come from an earlier generation run (see `CONTEXT.md` §5). Old-only: `lexical_grid`, `realword_silent_failure`, `repair_wordlevel_by_real`, `self_doubt_by_marker`. Diff: `diffs/gsm8k_result_tables.diff`. |

## New-only (no old counterpart)

`data_creation/keyboard_typos.py` (as a named module), `inference/repair_dropped.py`,
`inference/rerun_manifest.json`, `analysis/corruption_stats.py`,
`analysis/llm_judge.py`, `analysis/spellcheck_recovery.py`,
`analysis/data_manifest.json`, `results/{math500,arc,gsm8k_warn,gsm8k_rewrite,gsm8k_spellcheck}/`,
all of `report/`, `LICENSE`.
