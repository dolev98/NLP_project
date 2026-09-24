"""Self-doubt: frequency of doubt markers in the reasoning, over answered questions.

Two curated marker sets (whole-word, case-insensitive):
  second_guess  explicit reconsideration: wait, hmm, actually, reconsider,
                but wait, hold on, let me recheck, double-check, ...
  uncertainty   hedging: maybe, perhaps, possibly, might be, not sure, ...

Each doubt expression is counted ONCE per category: when several patterns match
overlapping text ("but wait" matches both "but wait" and "wait"; "let me
double-check" matches "let me recheck" and "double-check"), the overlapping
matches are merged into one occurrence.

Reported per config as markers per 1,000 reasoning words (density) and per trace,
and split by final outcome (correct vs wrong).
Outputs results/<run>/{self_doubt_per_config, self_doubt_by_outcome}.csv
    NLP_RUN=gsm8k python analysis/self_doubt.py
"""
import os, sys, re, json

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from common import config_files, parse_tag, load_evals, write_csv, TABLES, RUN  # noqa: E402

# "let me reconsider" is ~0 on this data but kept from the proposal's own examples;
# typo-NOTICING words (typo, misspelled) are repair behaviour, not self-doubt.
MARKER_CATS = {
    "second_guess": {
        "wait":              r"\bwait\b",
        "hmm":               r"\bhm+\b",
        "actually":          r"\bactually\b",
        "reconsider":        r"\breconsider\b",          # incl. "let me reconsider" (~0 here)
        "but wait":          r"\bbut,? wait\b",
        "wait/actually no":  r"\b(?:wait,? no|actually,? no|no,? wait)\b",
        "hold on":           r"\bhold on\b",
        "on second thought": r"\bon second thought\b",
        "let me recheck":    r"\blet me (?:re-?check|recheck|re-?read|reread|verify|redo|double-?check)\b",
        "double-check":      r"\bdouble[- ]?check(?:ing|ed)?\b",
    },
    "uncertainty": {
        "not sure":            r"\b(?:not sure|unsure|not certain|not entirely sure|not totally sure)\b",
        "maybe":               r"\bmaybe\b",
        "perhaps":             r"\bperhaps\b",
        "possibly":            r"\bpossibly\b",
        "might be":            r"\bmight be\b",
        "could be":            r"\bcould be\b",
        "I guess":             r"\bi guess\b",
        "I assume":            r"\bi(?:'?ll)? assume\b",
        "presumably":          r"\bpresumably\b",
        "or maybe/alt":        r"\b(?:or maybe|alternatively|then again)\b",
        "unclear/confused":    r"\b(?:unclear|not clear|isn'?t clear|hard to tell|ambiguous|confus(?:ed|ing))\b",
        "not entirely":        r"\bnot entirely\b",
    },
}
CATS = list(MARKER_CATS)
COMPILED = {cat: [re.compile(rx, re.I) for rx in d.values()] for cat, d in MARKER_CATS.items()}
SHORT = {"second_guess": "2g", "uncertainty": "un", "total": "tot"}


def count_category(text, cat):
    """Number of doubt expressions of one category in text; overlapping matches
    of different patterns count as one expression."""
    spans = sorted((m.start(), m.end()) for rx in COMPILED[cat] for m in rx.finditer(text))
    n, end = 0, -1
    for start, stop in spans:
        if start >= end:
            n += 1
            end = stop
        else:
            end = max(end, stop)
    return n


def count_markers(text):
    """{category: count} and the total over categories for one string."""
    cat_counts = {c: count_category(text, c) for c in CATS}
    return cat_counts, sum(cat_counts.values())


def analyze_file(path):
    """Per answered trace: category counts, reasoning words, outcome."""
    ev = load_evals(path)
    recs = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        e = ev[r["idx"]]
        if not e["answered"]:
            continue
        reasoning = r.get("reasoning", "") or ""
        cat_counts, total = count_markers(reasoning)
        recs.append(dict(idx=r["idx"], cat=cat_counts, total=total,
                         words=max(len(reasoning.split()), 1), correct=e["correct"]))
    return recs


def density(recs, key="total"):
    """Markers per 1,000 reasoning words over a group of traces."""
    cats = CATS if key == "total" else [key]
    m = sum(sum(x["cat"][c] for c in cats) for x in recs)
    w = sum(x["words"] for x in recs)
    return (m / w * 1000) if w else 0.0


def per_trace(recs, key="total"):
    """Mean markers per trace."""
    if not recs:
        return 0.0
    cats = CATS if key == "total" else [key]
    return sum(sum(x["cat"][c] for c in cats) for x in recs) / len(recs)


def main():
    tags, DATA = [], {}
    for f in config_files():
        t = parse_tag(f)
        tags.append(t["tag"])
        DATA[t["tag"]] = analyze_file(f)

    print(f"=== {RUN}: doubt markers per 1,000 reasoning words (answered only) ===")
    print(f"{'config':16s}{'n_ans':>7}" + "".join(f"{c + '/1k':>16}" for c in CATS + ["total"]))
    sum_csv = []
    for tag in tags:
        recs = DATA[tag]
        row = dict(config=tag, n_answered=len(recs))
        for c in CATS:
            row[f"{c}_per_1k"] = round(density(recs, c), 3)
            row[f"{c}_per_trace"] = round(per_trace(recs, c), 3)
        row["total_per_1k"] = round(density(recs, "total"), 3)
        row["total_per_trace"] = round(per_trace(recs, "total"), 3)
        for c in CATS:
            row[f"{c}_n"] = sum(x["cat"][c] for x in recs)
        row["words"] = sum(x["words"] for x in recs)
        print(f"{tag:16s}{len(recs):>7}" + "".join(
            f"{row[c + '_per_1k'] if c != 'total' else row['total_per_1k']:>16.2f}"
            for c in CATS + ["total"]))
        sum_csv.append(row)
    write_csv(os.path.join(TABLES, "self_doubt_per_config.csv"), sum_csv)

    print("\n=== density by outcome (w/c = wrong over correct) ===")
    oc_csv = []
    for tag in tags:
        recs = DATA[tag]
        corr = [x for x in recs if x["correct"]]
        wrong = [x for x in recs if not x["correct"]]
        row = {"config": tag}
        for k in CATS + ["total"]:
            dc, dw = density(corr, k), density(wrong, k)
            wc = dw / dc if dc else 0
            row[f"{SHORT[k]}_correct"] = round(dc, 3)
            row[f"{SHORT[k]}_wrong"] = round(dw, 3)
            row[f"{SHORT[k]}_wrong_over_correct"] = round(wc, 3)
        for k in CATS:
            row[f"{SHORT[k]}_n_correct"] = sum(x["cat"][k] for x in corr)
            row[f"{SHORT[k]}_n_wrong"] = sum(x["cat"][k] for x in wrong)
        row["words_correct"] = sum(x["words"] for x in corr)
        row["words_wrong"] = sum(x["words"] for x in wrong)
        print(f"{tag:16s}" + "".join(f"{row[SHORT[k] + '_wrong_over_correct']:>10.2f}"
                                     for k in CATS + ["total"]))
        oc_csv.append(row)
    write_csv(os.path.join(TABLES, "self_doubt_by_outcome.csv"), oc_csv)
    print(f"\ntables written to {TABLES}")


if __name__ == "__main__":
    main()
