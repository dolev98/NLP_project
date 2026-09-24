#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build the typo datasets: typo rate r x real-word ratio rho, plus a clean config.

    python data_creation/generate_variants.py --clean                 # the untouched 'clean' configs
    python data_creation/generate_variants.py                         # r in {25,50,75}% x rho in {10,40,70}%
    python data_creation/generate_variants.py --datasets arc --subset 20   # quick check on 20 rows
    python data_creation/generate_variants.py --push --namespace <hf-user> # also publish to the Hub

Each variant is saved with save_to_disk under <out>/<dataset>/<config> and, with
--push, becomes config <config> of <namespace>/<dataset>-typos, e.g.

    load_dataset("idoazou/gsm8k-typos", "rate25_real10", split="test")

The published datasets (idoazou/{gsm8k,math500,arc}-typos) were made with the
defaults below (seed 42, two-edit probability 0.10): all 1,319 GSM8K test
questions, all 500 MATH-500 questions, and the first 500 four-choice
ARC-Challenge test questions. See typo_pipeline.py for the algorithm.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from typo_pipeline import Config, load_source, process_row


def _prepare_arc(dataset):
    """Map ARC rows to a four-option multiple-choice schema; drop questions that
    do not have exactly four options. answerKey uses the row's own label
    alphabet (A-D or 1-4), so the correct option is found by label."""
    dataset = dataset.filter(lambda r: len(r["choices"]["text"]) == 4)

    def to_mc(row):
        texts, labels = row["choices"]["text"], row["choices"]["label"]
        i = labels.index(row["answerKey"])
        wrong = [t for j, t in enumerate(texts) if j != i]
        return {"Question": row["question"], "Correct Answer": texts[i],
                "Incorrect Answer 1": wrong[0], "Incorrect Answer 2": wrong[1],
                "Incorrect Answer 3": wrong[2], "Record ID": row["id"]}

    return dataset.map(to_mc, remove_columns=dataset.column_names)


PRESETS: Dict[str, Dict[str, Any]] = {
    "gsm8k": {
        "dataset_name": "openai/gsm8k",
        "dataset_config_name": "main",
        "dataset_split": "test",
        "text_field": "question",
        "hub_repo": "gsm8k-typos",
        "rows": None,            # all 1,319 test questions
    },
    "math500": {
        "dataset_name": "HuggingFaceH4/MATH-500",
        "dataset_config_name": None,
        "dataset_split": "test",
        "text_field": "problem",
        "hub_repo": "math500-typos",
        "rows": None,            # all 500 questions
    },
    "arc": {
        "dataset_name": "allenai/ai2_arc",
        "dataset_config_name": "ARC-Challenge",
        "dataset_split": "test",
        "text_field": "Question",
        "hub_repo": "arc-typos",
        "rows": 500,             # first 500 of the 1,165 four-option questions
        "prepare": _prepare_arc,
    },
}

TYPO_RATES = [0.25, 0.50, 0.75]
REAL_RATIOS = [0.10, 0.40, 0.70]


def config_name(rate: float, ratio: float) -> str:
    return f"rate{int(round(rate * 100))}_real{int(round(ratio * 100))}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the controlled typo datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--datasets", nargs="+", choices=sorted(PRESETS),
                        default=["gsm8k", "math500", "arc"])
    parser.add_argument("--typo-rates", nargs="+", type=float, default=TYPO_RATES,
                        help="fractions of eligible words to corrupt")
    parser.add_argument("--ratios", nargs="+", type=float, default=REAL_RATIOS,
                        help="target real-word ratios in [0, 1]")
    parser.add_argument("--two-edit-prob", type=float, default=0.10,
                        help="probability a typo consists of two edits")
    parser.add_argument("--subset", type=int, default=None,
                        help="only the first N rows (default: the published row count)")
    parser.add_argument("--seed", type=int, default=42,
                        help="base seed; row i uses seed + i, so variants are paired")
    parser.add_argument("--num-proc", type=int, default=1,
                        help="parallel workers for datasets.map")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "typo_variants",
                        help="local output root")
    parser.add_argument("--clean", action="store_true",
                        help="only produce the untouched 'clean' config per dataset")
    parser.add_argument("--push", action="store_true",
                        help="push each variant to the Hugging Face Hub")
    parser.add_argument("--namespace", type=str, default=None,
                        help="HF user or org to push to (required with --push)")
    parser.add_argument("--private", action="store_true",
                        help="create the Hub repos as private")
    args = parser.parse_args()

    for r in args.ratios + args.typo_rates:
        if not 0.0 <= r <= 1.0:
            parser.error(f"value {r} outside [0, 1]")
    if args.push and not args.namespace:
        parser.error("--push requires --namespace <hf-username>")
    return args


