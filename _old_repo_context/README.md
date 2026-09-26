# `_old_repo_context/`: TEMPORARY, delete before submission

This folder brings over everything relevant from the old repo
[`ronshtricker1210/NLP_project`](https://github.com/ronshtricker1210/NLP_project)
(`main` @ `9719fcb`, 2026-07-25), so you can keep working here without switching repos.
Nothing in the new repo imports or reads it.

**Remove it before you submit:**

```bash
git rm -r _old_repo_context && git commit -m "Remove old-repo context"
```

## What's here

| Path | Contents |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | **Start here.** Timeline, design decisions and how they changed, dropped analyses, old findings, a proposal-vs-final checklist for the report, cluster/GCP/API notes. |
| [`PATH_MAP.md`](PATH_MAP.md) | Every old file and its new counterpart (ported / merged / dropped). |
| [`GIT_HISTORY.md`](GIT_HISTORY.md) | The old repo's full commit log with complete messages, and its one PR. |
| [`diffs/`](diffs/) | Unified diffs old → new for the 14 ported source files, plus `gsm8k_result_tables.diff` for the 11 GSM8K tables that exist in both. New side = `dolev98/NLP_project` `main` @ `f5d6c41`. |
| [`snapshot/`](snapshot/) | Verbatim copy of every file in the old repo at `9719fcb` (74 files, including the proposal PDF and the old `.gitignore`). |

## Most useful old files in `snapshot/`

- `NLP_Project_Proposal.md` and the proposal PDF: what we promised.
- `server-setup/CLUSTER_RUNBOOK.md`: TAU Slurm cluster guide and troubleshooting.
- `gcp-setup/GCP_RUNBOOK.md`: GCP L4 guide, timing, first sanity results.
- `api-setup/README.md`: HF router setup, Hub mirroring layout, billing caveat.
- `full_analysis/README.md`, `full_analysis/report_gsm8k.tex`,
  `full_analysis/tables/gsm8k/`: the first full GSM8K analysis and its tables.
- `DATASET_USAGE.md`, `AGENTS.md`: the old `real0`..`real70` dataset scheme.

The snapshot's `.py` files are for reading only; they use the old paths and are
not meant to run from here.
