"""Repair behaviour, grounded in the actual corrupted words.

Every (original -> corrupted) word pair is recovered by aligning the clean question
with the question the model was shown, word by word: typos replace a word in place,
so the i-th word of one text corresponds to the i-th word of the other (this
reproduces the generator's own typo lists exactly). In the spell-check arm the shown
question is the spell-checked one, so words the checker restored are not typos and
its miscorrections are. For each pair we check which form the reasoning trace uses
(whole word, case-insensitive, words of length >= 3):

  silent fix  (RECOVERED) original present, corrupted form absent
  flagged     (NOTICED)   both forms present
  misread     (ECHOED)    corrupted form present, original absent
  not used    (UNUSED)    neither form present

Baseline control. A real-word typo form is often an ordinary word ("form" ->
"from") that the model would write anyway, so its presence says nothing about
how the typo was read. A pair is therefore UNINFORMATIVE, and left out of the
four shares, when its corrupted form appears in the trace AND also appears in
the model's reasoning on the clean version of the same question (same run).
The number of such pairs is reported separately.

Answered questions only. Outputs
results/<run>/{repair_wordlevel_per_config, repair_wordlevel_by_outcome}.csv
    NLP_RUN=gsm8k python analysis/repair_wordlevel.py
"""
import os, sys, re, json, difflib
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from common import config_files, parse_tag, load_evals, write_csv, TABLES  # noqa: E402
WORD = re.compile(r"[A-Za-z]+")      # the generator's word pattern (typo_pipeline._WORD_PATTERN)
MIN_LEN = 3   # ignore very short words (the/of/a) — they match trivially


def corrupted_pairs(clean, typo):
    """[(original, corrupted), ...] for the words that differ between clean and typo.
    Aligned by position; falls back to difflib only if the word counts differ."""
    cw, tw = WORD.findall(clean), WORD.findall(typo)
    if len(cw) == len(tw):
        return [(a, b) for a, b in zip(cw, tw) if a != b]
    sm = difflib.SequenceMatcher(a=[w.lower() for w in cw], b=[w.lower() for w in tw])
    pairs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            a, b = cw[i1:i2], tw[j1:j2]
            for k in range(min(len(a), len(b))):   # position-align within the block
                if a[k].lower() != b[k].lower():
                    pairs.append((a[k], b[k]))
    return pairs


def present(word, reasoning_low):
    """Whole-word, case-insensitive membership in the (lowercased) reasoning."""
    if len(word) < MIN_LEN:
        return False
    return re.search(r"\b" + re.escape(word.lower()) + r"\b", reasoning_low) is not None


def classify_word(orig, typo, reasoning_low):
    o = present(orig, reasoning_low)
    t = present(typo, reasoning_low)
    if o and not t:
        return "recovered"
    if o and t:
        return "noticed"
    if t and not o:
        return "echoed"
    return "unused"


def clean_reasoning(files):
    """{idx: lower-cased reasoning} from the run's clean config."""
    clean = next(f for f in files if parse_tag(f)["is_clean"])
    out = {}
    for line in open(clean, encoding="utf-8"):
        r = json.loads(line)
        out[r["idx"]] = (r.get("reasoning", "") or "").lower()
    return out


def analyze_file(path, clean_low):
    ev = load_evals(path)
    rows = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        e = ev[r["idx"]]
        if not e["answered"]:
            continue
        reasoning_low = (r.get("reasoning", "") or "").lower()
        shown = r.get("spellchecked_question") or r["typo_question"]
        pairs = corrupted_pairs(r["clean_question"], shown)
        base_low = clean_low.get(r["idx"], "")
        cats = Counter()
        usable = excluded = 0
        for orig, typo in pairs:
            if len(orig) < MIN_LEN:      # skip words we can't reliably search
                continue
            if present(typo, reasoning_low) and present(typo, base_low):
                excluded += 1            # corrupted form is used even without the typo
                continue
            usable += 1
            cats[classify_word(orig, typo, reasoning_low)] += 1
        rows.append(dict(idx=r["idx"], correct=e["correct"], cats=cats,
                         usable=usable, excluded=excluded))
    return rows


