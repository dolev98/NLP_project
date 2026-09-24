"""Isolating the real-word effect: does the KIND of typo matter, not just the number?

Within a fixed typo rate, the rho=10/40/70 variants corrupt the SAME words in the
SAME positions of the SAME question; only whether a typo lands on a valid word
differs. Every row also records how many real-word and non-word typos it got.

1. Controlled paired comparison: same question and rate, lower vs higher rho,
   over questions answered in both, McNemar test (Holm-corrected over the nine
   contrasts of the run).
2. Per-typo harm: logistic regression  correct ~ num_real + num_nonword  over all
   answered typo questions; compares the damage of one real-word vs one non-word typo.
   95% intervals come from a bootstrap over questions (each question appears in up to
   nine configs, so questions, not traces, are resampled). The ratio of the two
   losses is only meaningful when the non-word coefficient is clearly below zero.

Outputs results/<run>/{realword_paired, realword_pertypo_logit}.csv
    NLP_RUN=gsm8k python analysis/real_word_effect.py
"""
import os, sys, json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
from sklearn.linear_model import LogisticRegression

from common import config_files, parse_tag, load_evals, mcnemar, holm, sig6, write_csv, TABLES  # noqa: E402


def load_records(path):
    """{idx: rec} for answered rows, with correctness + typo-count metadata."""
    ev = load_evals(path)
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        e = ev[r["idx"]]
        if not e["answered"]:
            continue
        out[r["idx"]] = dict(idx=r["idx"], correct=e["correct"],
                             num_real=r.get("num_real", 0), num_nonword=r.get("num_nonword", 0),
                             num_total=r.get("num_total", 0))
    return out


def main():
    files = config_files()
    D, meta = {}, {}
    for f in files:
        t = parse_tag(f)
        meta[t["tag"]] = t
        D[t["tag"]] = load_records(f)
    rates = sorted({meta[t]["rate"] for t in meta if not meta[t]["is_clean"]})

    # ---- 1. CONTROLLED PAIRED comparison within each rate -----------------
    print("=== 1. controlled paired comparison: same question+rate, low vs high real-word ===")
    print("(real10 = mostly NON-word typos, real70 = mostly REAL-word; same corrupted positions)\n")
    print(f"{'rate':>6}{'compare':>14}{'n_both':>8}{'acc_low':>9}{'acc_high':>10}"
          f"{'Δacc':>8}{'r→w':>6}{'w→r':>6}{'McNemar p':>12}")
    paired_csv, exact_p = [], []
    for rate in rates:
        for lo, hi in [(10, 70), (10, 40), (40, 70)]:
            A = D.get(f"typo{rate}_real{lo}", {})
            B = D.get(f"typo{rate}_real{hi}", {})
            shared = [i for i in A if i in B]
            n = len(shared)
            if not n:
                continue
            accA = sum(A[i]["correct"] for i in shared) / n
            accB = sum(B[i]["correct"] for i in shared) / n
            r2w = sum(1 for i in shared if A[i]["correct"] and not B[i]["correct"])
            w2r = sum(1 for i in shared if not A[i]["correct"] and B[i]["correct"])
            _, _, _, p = mcnemar({i: A[i]["correct"] for i in shared},
                                 {i: B[i]["correct"] for i in shared})
            pstr = f"{p:.2e}"
            print(f"{rate:>5}%{f'real{lo}→{hi}':>14}{n:>8}{accA:>9.1%}{accB:>10.1%}"
                  f"{accB-accA:>+8.1%}{r2w:>6}{w2r:>6}{pstr:>12}")
            paired_csv.append(dict(rate=rate, compare=f"real{lo}_to_real{hi}", n_both=n,
                                   acc_low_real=round(accA, 4), acc_high_real=round(accB, 4),
                                   delta_acc=round(accB - accA, 4), r2w=r2w, w2r=w2r,
                                   mcnemar_p=sig6(p)))
            exact_p.append(p)
    for row, adj in zip(paired_csv, holm(exact_p)):
        row["mcnemar_p_holm"] = sig6(adj)
    write_csv(os.path.join(TABLES, "realword_paired.csv"), paired_csv)
    print("\n  Δacc<0 with r→w>w→r  => real-word typos are MORE harmful than the non-word\n"
          "  typos they replaced (same question, same positions).")

    # ---- 2. PER-TYPO harm: logistic regression ----------------------------
    print("\n=== 2. per-typo harm: logistic regression  correct ~ num_real + num_nonword ===")
    rows = [r for tag in D if not meta[tag]["is_clean"] for r in D[tag].values()]
    X = np.array([[r["num_real"], r["num_nonword"]] for r in rows], dtype=float)
    y = np.array([1 if r["correct"] else 0 for r in rows])
    clf = LogisticRegression(max_iter=1000, C=1e6)  # ~unregularised
    clf.fit(X, y)
    b_real, b_non = clf.coef_[0]

    # bootstrap over questions (all of a question's typo traces move together)
    qid = np.array([r["idx"] for r in rows])
    uniq = np.unique(qid)
    members = {q: np.flatnonzero(qid == q) for q in uniq}
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(1000):
        pick = np.concatenate([members[q] for q in rng.choice(uniq, size=len(uniq))])
        if y[pick].min() == y[pick].max():
            continue
        c = LogisticRegression(max_iter=1000, C=1e6).fit(X[pick], y[pick]).coef_[0]
        boot.append(c)
    boot = np.array(boot)
    ci = lambda v: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
    real_ci, non_ci = ci(boot[:, 0]), ci(boot[:, 1])
    rel_ci = ci((1 - np.exp(boot[:, 0])) / (1 - np.exp(boot[:, 1])))
    print(f"  n={len(rows)} answered typo traces")
    print(f"  per REAL-word typo : log-odds {b_real:+.4f}  (odds x{np.exp(b_real):.3f} on correctness)")
    print(f"  per NON-word typo  : log-odds {b_non:+.4f}  (odds x{np.exp(b_non):.3f} on correctness)")
    worse = "REAL-word" if b_real < b_non else "NON-word"
    print(f"  => each {worse} typo hurts correctness more (more negative log-odds).")
    rel = (1 - np.exp(b_real)) / (1 - np.exp(b_non))
    print(f"  odds lost per real-word typo / per non-word typo = {rel:.3f}"
          f"  (95% CI {rel_ci[0]:.2f} to {rel_ci[1]:.2f}; non-word coef CI "
          f"{non_ci[0]:+.4f} to {non_ci[1]:+.4f})")
    write_csv(os.path.join(TABLES, "realword_pertypo_logit.csv"), [dict(
        n=len(rows), coef_num_real=round(b_real, 5), coef_num_nonword=round(b_non, 5),
        odds_real=round(float(np.exp(b_real)), 4), odds_nonword=round(float(np.exp(b_non)), 4),
        intercept=round(float(clf.intercept_[0]), 5),
        relative_loss_real_vs_nonword=round(float(rel), 4),
        coef_real_ci_lo=round(real_ci[0], 5), coef_real_ci_hi=round(real_ci[1], 5),
        coef_nonword_ci_lo=round(non_ci[0], 5), coef_nonword_ci_hi=round(non_ci[1], 5),
        relative_loss_ci_lo=round(rel_ci[0], 3), relative_loss_ci_hi=round(rel_ci[1], 3),
        n_bootstrap=len(boot))])

    print(f"\ntables written to {TABLES}")


if __name__ == "__main__":
    main()
