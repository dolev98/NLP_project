"""Reasoning length: generated tokens per config, over answered questions.

n_gen_tokens counts every generated token (reasoning plus final answer).
Outputs results/<run>/{reasoning_length_absolute, length_by_outcome}.csv
    NLP_RUN=gsm8k python analysis/reasoning_length.py
"""
import os, sys, json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from common import config_files, parse_tag, load_evals, write_csv, TABLES, RUN  # noqa: E402



def load_tokens(path):
    """{idx: n_gen_tokens} for one config."""
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        out[r["idx"]] = r["n_gen_tokens"]
    return out


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    i = min(len(xs) - 1, int(q * len(xs)))
    return xs[i]


def main():
    files = config_files()
    tags, meta, EV, TOK = [], {}, {}, {}
    for f in files:
        t = parse_tag(f)
        tags.append(t["tag"]); meta[t["tag"]] = t
        EV[t["tag"]] = load_evals(f)
        TOK[t["tag"]] = load_tokens(f)

    # ---- absolute generated-token counts (answered-only) ------------------
    print(f"=== {RUN}: absolute generated tokens (answered-only) ===")
    print(f"{'config':16s}{'n_ans':>7}{'mean':>8}{'median':>8}{'p90':>8}{'max':>7}")
    abs_csv = []
    for tag in tags:
        ev, tok = EV[tag], TOK[tag]
        vals = [tok[i] for i in ev if ev[i]["answered"]]
        mean = sum(vals) / len(vals) if vals else 0
        print(f"{tag:16s}{len(vals):>7}{mean:>8.0f}{median(vals):>8.0f}"
              f"{percentile(vals, 0.9):>8.0f}{max(vals) if vals else 0:>7}")
        abs_csv.append(dict(config=tag,
                            n_answered=len(vals), sum_tok=sum(vals), mean_tok=round(mean, 1),
                            median_tok=median(vals), p90_tok=percentile(vals, 0.9),
                            max_tok=max(vals) if vals else 0))
    write_csv(os.path.join(TABLES, "reasoning_length_absolute.csv"), abs_csv)

    # ---- length vs correctness (answered only) ---------------------------
    # wrong_over_correct = mean tokens of wrong answers / mean tokens of correct answers
    print("\n=== mean tokens by outcome, answered-only (does wrongness cost length?) ===")
    print(f"{'config':16s}{'tok|correct':>13}{'tok|wrong':>11}{'wrong/correct':>15}")
    lc_csv = []
    for tag in tags:
        ev, tok = EV[tag], TOK[tag]
        corr = [tok[i] for i in ev if ev[i]["answered"] and ev[i]["correct"]]
        wrong = [tok[i] for i in ev if ev[i]["answered"] and not ev[i]["correct"]]
        mc = sum(corr)/len(corr) if corr else 0
        mw = sum(wrong)/len(wrong) if wrong else 0
        ratio = mw/mc if mc else 0
        print(f"{tag:16s}{mc:>13.0f}{mw:>11.0f}{ratio:>15.2f}")
        lc_csv.append(dict(config=tag, tok_correct=round(mc,1), tok_wrong=round(mw,1),
                           wrong_over_correct=round(ratio,4),
                           n_correct=len(corr), sum_tok_correct=sum(corr),
                           n_wrong=len(wrong), sum_tok_wrong=sum(wrong)))
    write_csv(os.path.join(TABLES, "length_by_outcome.csv"), lc_csv)

    print(f"\ntables written to {TABLES}")


if __name__ == "__main__":
    main()
