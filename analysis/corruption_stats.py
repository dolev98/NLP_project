"""Corruption statistics of the typo datasets as used in the runs (report Table 1).

Counts, per main run, over its first 500 questions:
  words per question            whitespace-separated tokens of the clean question
  eligible words per question   words the generator may corrupt (same rule as
                                data_creation/typo_pipeline.py)
  typos per config              num_total summed over questions
  real-word typos per config    num_real summed over questions
Output results/<run>/corruption_stats.csv (skipped for mitigation arms). For gsm8k it
also writes figure1_example.json, the worked example in the report's Figure 1:
question 0 clean and at r=25%, rho=40%, with the model's answers, which typos are
real words (nltk.corpus.words, as in the generator) and which of those the spell
checker of the spell-check arm (pyspellchecker, edit distance 2) accepts as spelled
correctly.
    NLP_RUN=gsm8k python analysis/corruption_stats.py
"""
import os, sys, json

from common import config_files, parse_tag, write_csv, eval_row, TABLES, RUN, REPO

sys.path.insert(0, os.path.join(REPO, "data_creation"))
from typo_pipeline import (Config, find_protected_spans, _WORD_PATTERN, _overlaps_any,  # noqa: E402
                           get_nltk_word_set)
from repair_wordlevel import corrupted_pairs  # noqa: E402

EXAMPLE = ("typo25_real40", 0)     # (config, question idx) shown in Figure 1
from keyboard_typos import KeyboardTypoGenerator  # noqa: E402

IGNORE = KeyboardTypoGenerator(use_excluding_set=True).ignore_set
MIN_LEN = Config().min_word_len


def eligible_words(text):
    spans = find_protected_spans(text)
    return sum(1 for m in _WORD_PATTERN.finditer(text)
               if len(m.group()) >= MIN_LEN and not _overlaps_any(m.start(), m.end(), spans)
               and m.group().lower() not in IGNORE)


def main():
    if RUN not in ("gsm8k", "math500", "arc"):
        print(f"[corruption_stats] {RUN}: mitigation arm, same questions as its dataset; skipped")
        return
    rows = []
    for path in config_files():
        meta = parse_tag(path)
        recs = [json.loads(l) for l in open(path, encoding="utf-8")]
        row = dict(config=meta["tag"], n_questions=len(recs))
        if meta["is_clean"]:
            words = sorted(len(r["clean_question"].split()) for r in recs)
            row.update(words_total=sum(words),
                       words_median=(words[len(words) // 2] + words[(len(words) - 1) // 2]) / 2,
                       eligible_total=sum(eligible_words(r["clean_question"]) for r in recs))
        else:
            row.update(typos_total=sum(r["num_total"] for r in recs),
                       real_typos_total=sum(r["num_real"] for r in recs))
        rows.append(row)
    write_csv(os.path.join(TABLES, "corruption_stats.csv"), rows)
    if RUN == "gsm8k":
        write_example()
    print(f"tables written to {TABLES}")


def write_example():
    cfg, idx = EXAMPLE
    def row(tag):
        path = next(f for f in config_files() if parse_tag(f)["tag"] == tag)
        return next(r for r in map(json.loads, open(path, encoding="utf-8")) if r["idx"] == idx)
    clean, typo = row("clean"), row(cfg)
    ec, et = eval_row(clean), eval_row(typo)
    words = get_nltk_word_set()
    from spellchecker import SpellChecker
    checker = SpellChecker(distance=2)
    pairs = corrupted_pairs(typo["clean_question"], typo["typo_question"])
    json.dump({
        "config": cfg, "idx": idx, "gold": ec["gold"],
        "clean_question": clean["clean_question"], "typo_question": typo["typo_question"],
        "clean_answer": ec["pred"], "clean_correct": ec["correct"],
        "typo_answer": et["pred"], "typo_correct": et["correct"],
        "typos": [{"original": o, "typo": t, "real_word": t.lower() in words,
                   "spellchecker_accepts": not checker.unknown([t.lower()])} for o, t in pairs],
        "num_total": typo["num_total"], "num_real": typo["num_real"],
    }, open(os.path.join(TABLES, "figure1_example.json"), "w", encoding="utf-8"),
        indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
