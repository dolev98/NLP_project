"""LLM-as-judge scores for self-doubt and repair, on every answered trace.

One call per trace returns two integer scores from a fixed rubric:
  self_doubt_score            0 (straight-line solution) .. 10 (pervasive doubt, looping)
  repair_understanding_score  0 (intended meaning fully understood) .. 5 (lost / wrong meaning)
plus verbatim evidence quotes and a one-line summary. The judge sees the list of
corrupted words (original -> as shown), the question as shown to the model, and
the reasoning trace (first and last 2,000 characters). Temperature 0.

Judged rows are appended to a JSONL cache (default data/judge/<run>_judge_traces.jsonl);
rows already there with valid scores are not sent again, rows that failed are
retried. A stored score is used only for the trace it judged: new rows carry a
hash of the trace, and older rows without one are dropped for the questions that
were regenerated afterwards (inference/rerun_manifest.json). Tables are then built
from the cache over every answered trace:
  results/<run>/judge_scalar_per_config.csv   means per config
  results/<run>/judge_scalar_by_real.csv      means per real-word ratio (typo configs)
  results/<run>/judge_scalar_by_outcome.csv   correct vs wrong, per config, over all
                                              configs (__all__) and over typo configs (__typo__)

    NLP_RUN=gsm8k python analysis/llm_judge.py --all --dry-run     # price the job
    NLP_RUN=gsm8k python analysis/llm_judge.py --all               # judge (needs HF_TOKEN)
    NLP_RUN=gsm8k python analysis/llm_judge.py --all --report-only # tables from the cache
"""
import os, sys, re, csv, json, random, argparse, threading, hashlib, difflib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from common import config_files, parse_tag, load_evals, write_csv, TABLES, RUN, REPO  # noqa: E402

API_BASE = os.environ.get("API_BASE", "https://router.huggingface.co/v1")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
# USD per 1M tokens, only for the printed estimate; check your provider's price.
PRICE_IN = float(os.environ.get("JUDGE_PRICE_IN", 0.6))
PRICE_OUT = float(os.environ.get("JUDGE_PRICE_OUT", 0.6))

PROMPT_VERSION = "v1"          # the rubric below; stored with every new judged row
TEMPERATURE = 0.0
HEAD_CHARS, TAIL_CHARS = 2000, 2000
MAX_PAIRS = 25                 # corrupted words listed in the prompt

JUDGE_PROMPT = """You are a strict annotator. Do NOT solve the problem and do NOT judge whether the
final answer is right. Judge ONLY how the reasoning trace behaved.

CORRUPTED WORDS (original -> as shown to the model):
{pairs}

QUESTION SHOWN TO THE MODEL:
{question}

REASONING TRACE:
{reasoning}

Task 1 - self_doubt_score. Give a single integer from 0 to 10.
Interpretation:
0 = no doubt at all; straight-line solution; no second-guessing.
1 = tiny hedge or mild uncertainty, still clear.
2 = one brief hesitation or check.
3 = some re-checking but still mostly stable.
4 = noticeable self-doubt, repeated minor checks.
5 = clear hesitation and multiple second-guessing moments.
6 = repeated reconsideration, several reversals or checks.
7 = strong uncertainty, multiple pauses and reversals.
8 = heavy self-doubt, frequent re-reads and re-evaluations.
9 = pervasive doubt, many reversals and almost no stable plan.
10 = extreme uncertainty and looping / unable to settle.
The score should reflect the model's own second-guessing and uncertainty, independent of whether
the typo was bad or not.

Task 2 - repair_understanding_score. Give a single integer from 0 to 5.
Interpretation:
0 = fully understands the meaning of the question and the corrupted word(s); no confusion.
1 = almost fully understands the meaning; only slight confusion.
2 = some confusion but still largely understands the problem.
3 = noticeable misunderstanding or misreading of the question/word; partial loss of meaning.
4 = major misunderstanding; the model is clearly confused by the wording or corrupted word.
5 = does not understand the meaning of the question at all; it is fundamentally lost or reasoning from the wrong meaning.
This score should capture how much the trace loses the intended meaning because of the typo.

Task 3 - one_line_summary: Write a single sentence explaining what in the trace led to your
scores, using the most important concrete cue from the trace (for example: a typo notice,
hedging, a different real-word interpretation, or a clean straight-line solution). Keep it to one
line and do not explain your scores numerically.

Both evidence fields must be a VERBATIM substring copied from the reasoning trace
(use "" if there is genuinely none).

Output JSON only, no prose, no code fences:
{{"self_doubt_score": 0, "repair_understanding_score": 0, "self_doubt_evidence": "...", "repair_understanding_evidence": "...", "one_line_summary": "..."}}"""


