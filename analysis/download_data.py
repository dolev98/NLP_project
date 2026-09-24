"""Download the paper's raw generations and judge scores from the Hub.

Everything lives in the public dataset repo Dolevabudi/silent-tax-results, laid
out exactly like the local data/ folder:

    raw/<run>/<run>_<config>.jsonl      one model generation per question
    judge/<run>_judge_traces.jsonl      LLM-judge scores per trace

analysis/data_manifest.json pins the repo revision and the sha256 of every file,
so the download is checked against the exact data the tables were built from.

    python analysis/download_data.py --run gsm8k     # one run's generations
    python analysis/download_data.py --all           # every run + judge scores
    python analysis/download_data.py --judge         # judge scores only
"""
import os, json, shutil, hashlib, argparse

from huggingface_hub import hf_hub_download

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_manifest.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(manifest, path):
    dest = os.path.join(REPO_ROOT, "data", path)
    want = manifest["files"][path]["sha256"]
    if os.path.exists(dest) and sha256(dest) == want:
        return "present"
    tmp = hf_hub_download(manifest["repo"], path, repo_type="dataset",
                          revision=manifest["revision"])
    if sha256(tmp) != want:
        raise SystemExit(f"checksum mismatch for {path}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(tmp, dest)
    return "downloaded"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", help="gsm8k | math500 | arc | gsm8k_warn | gsm8k_rewrite | gsm8k_spellcheck")
    g.add_argument("--all", action="store_true", help="every run and the judge scores")
    g.add_argument("--judge", action="store_true", help="the judge scores only")
    args = ap.parse_args()

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    paths = sorted(manifest["files"])
    if args.run:
        paths = [p for p in paths if p.startswith(f"raw/{args.run}/")]
    elif args.judge:
        paths = [p for p in paths if p.startswith("judge/")]
    if not paths:
        raise SystemExit(f"nothing in the manifest for {args.run!r}")
    for p in paths:
        print(f"{fetch(manifest, p):10s} data/{p}", flush=True)
    print(f"{len(paths)} files verified against {os.path.basename(MANIFEST)}")


if __name__ == "__main__":
    main()