CATS = ("recovered", "noticed", "echoed", "unused")


def dist(recs):
    """Pooled per-word category counts and fractions over problem records.
    Returns (fractions, counts, total)."""
    tot = Counter()
    for r in recs:
        tot.update(r["cats"])
    n = sum(tot.values()) or 1
    counts = {k: tot[k] for k in CATS}
    return {k: counts[k] / n for k in CATS}, counts, n


def main():
    files = config_files()
    clean_low = clean_reasoning(files)
    tags, DATA = [], {}
    for f in files:
        t = parse_tag(f)
        if t["is_clean"]:
            continue      # clean has no corrupted words
        tags.append(t["tag"])
        DATA[t["tag"]] = analyze_file(f, clean_low)

    # ---- per-config word-handling distribution ---------------------------
    print("=== how the model handled each corrupted word, per config (answered-only) ===")
    print("Each corrupted word (from diffing clean vs typo) goes in ONE bucket by which form the")
    print("reasoning used. Columns are the % share of that config's corrupted words:")
    print("  n_corrupt_words = total corrupted words examined (the denominator)")
    print("  silent_fix%     = used ONLY the original word        (recovered silently)")
    print("  flagged%        = used BOTH the typo and the original (noticed & fixed)")
    print("  misread%        = used ONLY the corrupted word        (echoed / read as wrong word)")
    print("  not_used%       = neither form appears in the reasoning")
    print("  excluded        = corrupted form also used on the clean question (left out)\n")
    print(f"{'config':16s}{'n_corrupt_words':>16}{'silent_fix%':>12}{'flagged%':>10}"
          f"{'misread%':>10}{'not_used%':>11}")
    cfg_csv = []
    for tag in tags:
        d, c, n = dist(DATA[tag])
        excluded = sum(r["excluded"] for r in DATA[tag])
        print(f"{tag:16s}{n:>16}{d['recovered']:>12.1%}{d['noticed']:>10.1%}"
              f"{d['echoed']:>10.1%}{d['unused']:>11.1%}")
        cfg_csv.append(dict(config=tag, n_corrupt_words=n, n_excluded=excluded,
                            silent_fix_n=c["recovered"], flagged_n=c["noticed"],
                            misread_n=c["echoed"], not_used_n=c["unused"],
                            silent_fix_frac=round(d["recovered"], 4),
                            flagged_frac=round(d["noticed"], 4),
                            misread_frac=round(d["echoed"], 4),
                            not_used_frac=round(d["unused"], 4)))
    write_csv(os.path.join(TABLES, "repair_wordlevel_per_config.csv"), cfg_csv)

    # ---- does misreading predict a wrong answer? -------------------------
    # Per problem: misread rate among its corrupted words, split by final correctness.
    print("\n=== misread rate (used corrupted word) per problem, by final outcome ===")
    print(f"{'config':16s}{'misread%|correct':>18}{'misread%|wrong':>16}{'wrong/correct':>15}")
    oc_csv = []
    for tag in tags:
        def misread_rate(recs):
            e = sum(r["cats"]["echoed"] for r in recs)
            u = sum(r["usable"] for r in recs)
            return e / u if u else 0
        corr = [r for r in DATA[tag] if r["correct"]]
        wrong = [r for r in DATA[tag] if not r["correct"]]
        ec, ew = misread_rate(corr), misread_rate(wrong)
        print(f"{tag:16s}{ec:>18.1%}{ew:>16.1%}{(ew/ec if ec else 0):>15.2f}")
        oc_csv.append(dict(config=tag, misread_correct=round(ec, 4), misread_wrong=round(ew, 4),
                           wrong_over_correct=round(ew/ec if ec else 0, 3),
                           misread_n_correct=sum(r["cats"]["echoed"] for r in corr),
                           words_correct=sum(r["usable"] for r in corr),
                           misread_n_wrong=sum(r["cats"]["echoed"] for r in wrong),
                           words_wrong=sum(r["usable"] for r in wrong)))
    write_csv(os.path.join(TABLES, "repair_wordlevel_by_outcome.csv"), oc_csv)

    print(f"\ntables written to {TABLES}")


if __name__ == "__main__":
    main()