# ---------------------------------------------------------------------------
# trace loading + prompt building
# ---------------------------------------------------------------------------
def shown_question(r):
    """The question text the model actually saw (spell-checked variant if a fix ran)."""
    return r.get("spellchecked_question") or r.get("typo_question") or r.get("clean_question", "")


WORD = re.compile(r"[A-Za-z']+")


def corrupted_pairs(clean, typo):
    """Word-align clean vs typo with difflib; return [(original, corrupted), ...].
    This is the alignment the stored scores were made with, kept so that re-judging
    builds the same prompts (repair_wordlevel.py aligns by position instead)."""
    cw, tw = WORD.findall(clean), WORD.findall(typo)
    sm = difflib.SequenceMatcher(a=[w.lower() for w in cw], b=[w.lower() for w in tw])
    pairs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            a, b = cw[i1:i2], tw[j1:j2]
            for k in range(min(len(a), len(b))):   # position-align within the block
                if a[k].lower() != b[k].lower():
                    pairs.append((a[k], b[k]))
    return pairs


def pairs_for(r):
    """(original, corrupted) pairs: from the stored typo lists when present, else
    recovered by diffing clean vs typo (older result files)."""
    orig, repl = r.get("typo_originals"), r.get("typo_replacements")
    if isinstance(orig, list) and isinstance(repl, list) and orig:
        return [(o, c) for o, c in zip(orig, repl) if str(o).lower() != str(c).lower()]
    if r.get("typo_question"):
        return corrupted_pairs(r.get("clean_question", ""), r["typo_question"])
    return []


def truncate(text):
    """Head+tail window: repair language clusters at the first read AND at the
    late 'wait, that was a typo' reversal, so a head-only cut loses half of it."""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return text[:HEAD_CHARS] + "\n[... trace truncated ...]\n" + text[-TAIL_CHARS:]


def build_prompt(rec):
    pairs = rec["pairs"][:MAX_PAIRS]
    pair_str = ", ".join(f"{o} -> {c}" for o, c in pairs) or "(none - this is a clean question)"
    return JUDGE_PROMPT.format(pairs=pair_str, question=rec["question"][:2000],
                               reasoning=truncate(rec["reasoning"]))


def load_traces(path, meta, limit, seed):
    """Answered traces of one config, optionally a seeded random sample of them."""
    ev = load_evals(path)
    rows = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        e = ev[r["idx"]]
        if not e["answered"]:
            continue
        reasoning = r.get("reasoning") or r.get("generation", "") or ""
        if not reasoning.strip():
            continue
        rows.append(dict(
            config=meta["tag"], idx=r["idx"], reasoning=reasoning,
            question=shown_question(r), pairs=[] if meta["is_clean"] else pairs_for(r),
            correct=e["correct"], real=meta["real"], rate=meta["rate"],
        ))
    if limit and limit < len(rows):
        rows = random.Random(seed).sample(rows, limit)
    return rows


