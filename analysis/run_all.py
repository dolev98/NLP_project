"""Run every analysis module for one run, or for all runs, and write results/<run>/.

    python analysis/run_all.py --run gsm8k
    python analysis/run_all.py --all

Runs: gsm8k, math500, arc (main grid) and gsm8k_warn, gsm8k_rewrite,
gsm8k_spellcheck (mitigation arms). Raw generations must be in data/raw/<run>/
(python analysis/download_data.py). The LLM judge is a separate step
(analysis/llm_judge.py) because it calls an API.
"""
import os, sys, subprocess, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = ["gsm8k", "math500", "arc", "gsm8k_warn", "gsm8k_rewrite", "gsm8k_spellcheck"]
MODULES = ["accuracy_flips", "reasoning_length", "self_doubt", "repair_wordlevel",
           "real_word_effect", "spellcheck_recovery", "corruption_stats"]


def run(name):
    env = dict(os.environ, NLP_RUN=name, PYTHONIOENCODING="utf-8")
    for m in MODULES:
        print(f"[{name}] {m}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, m + ".py")], env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout[-2000:] + r.stderr[-4000:])
            raise SystemExit(f"[{name}] {m} failed (exit {r.returncode})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", choices=RUNS)
    g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    for name in (RUNS if args.all else [args.run]):
        run(name)
    print("done")


if __name__ == "__main__":
    main()
