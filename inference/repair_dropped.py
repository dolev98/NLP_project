"""Remove rows whose generation was cut off by the router, so they can be regenerated.

Before the runner rejected dropped streams, the Hugging Face router could close a
stream mid-generation. The stored row then holds a partial generation that is a
transport failure, not model behaviour. Two shapes occur, both far below the
token cap and without a recorded finish_reason:

  empty final   the stream died inside the reasoning: no final-answer section
  cut final     the stream died inside the final answer. The final section has an
                unclosed \\boxed{, or it holds no answer at all (no closed \\boxed{}
                and no "answer" statement) and either stops mid-sentence, belongs
                to a math dataset, or yields no answer for the scorer (a bare
                multiple-choice line such as "D) confident" is complete)

Rows that stop at the token cap are real truncation and are kept.

The removed rows are regenerated with identical prompts by re-running
run_typo_api.py, whose resume mode fills in exactly the questions missing from
each file. rerun_manifest.json lists every row regenerated this way: 57 ARC rows
with an empty final (August 2026) and 50 rows with a cut final (40 GSM8K, 10 ARC;
September 2026).

    python inference/repair_dropped.py --run gsm8k --dry-run    # list, change nothing
    python inference/repair_dropped.py --run gsm8k              # remove (keeps .orig)
    python inference/run_typo_api.py --dataset gsm8k --variant both --limit 500
"""
import os, re, sys, json, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))


def boxes(text):
    """[(content, closed)] for every \\boxed{ in text, balancing nested braces."""
    out = []
    for m in re.finditer(r"\\boxed\{", text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        out.append((text[m.end():i - 1] if depth == 0 else text[m.end():], depth == 0))
    return out


def dropped(row, answered, cap, math=True):
    """'empty' or 'cut' if the row is a cut-off stream, else None.
    math: the dataset asks for a \\boxed{} number or expression (GSM8K, MATH-500)."""
    if row.get("finish_reason") or (row.get("n_gen_tokens") or 0) >= cap:
        return None
    final = (row.get("final_answer_text") or "").strip()
    if not final:
        return None if answered else "empty"
    bx = boxes(final)
    if any(not closed for _, closed in bx):
        return "cut"                                    # stopped inside \\boxed{...
    if any(closed for _, closed in bx) or re.search(r"(?i)\banswer\b", final) \
            or re.match(r"\**\s*[A-D]\)", final):
        return None                                     # an answer is there
    if not re.search(r"[.!?)\]]\**\s*$", final) or math or not answered:
        return "cut"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="e.g. gsm8k or arc")
    ap.add_argument("--dry-run", action="store_true", help="report, change nothing")
    args = ap.parse_args()
    os.environ["NLP_RUN"] = args.run
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "analysis"))
    from common import MAX_NEW_TOKENS, BASE_DATASET, config_files, parse_tag, eval_row

    manifest = {}
    for path in config_files():
        tag = parse_tag(path)["tag"]
        kept, removed = [], {"empty": [], "cut": []}
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            kind = dropped(r, eval_row(r)["answered"], MAX_NEW_TOKENS, BASE_DATASET != "arc")
            if kind:
                removed[kind].append(r["idx"])
            else:
                kept.append(line)
        n = len(removed["empty"]) + len(removed["cut"])
        print(f"{tag:20s} kept {len(kept):4d}  removed {n:3d}  "
              f"(empty final {removed['empty']}, cut final {removed['cut']})")
        if n:
            manifest[tag] = removed
        if n and not args.dry_run:
            orig = path + ".orig"
            if not os.path.exists(orig):
                shutil.copyfile(path, orig)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(kept)

    total = sum(len(v["empty"]) + len(v["cut"]) for v in manifest.values())
    print(f"\n{args.run}: {total} cut-off rows (cap={MAX_NEW_TOKENS})")
    if manifest and not args.dry_run:
        mpath = os.path.join(os.path.dirname(config_files()[0]), "dropped_rows.json")
        json.dump(manifest, open(mpath, "w"), indent=1)
        print(f"list -> {mpath}")


if __name__ == "__main__":
    main()