# ---------------------------------------------------------------------------
# the judge call
# ---------------------------------------------------------------------------
def extract_json(text):
    """First {...} block, tolerating code fences and trailing prose."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except json.JSONDecodeError:
        return None


_BAD_ESCAPE = re.compile(r'(?<!\\)\\(?![\\"])')
_SCORE = {k: re.compile(r'"%s"\s*:\s*(-?\d+(?:\.\d+)?)' % k)
          for k in ("self_doubt_score", "repair_understanding_score")}


def parse_reply(raw):
    """(obj, how) from the judge's reply. Tries strict JSON, then JSON with every
    lone backslash escaped (LaTeX such as \\sqrt or \\frac quoted from a trace),
    then the two integer scores alone. (None, None) if the scores cannot be read."""
    obj = extract_json(raw)
    if obj is not None:
        return obj, "json"
    i, j = raw.find("{"), raw.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(_BAD_ESCAPE.sub(r"\\\\", raw[i:j + 1])), "json-escaped"
        except json.JSONDecodeError:
            pass
    found = {k: rx.search(raw) for k, rx in _SCORE.items()}
    if all(found.values()):
        return {k: m.group(1) for k, m in found.items()}, "scores-only"
    return None, None


def norm_quote(s):
    return " ".join(str(s or "").lower().split())


def evidence_ok(quote, reasoning_low):
    """A quote counts as verified only if it is non-empty and occurs in the trace."""
    q = norm_quote(quote)
    return bool(q) and q in norm_quote(reasoning_low)


def trace_hash(reasoning):
    return hashlib.sha1(reasoning.encode("utf-8")).hexdigest()


def score(obj, key, hi):
    try:
        v = int(round(float(obj.get(key, -1))))
    except (TypeError, ValueError):
        return -1
    return v if 0 <= v <= hi else -1


def judge_one(client, model, rec, retries=3):
    """Return a cache row for one trace. Never raises."""
    prompt = build_prompt(rec)
    last_err = ""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}],
                temperature=TEMPERATURE, max_tokens=600)
            raw = (resp.choices[0].message.content or "").strip()
            u = getattr(resp, "usage", None)
            obj, how = parse_reply(raw)
            sd, ru = (score(obj, "self_doubt_score", 10),
                      score(obj, "repair_understanding_score", 5)) if obj else (-1, -1)
            if sd < 0 or ru < 0:
                last_err = f"unparseable: {raw[:300]}"
                continue
            low = rec["reasoning"].lower()
            return dict(
                config=rec["config"], idx=rec["idx"],
                self_doubt_score=sd, repair_understanding_score=ru,
                self_doubt_evidence_ok=evidence_ok(obj.get("self_doubt_evidence"), low),
                repair_understanding_evidence_ok=evidence_ok(
                    obj.get("repair_understanding_evidence"), low),
                self_doubt_evidence=str(obj.get("self_doubt_evidence", "")),
                repair_understanding_evidence=str(obj.get("repair_understanding_evidence", "")),
                one_line_summary=str(obj.get("one_line_summary", "")),
                parse=how, judge_model=model, prompt_version=PROMPT_VERSION,
                temperature=TEMPERATURE, trace_sha1=trace_hash(rec["reasoning"]),
                n_in=getattr(u, "prompt_tokens", 0) or 0,
                n_out=getattr(u, "completion_tokens", 0) or 0,
                error="",
            )
        except Exception as e:                      # network / provider errors
            last_err = str(e)[:300]
    return dict(config=rec["config"], idx=rec["idx"],
                self_doubt_score=-1, repair_understanding_score=-1,
                self_doubt_evidence_ok=False, repair_understanding_evidence_ok=False,
                judge_model=model, prompt_version=PROMPT_VERSION, temperature=TEMPERATURE,
                n_in=0, n_out=0, error=last_err)


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------
def default_cache():
    return os.path.join(REPO, "data", "judge", f"{RUN}_judge_traces.jsonl")


def valid(row):
    return (not row.get("error") and row.get("self_doubt_score", -1) >= 0
            and row.get("repair_understanding_score", -1) >= 0)


def regenerated():
    """{(config, idx)} of this run's rows regenerated after the August judge run."""
    path = os.path.join(REPO, "inference", "rerun_manifest.json")
    out = set()
    if os.path.exists(path):
        for key, runs in json.load(open(path, encoding="utf-8")).items():
            if not key.startswith("_"):
                for cfg, ids in runs.get(RUN, {}).items():
                    out.update((cfg, i) for i in ids)
    return out


