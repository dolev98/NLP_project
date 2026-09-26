# Context carried over from the old repo

What the old repo (`ronshtricker1210/NLP_project`, snapshot of `main` @ `9719fcb`,
2026-07-25) knew that the new repo (`dolev98/NLP_project`) does not say anywhere.
Sources are the old files in [`snapshot/`](snapshot/) and the commit messages in
[`GIT_HISTORY.md`](GIT_HISTORY.md); file references below are old-repo paths
inside `snapshot/` unless marked *new*.

## 1. Timeline

| Date (2026) | Who (git author) | What happened | Old files |
|---|---|---|---|
| 07-18 | Ron Shtricker | Initial setup; data-creation pipeline organized (natural mode: inject typos, score real-word ratio P, bin with `pandas.cut`). | `data_creation/typo_pipeline.py`, `AGENTS.md` |
| 07-18 | Ido Azoulay | Controlled real-word ratio: per-problem real-word quota, 1- or 2-edit typos, variants `real0`..`real70` for MATH-500, GSM8K, GPQA Diamond; pushed to `idoazou/*-typos`. | `data_creation/generate_variants.py`, `DATASET_USAGE.md` |
| 07-20 → 07-21 | Shiran Hamami | TAU Slurm cluster setup: transformers + vLLM pipelines for DeepSeek-R1-Distill-Qwen-7B, runbook, `bootstrap.sh`; AWQ 4-bit tried and dropped (~10× slower on RTX 2080 Ti). | `server-setup/` |
| 07-21 | Shiran Hamami | Scoring fixes: wrap answers in `$…$` for `math_verify`; multiple choice only from a boxed letter or explicit "answer is X"; report answered-rate. | `server-setup/score.py` |
| 07-21 | Ido Azoulay | `--rate-in-name` density sweeps (`rate{25,50,75}_real{…}`) and a `clean` config: the start of the r × ρ grid. | `data_creation/generate_variants.py` |
| 07-24 | Ido Azoulay | GCP port for one NVIDIA L4 (`idonlpinstance1`); markdown copy of the proposal added. | `gcp-setup/`, `NLP_Project_Proposal.md` |
| 07-24 | Dolev Abudi | API route: same pipeline through the Hugging Face Inference Providers router (Nscale). Became the route used for the final runs. Accuracy/token/cost matrices. Streaming added (router's ~10 min gateway timeout killed long non-streamed generations). | `api-setup/` |
| 07-24 → 07-25 | author not recorded | Full GSM8K analysis: accuracy/flips, length, self-doubt, word-level repair, real-word isolation, auto-generated LaTeX report; then made dataset-parameterized. | `full_analysis/` |
| 07-25 | Dolev Abudi | Reject streams that end without a `finish_reason` (432/5,000 records of the first 20k-cap sweep were silently truncated); `--file-suffix` for token-budget variants. | `api-setup/run_typo_api.py` |
| later | – | Work moved to `dolev98/NLP_project`: restructured into `data_creation/ inference/ analysis/ results/ report/`, ARC replaces GPQA, mitigations, LLM judge, ACL report. | *new* repo |

## 2. Design decisions and how they changed

1. **Datasets.** Proposal and old repo: MATH-500, GSM8K test, GPQA Diamond
   (gated; `idoazou/gpqa-typos` was always private). New repo: GSM8K, MATH-500,
   ARC-Challenge (first 500 four-option questions). The reason is in the new
   report's Limitations: the model scored only about 52% on clean GPQA-Diamond
   in a preliminary run, too close to 25% chance.
2. **Typo configurations.** Old: 8 variants `real0`..`real70` (10-point steps) at a
   fixed ~30% typo rate, later also `rate{25,50,75}_real{N}`; the GCP runbook
   counts 34 configs per dataset. New: `clean` + `rate{25,50,75}_real{10,40,70}`.
   Why real-word ratio stops at 70% (`DATASET_USAGE.md`): most words have no
   1-edit typo that is a real word, so higher targets cannot be reached without
   biasing which words get corrupted; each row stores the achieved ratio.
3. **Typo generator.** Old: local package `data_creation/multypo/` plus a near-identical
   fallback `data_creation/typo_generator.py`. New: `data_creation/keyboard_typos.py`,
   described as a reimplementation of MulTypo's four edit operations (commit `690cded`
   on the new repo's branch `claude/cool-lamport-utawqi` changes the report wording to match).
4. **Pipeline modes.** The old `typo_pipeline.py` also had a *natural* mode (no
   target ratio, then bin problems by achieved ratio P into `bin_<range>/` folders,
   with a mock dataset and a tiny dictionary as offline fallbacks). The new one
   keeps only the controlled-ratio mode. `AGENTS.md` still describes the natural mode.
5. **Where inference ran.** TAU Slurm (2× RTX 2080 Ti, fp16, vLLM 0.11.0) → GCP
   (1× L4, bf16, vLLM) → HF router API (Nscale, serverless). The API run was checked
   on 2026-07-24: a full MATH-500 pass gave 94.6% accuracy with about 3,256 reasoning
   tokens per question, matching the model's published score
   (`api-setup/README.md`).
6. **Generation cap.** Old default `--max-new-tokens 4096`, which old
   `full_analysis/common.py` assumes (`MAX_NEW_TOKENS = 4096`). The last old commits
   mention a 20k-cap sweep. New: 20,000 for GSM8K, 17,000 for MATH-500 and ARC.
7. **Samples per question.** Old runners supported `--n-samples` (GCP `score.py`
   takes a majority vote for flips). New: one sample per question; the report's
   Limitations says the API budget did not allow more.
8. **Where results are stored.** Old: `Dolevabudi/typo-results`, laid out as
   `results/<ds>/clean.jsonl`, `results/<ds>/typo<r>/real<rho>.jsonl`, plus
   `push_to_hub` configs like `math500_typo30_real40`. New:
   `Dolevabudi/silent-tax-results` (`raw/<run>/`, `judge/`) with a sha256 manifest.
9. **Repair measure.** Old first tried a keyword measure (typo-noticing words),
   retired because it cannot tell a silent fix from a silent misread
   (`full_analysis/repair_behavior_old_version.py`). It was replaced by word-level
   repair: silent_fix / flagged / misread / not_used per corrupted word. The new
   repo keeps this and also leaves out words whose corrupted form already appears in
   the clean-question reasoning.
10. **Scoring rules (unchanged in spirit).** Answer is read only after `</think>`;
    a trace with no answer there is *unanswered* (excluded from answered-only accuracy,
    wrong under strict accuracy); multiple choice never falls back to a stray letter
    in the reasoning; `math_verify` inputs are wrapped in `$…$`.
11. **Report.** Old: `full_analysis/report_gsm8k.tex`, an auto-generated dump of 14
    tables for GSM8K only. New: `report/report.tex`, the ACL-format paper.

## 3. Analyses the old repo had that the new one dropped

Possibly useful if a reviewer asks, or for an appendix. All code is in
`snapshot/full_analysis/`; GSM8K outputs from the old run are in
`snapshot/full_analysis/tables/gsm8k/`.

- `lexical_grid.py` → `lexical_grid.csv`: all four marker families
  (second_guess, uncertainty, typo_noticing, repair_words) across the grid.
- `real_word_effect.py` silent-failure test → `realword_silent_failure.csv`: among
  wrong answers, the share whose reasoning explicitly flags the corruption, by
  real-word ratio.
- `self_doubt.py` per-marker discrimination → `self_doubt_by_marker.csv`; flag
  `--no-2guess` (uncertainty markers only, because second_guess was a flat baseline).
- `repair_wordlevel.py` → `repair_wordlevel_by_real.csv`: word handling pooled by
  real-word ratio.
- `marker_banks.py`: the typo-noticing and repair word banks and `classify_trace`.
- `api-setup/analyze.py`: per-config token and **cost** aggregation.
- `repair_behavior_old_version.py`: an early LLM-judge scaffold (`--judge`).

## 4. Findings recorded in the old repo

From an earlier GSM8K run; the new `results/` supersede them, so treat these as
history, not as numbers to cite.

- **Real-word effect** (`full_analysis/README.md`): same questions and same positions,
  real10 vs real70 within one rate: real-word typos lowered accuracy significantly at
  rate 50 and 75 (−5 and −9 points, McNemar p < 0.05). Per typo, a real-word typo did
  about 2× the damage of a non-word one. Real-word failures were flagged *more* often,
  not less ("noticed but unrecoverable", not silent).
- **First GCP sanity run** (`gcp-setup/GCP_RUNBOOK.md`, GSM8K, 50 questions): clean
  98.0%, `rate25_real10` 82.0% (9 right→wrong, 1 wrong→right); reasoning +23.5% longer;
  self-doubt markers +41%.
- **Old GSM8K accuracy** (`full_analysis/tables/gsm8k/accuracy_per_config.csv`, 500
  questions per config):

  | config | answered | acc (answered) | acc (strict) |
  |---|---|---|---|
  | clean | 481 | 95.2% | 91.6% |
  | typo25_real10 | 454 | 90.8% | 82.4% |
  | typo50_real40 | 445 | 82.5% | 73.4% |
  | typo75_real70 | 392 | 71.4% | 56.0% |

  The new `results/gsm8k/accuracy_per_config.csv` has clean 92.6% / 92.6% with 500
  answered. The difference in answered counts is consistent with a lower token cap
  and/or the dropped-stream truncation fixed in `46cd701`; which of the two produced
  the old files is not recorded.

## 5. Old result tables vs new

`diffs/gsm8k_result_tables.diff` diffs the 11 GSM8K tables that exist in both repos.
Column sets changed too (e.g. new accuracy table adds `n_correct` and renames the
CI columns to `strict_ci_lo/hi`).

## 6. Proposal vs final work: checklist for the report

The proposal (`NLP_Project_Proposal.md` / the PDF) promised the items below. Status
comes from the new README and `report/report.tex` in the new repo (grep, 2026-09-26);
please confirm the "not found" items yourself before submitting.

| Proposal item | In the new repo? |
|---|---|
| 4 typo techniques (adjacent key, swap, delete, insert) | Yes (`keyboard_typos.py`) |
| Real-word vs non-word typos | Yes (ρ axis) |
| Numbers and math never corrupted | Yes |
| Real-word typos "filtered so a human can still understand the question" / "confirm on a small sample that a human can still answer" | **Not found** in report.tex (no "human" check mentioned) |
| Several runs per question, averaged | Deviation, stated in Limitations (n = 1, budget) |
| Flips per typo technique **and** type | Per type (ρ) yes; per technique **not found** in report.tex |
| Reasoning length as typo/clean token ratio | New reports absolute lengths and length by outcome (the old repo removed the ratio table in `f718cbf`) |
| Self-doubt: marker counts + LLM judge | Yes (`self_doubt.py`, `llm_judge.py`) |
| Repair behavior via LLM judge | Word-level measure + LLM judge |
| 3 fixes: rewrite, spell-checker, typo warning | Yes, on GSM8K only (stated in Limitations) |
| Datasets MATH-500, GSM8K, GPQA Diamond | GPQA replaced by ARC-Challenge (stated in Limitations) |
| Run on the TAU Slurm cluster | Moved to the HF Inference Providers API (runbooks for the cluster and GCP are in `snapshot/server-setup/`, `snapshot/gcp-setup/`) |

## 7. Infrastructure notes (only in the old repo)

Full details in the runbooks; the short version:

- **TAU cluster** (`server-setup/CLUSTER_RUNBOOK.md`): login `slurm-client.cs.tau.ac.il`
  (VPN off campus; host key changes per login node); default shell tcsh, run `bash`;
  home quota 6 GB, so conda and the 15 GB model go to `/vol/scratch/$USER`, which is
  **purged every few days** (rebuild with `bootstrap.sh`); students get RTX 2080 Ti
  (Titan Xp too old), so the 7B model needs 2 GPUs; torch must be cu128; vLLM needs
  fp16 + `enforce_eager`; `hf_xet` stalls downloads; copying the model to node-local
  `/tmp` loads it in ~4 s instead of ~8 min; account `gpu-students`, partition
  `studentkillable`.
- **GCP L4** (`gcp-setup/GCP_RUNBOOK.md`): bare Ubuntu 22.04 without `g++`, `make`,
  `python3-dev`; `setup_gcp.sh` installs them. About 2.5–3 min per 50-question config.
  `run.sh --detach` survives SSH drops.
- **HF router** (`api-setup/README.md`): token needs "Make calls to Inference
  Providers"; pushing results needs write access (or a separate `HF_WRITE_TOKEN`).
  On 2026-07-24 the router had a billing bug that charged $0.01 per request instead of
  per token. Nscale's price was corrected to $0.15/M tokens in `63f456a`.

## 8. People

Team (from the proposal): Shiran Hamami, Dolev Abudi, Ron Shtricker, Ido Azoulay.
Hub namespaces used: `idoazou` (typo datasets), `Dolevabudi` (results).