def build_config(preset: Dict[str, Any], rate: float, ratio: float,
                 args: argparse.Namespace) -> Config:
    # Presets with a prepare hook filter rows, so their subset is taken afterwards.
    subset = 10**9 if preset.get("prepare") else (args.subset or preset["rows"] or 10**9)
    return Config(
        dataset_name=preset["dataset_name"],
        dataset_config_name=preset["dataset_config_name"],
        dataset_split=preset["dataset_split"],
        text_field=preset["text_field"],
        subset_size=subset,
        typo_rate=rate,
        target_real_fraction=ratio,
        two_edit_prob=args.two_edit_prob,
        num_proc=args.num_proc,
        seed=args.seed,
    )


def load_rows(preset: Dict[str, Any], config: Config, args: argparse.Namespace):
    dataset = load_source(config)
    if preset.get("prepare"):
        dataset = preset["prepare"](dataset)
        n = args.subset or preset["rows"] or len(dataset)
        dataset = dataset.select(range(min(n, len(dataset))))
    return dataset


def variant_stats(processed) -> Dict[str, Any]:
    ratios = [r for r in processed["real_ratio"] if r == r]          # drop NaN
    totals = processed["num_total"]
    edit_counts = [c for row in processed["typo_edit_counts"] for c in row]
    return {
        "rows": len(processed),
        "mean_ratio": sum(ratios) / len(ratios) if ratios else float("nan"),
        "mean_typos": sum(totals) / len(totals),
        "min_typos": min(totals),
        "two_edit_pct": 100.0 * sum(1 for c in edit_counts if c == 2) / max(1, len(edit_counts)),
    }


def save_and_push(dataset, preset_key: str, name: str, args: argparse.Namespace) -> None:
    out_dir = Path(args.out) / preset_key / name
    dataset.save_to_disk(str(out_dir))
    print(f"[save] {out_dir} ({len(dataset)} rows)")
    if args.push:
        repo_id = f"{args.namespace}/{PRESETS[preset_key]['hub_repo']}"
        dataset.push_to_hub(repo_id, config_name=name, split="test", private=args.private)
        print(f"[push] {repo_id} config={name}")


def main() -> None:
    args = parse_args()
    if args.clean:
        for preset_key in args.datasets:
            preset = PRESETS[preset_key]
            save_and_push(load_rows(preset, build_config(preset, 0.0, 0.0, args), args),
                          preset_key, "clean", args)
        return

    summary: List[Dict[str, Any]] = []
    for preset_key in args.datasets:
        preset = PRESETS[preset_key]
        for rate in sorted(args.typo_rates):
            for ratio in sorted(args.ratios):
                name = config_name(rate, ratio)
                config = build_config(preset, rate, ratio, args)
                print(f"\n=== {preset_key} / {name} ===")
                dataset = load_rows(preset, config, args)
                map_kwargs = {"num_proc": config.num_proc} if config.num_proc > 1 else {}
                processed = dataset.map(process_row, with_indices=True,
                                        fn_kwargs={"config": config},
                                        desc=f"{preset_key}/{name}", **map_kwargs)
                stats = variant_stats(processed)
                print(f"rows={stats['rows']}  achieved real-word ratio={stats['mean_ratio']:.3f}  "
                      f"typos/question={stats['mean_typos']:.1f} (min {stats['min_typos']})  "
                      f"two-edit typos={stats['two_edit_pct']:.1f}%")
                save_and_push(processed, preset_key, name, args)
                summary.append({"dataset": preset_key, "config": name, **stats})

    print("\n" + "=" * 72)
    print(f"{'dataset':<9} {'config':<14} {'rows':>5} {'real ratio':>11} "
          f"{'typos/q':>8} {'2-edit%':>8}")
    for s in summary:
        print(f"{s['dataset']:<9} {s['config']:<14} {s['rows']:>5} {s['mean_ratio']:>11.3f} "
              f"{s['mean_typos']:>8.1f} {s['two_edit_pct']:>7.1f}%")


if __name__ == "__main__":
    main()
