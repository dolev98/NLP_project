"""How many typos the external spell checker restored (spell-check arm only).

run_typo_api.py --fix spellcheck stores, per question, how many of the injected
typos pyspellchecker changed back to exactly the original word
(spellcheck_restored_exact_n out of spellcheck_total_typo_words).

Outputs results/<run>/
  spellcheck_recovery_per_config.csv  per typo config, pooled over its typo words
  spellcheck_recovery_by_real.csv     per real-word ratio: pooled over all typo
                                      words of the three rates, and the unweighted
                                      mean of the three per-rate values
  spellcheck_recovery_overall.csv     all typo configs pooled
Runs without spell-check metadata are skipped.
    NLP_RUN=gsm8k_spellcheck python analysis/spellcheck_recovery.py
"""
import os, json
from collections import defaultdict

from common import config_files, parse_tag, write_csv, TABLES, RUN


def spell_rows(path):
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        total = row.get("spellcheck_total_typo_words")
        restored = row.get("spellcheck_restored_exact_n")
        if isinstance(total, int) and isinstance(restored, int):
            yield {"total": total, "restored": restored,
                   "changed_other": int(row.get("spellcheck_changed_other_n") or 0)}


def main():
    per_cfg = []
    for path in config_files():
        meta = parse_tag(path)
        rows = list(spell_rows(path))
        if meta["is_clean"] or not rows:
            continue
        total = sum(r["total"] for r in rows)
        restored = sum(r["restored"] for r in rows)
        per_cfg.append({
            "config": meta["tag"], "rate": meta["rate"], "real": meta["real"],
            "n_questions": len(rows),
            "total_typo_words": total,
            "restored_exact_n": restored,
            # changed, but not to the original word
            "changed_other_n": sum(r["changed_other"] for r in rows),
            # left as typed (not changed at all)
            "unchanged_n": total - restored - sum(r["changed_other"] for r in rows),
            "restored_exact_pct": round(100.0 * restored / total, 2) if total else 0.0,
        })
    if not per_cfg:
        print(f"[spellcheck_recovery] {RUN}: no spell-check metadata, nothing to do")
        return
    write_csv(os.path.join(TABLES, "spellcheck_recovery_per_config.csv"), per_cfg)

    by_real = defaultdict(list)
    for r in per_cfg:
        by_real[r["real"]].append(r)
    real_rows = []
    for real in sorted(by_real):
        g = by_real[real]
        total = sum(r["total_typo_words"] for r in g)
        restored = sum(r["restored_exact_n"] for r in g)
        real_rows.append({
            "real": real, "total_typo_words": total, "restored_exact_n": restored,
            "restored_pooled_pct": round(100.0 * restored / total, 2),
            "restored_mean_of_rates_pct": round(
                sum(100.0 * r["restored_exact_n"] / r["total_typo_words"] for r in g) / len(g), 2),
        })
        print(f"real{real}: {real_rows[-1]['restored_pooled_pct']:.2f}% restored "
              f"(pooled over {total} typo words)")
    write_csv(os.path.join(TABLES, "spellcheck_recovery_by_real.csv"), real_rows)

    total = sum(r["total_typo_words"] for r in per_cfg)
    restored = sum(r["restored_exact_n"] for r in per_cfg)
    write_csv(os.path.join(TABLES, "spellcheck_recovery_overall.csv"), [{
        "run": RUN, "configs": len(per_cfg), "total_typo_words": total,
        "restored_exact_n": restored,
        "restored_exact_pct": round(100.0 * restored / total, 2)}])
    print(f"tables written to {TABLES}")


if __name__ == "__main__":
    main()
