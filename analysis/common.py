"""Shared loading, scoring and statistics for the analysis modules.

A *run* is one set of generations: a dataset, optionally under a mitigation.
The run is chosen with the NLP_RUN environment variable (run_all.py --run sets it):

    gsm8k  math500  arc  gsm8k_warn  gsm8k_rewrite  gsm8k_spellcheck

Raw generations are read from data/raw/<run>/<run>_<config>.jsonl and tables are
written to results/<run>/. <config> is "clean" or "typo<r>_real<rho>".

Answers are read from the FINAL section only (after </think>), never from
mid-reasoning. A trace with no extractable answer there is UNANSWERED rather than
wrong, which keeps "did not finish" apart from "answered wrongly".
"""
import os, sys, json, glob, re, random, math

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "inference"))
from score import gold_gsm8k, extract_pred, is_correct  # noqa: E402

# ---- run selection ---------------------------------------------------------
# run -> (dataset, generation cap in tokens used for that run)
RUNS = {
    "gsm8k":            ("gsm8k", 20000),
    "math500":          ("math500", 17000),
    "arc":              ("arc", 17000),
    "gsm8k_warn":       ("gsm8k", 20000),
    "gsm8k_rewrite":    ("gsm8k", 20000),
    "gsm8k_spellcheck": ("gsm8k", 20000),
}
# dataset -> (how score.py extracts/compares answers, how to read the gold field)
DATASETS = {
    "gsm8k":   {"kind": "gsm8k_num", "gold": lambda r: gold_gsm8k(r["gold_answer"])},
    "math500": {"kind": "math",      "gold": lambda r: r["gold_answer"]},
    "arc":     {"kind": "mc",        "gold": lambda r: r["gold_answer"]},
}

RUN = os.environ.get("NLP_RUN", "gsm8k")
if RUN not in RUNS:
    raise SystemExit(f"unknown NLP_RUN={RUN!r}; choices: {list(RUNS)}")
BASE_DATASET, MAX_NEW_TOKENS = RUNS[RUN]
DATA_DIR = os.path.join(REPO, "data", "raw", RUN)
TABLES = os.path.join(REPO, "results", RUN)
os.makedirs(TABLES, exist_ok=True)

CONFIG_RE = re.compile(r"clean|typo(\d+)_real(\d+)")


# ---- config identity -------------------------------------------------------
def parse_tag(path):
    """<run>_clean.jsonl -> {'tag':'clean',...};
       <run>_typo50_real40.jsonl -> {'tag':'typo50_real40','rate':50,'real':40}."""
    base = os.path.basename(path)[len(RUN) + 1:-len(".jsonl")]
    m = CONFIG_RE.fullmatch(base)
    if not m:
        raise ValueError(f"not a result file of run {RUN}: {path}")
    if base == "clean":
        return {"tag": "clean", "rate": 0, "real": None, "is_clean": True}
    return {"tag": base, "rate": int(m.group(1)), "real": int(m.group(2)), "is_clean": False}


def config_files():
    """The run's result files: clean first, then typo configs by (rate, real).
    Only <run>_clean.jsonl and <run>_typo<r>_real<rho>.jsonl are picked up."""
    files = [f for f in glob.glob(os.path.join(glob.escape(DATA_DIR), f"{RUN}_*.jsonl"))
             if CONFIG_RE.fullmatch(os.path.basename(f)[len(RUN) + 1:-len(".jsonl")])]
    if not files:
        raise SystemExit(f"no data for run '{RUN}' in {DATA_DIR}\n"
                         f"  run:  python analysis/download_data.py --run {RUN}")
    def key(f):
        t = parse_tag(f)
        return (0, 0, 0) if t["is_clean"] else (1, t["rate"], t["real"])
    return sorted(files, key=key)


# ---- per-row evaluation ----------------------------------------------------
def _kind_gold(row):
    spec = DATASETS[BASE_DATASET]
    return spec["kind"], spec["gold"](row)


def extract_answer(final_text, kind):
    """Predicted answer from the FINAL section only. None => unanswered."""
    return extract_pred(final_text or "", kind, final_text or "")


def eval_row(row):
    """state is one of: "correct", "wrong", "unanswered"."""
    kind, gold = _kind_gold(row)
    pred = extract_answer(row.get("final_answer_text", "") or "", kind)
    answered = pred is not None
    correct = bool(answered and is_correct(kind, pred, gold))
    state = "correct" if correct else ("unanswered" if not answered else "wrong")
    return {
        "idx": row["idx"],
        "pred": pred,
        "gold": gold,
        "answered": answered,
        "correct": correct,
        "state": state,
        "n_gen_tokens": row.get("n_gen_tokens"),
        "capped": (row.get("n_gen_tokens") or 0) >= MAX_NEW_TOKENS,
    }


def load_evals(path):
    """{idx: eval_dict} for one config file (one sample per question)."""
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        out[r["idx"]] = eval_row(r)
    return out


# ---- statistics ------------------------------------------------------------
def bootstrap_ci(bools, n_boot=2000, alpha=0.05, seed=0):
    """95% percentile-bootstrap CI for the mean of a 0/1 list."""
    xs = [1 if b else 0 for b in bools]
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return (means[int((alpha / 2) * n_boot)], means[int((1 - alpha / 2) * n_boot)])


def mcnemar(base_correct, cfg_correct):
    """Continuity-corrected McNemar test on paired correctness.
    base/cfg are dicts idx->bool; only shared idx count.
    Returns (b, c, stat, p): b = base-right/cfg-wrong, c = base-wrong/cfg-right."""
    b = c = 0
    for idx, bo in base_correct.items():
        if idx not in cfg_correct:
            continue
        co = cfg_correct[idx]
        if bo and not co:
            b += 1
        elif not bo and co:
            c += 1
    n = b + c
    if n == 0:
        return b, c, 0.0, 1.0
    stat = max(abs(b - c) - 1, 0) ** 2 / n     # chi-square, 1 df
    return b, c, stat, math.erfc(math.sqrt(stat / 2.0))


def sig6(p):
    """A p-value rounded to 6 significant digits (never collapses small p to 0)."""
    return float(f"{p:.6g}")


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, in the input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj


def write_csv(path, rows):
    """Write dict rows; the header is the union of keys in first-seen order."""
    import csv
    if not rows:
        return
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