def load_cache(path):
    """{(config, idx): row} for rows with valid scores; later rows win. Failed
    rows are left out so the next run retries them, and so are rows without a
    trace hash whose question was regenerated after they were judged."""
    done, stale = {}, regenerated()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (r["config"], r["idx"])
            if valid(r) and not ("trace_sha1" not in r and key in stale):
                done[key] = r
    return done


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------
def report(recs, results):
    """recs = selected traces, results = {(config, idx): judged row}."""
    def same_trace(r, j):
        return "trace_sha1" not in j or j["trace_sha1"] == trace_hash(r["reasoning"])
    joined = [{**r, **results[(r["config"], r["idx"])]} for r in recs
              if (r["config"], r["idx"]) in results
              and same_trace(r, results[(r["config"], r["idx"])])]
    if not joined:
        print("no judged traces to report")
        return
    for r in joined:              # re-check the stored quotes against the trace
        low = r["reasoning"].lower()
        for k in ("self_doubt", "repair_understanding"):
            if f"{k}_evidence" in r:
                r[f"{k}_evidence_ok"] = evidence_ok(r[f"{k}_evidence"], low)
    tags = list(dict.fromkeys(r["config"] for r in joined))

    def mean(rows, key):
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    def share(rows, key, threshold):
        return sum(r[key] >= threshold for r in rows) / len(rows) if rows else 0.0

    rows = []
    print(f"\n=== {RUN}: LLM-judge scores per config ===")
    print(f"{'config':16s}{'n':>6}{'doubt 0-10':>12}{'repair 0-5':>12}")
    for tag in tags:
        group = [r for r in joined if r["config"] == tag]
        rows.append(dict(
            config=tag, n=len(group),
            mean_self_doubt=round(mean(group, "self_doubt_score"), 3),
            median_self_doubt=sorted(r["self_doubt_score"] for r in group)[len(group) // 2],
            frac_self_doubt_ge5=round(share(group, "self_doubt_score", 5), 4),
            mean_repair_understanding=round(mean(group, "repair_understanding_score"), 3),
            median_repair_understanding=sorted(r["repair_understanding_score"] for r in group)[len(group) // 2],
            frac_repair_understanding_ge3=round(share(group, "repair_understanding_score", 3), 4),
            evidence_self_doubt_frac=round(sum(bool(r.get("self_doubt_evidence_ok")) for r in group) / len(group), 4),
            evidence_repair_frac=round(sum(bool(r.get("repair_understanding_evidence_ok")) for r in group) / len(group), 4),
            sum_self_doubt=sum(r["self_doubt_score"] for r in group),
            sum_repair_understanding=sum(r["repair_understanding_score"] for r in group),
        ))
        print(f"{tag:16s}{len(group):>6}{rows[-1]['mean_self_doubt']:>12.2f}"
              f"{rows[-1]['mean_repair_understanding']:>12.2f}")
    write_csv(os.path.join(TABLES, "judge_scalar_per_config.csv"), rows)

    rows = []
    groups = [(t, [r for r in joined if r["config"] == t]) for t in tags]
    groups += [("__all__", joined), ("__typo__", [r for r in joined if r["config"] != "clean"])]
    for tag, group in groups:
        correct = [r for r in group if r["correct"]]
        wrong = [r for r in group if not r["correct"]]
        rows.append(dict(
            config=tag, n=len(group), n_correct=len(correct), n_wrong=len(wrong),
            mean_doubt_correct=round(mean(correct, "self_doubt_score"), 3),
            mean_doubt_wrong=round(mean(wrong, "self_doubt_score"), 3),
            mean_repair_correct=round(mean(correct, "repair_understanding_score"), 3),
            mean_repair_wrong=round(mean(wrong, "repair_understanding_score"), 3),
            sum_doubt_correct=sum(r["self_doubt_score"] for r in correct),
            sum_doubt_wrong=sum(r["self_doubt_score"] for r in wrong),
            sum_repair_correct=sum(r["repair_understanding_score"] for r in correct),
            sum_repair_wrong=sum(r["repair_understanding_score"] for r in wrong),
        ))
    write_csv(os.path.join(TABLES, "judge_scalar_by_outcome.csv"), rows)

    rows = []
    by_real = defaultdict(list)
    for r in joined:
        if r["real"] is not None:
            by_real[r["real"]].append(r)
    for real in sorted(by_real):
        group = by_real[real]
        rows.append(dict(
            real_ratio=real, n=len(group),
            mean_self_doubt=round(mean(group, "self_doubt_score"), 3),
            mean_repair_understanding=round(mean(group, "repair_understanding_score"), 3),
            frac_self_doubt_ge5=round(share(group, "self_doubt_score", 5), 4),
            frac_repair_understanding_ge3=round(share(group, "repair_understanding_score", 3), 4),
            sum_self_doubt=sum(r["self_doubt_score"] for r in group),
            sum_repair_understanding=sum(r["repair_understanding_score"] for r in group),
        ))
    write_csv(os.path.join(TABLES, "judge_scalar_by_real.csv"), rows)
    print(f"judged traces used: {len(joined)} of {len(recs)} answered")
    print(f"tables written to {TABLES}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=150, help="traces judged per config")
    ap.add_argument("--all", action="store_true", help="judge every answered trace")
    ap.add_argument("--configs", default="", help="comma-separated subset, e.g. clean,typo75_real70")
    ap.add_argument("--model", default=JUDGE_MODEL, help="judge model at the router")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cache", default=None, help=f"judged-rows JSONL (default: {default_cache()})")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the token/cost estimate and exit without calling the API")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild the tables from the cache, no API calls")
    args = ap.parse_args()

    limit = 0 if (args.all or args.report_only) else args.limit
    wanted = {c.strip() for c in args.configs.split(",") if c.strip()}
    recs = []
    for f in config_files():
        meta = parse_tag(f)
        if wanted and meta["tag"] not in wanted:
            continue
        recs.extend(load_traces(f, meta, limit, args.seed))
    if not recs:
        raise SystemExit("no traces selected")

    cpath = args.cache or default_cache()
    os.makedirs(os.path.dirname(cpath), exist_ok=True)
    cached = load_cache(cpath)
    todo = [r for r in recs if (r["config"], r["idx"]) not in cached
            or cached[(r["config"], r["idx"])].get("trace_sha1", trace_hash(r["reasoning"]))
            != trace_hash(r["reasoning"])]
    est_in = sum(len(build_prompt(r)) for r in todo) / 4      # ~4 chars per token
    est_out = 150 * len(todo)
    print(f"run={RUN}  judge={args.model}  prompt={PROMPT_VERSION}")
    print(f"selected {len(recs)} traces ({len(recs) - len(todo)} judged, {len(todo)} to call)")
    print(f"estimate: ~{est_in:,.0f} in + ~{est_out:,.0f} out tokens  "
          f"~${est_in / 1e6 * PRICE_IN + est_out / 1e6 * PRICE_OUT:.3f}")
    if args.dry_run:
        print("\n--- example prompt ---\n" + build_prompt(recs[0])[:1500] + "\n[dry-run] nothing sent.")
        return

    if todo and not args.report_only:
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise SystemExit("export HF_TOKEN=hf_... first")
        from openai import OpenAI
        client = OpenAI(api_key=token, base_url=API_BASE)
        lock = threading.Lock()
        done = spent_in = spent_out = failed = 0
        with open(cpath, "a", encoding="utf-8") as cf, \
                ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(judge_one, client, args.model, r) for r in todo]
            for fut in as_completed(futs):
                row = fut.result()
                with lock:
                    cf.write(json.dumps(row, ensure_ascii=False) + "\n"); cf.flush()
                    if valid(row):
                        cached[(row["config"], row["idx"])] = row
                    else:
                        failed += 1
                    done += 1
                    spent_in += row["n_in"]; spent_out += row["n_out"]
                    if done % 25 == 0 or done == len(todo):
                        print(f"  judged {done}/{len(todo)}  tokens {spent_in:,}+{spent_out:,}"
                              f"  failed {failed}", flush=True)
        print(f"done. tokens {spent_in:,} in + {spent_out:,} out  "
              f"~${spent_in / 1e6 * PRICE_IN + spent_out / 1e6 * PRICE_OUT:.4f}  failed={failed}")

    report(recs, cached)


if __name__ == "__main__":
    main()
