"""Answer extraction and correctness, shared by every analysis module.

    extract_pred(text, kind, final_text)  -> predicted answer or None
    is_correct(kind, pred, gold)          -> bool

kind is "gsm8k_num" (numeric), "math" (MATH-500, symbolic equivalence via
math_verify on the last \\boxed{}), or "mc" (ARC letter A-D). The analysis passes
only the final section (after </think>), so nothing from mid-reasoning is used.
"""
import os, re

# math_verify gives proper symbolic equivalence for MATH500 (1/2 == 0.5 == \frac{1}{2}).
try:
    from math_verify import parse as mv_parse, verify as mv_verify
    HAVE_MATH_VERIFY = True
except Exception:
    HAVE_MATH_VERIFY = False

# math_verify enforces its parsing timeout with a worker process, which cannot be
# spawned on Windows here; without this the parse silently returns nothing and
# every MATH500 answer is scored wrong. Disable the timeout on Windows only.
_MV_KWARGS = {"parsing_timeout": None} if os.name == "nt" else {}
_MV_VERIFY_KWARGS = {"timeout_seconds": None} if os.name == "nt" else {}


def last_boxed(text):
    """Return the content of the last \\boxed{...}, handling nested braces."""
    idx = text.rfind("\\boxed")
    if idx < 0:
        return None
    i = text.find("{", idx)
    if i < 0:
        return None
    depth, out = 0, []
    for ch in text[i:]:
        if ch == "{":
            depth += 1
            if depth == 1:
                continue
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
    return "".join(out).strip()


def norm_num(s):
    """Normalize a numeric string for GSM8K comparison."""
    if s is None:
        return None
    s = s.replace(",", "").replace("$", "").replace("%", "").strip()
    m = re.search(r"-?\d+\.?\d*", s)
    if not m:
        return None
    v = m.group(0)
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return None


def gold_gsm8k(g):       # gold field is the full solution ending in "#### N"
    return norm_num(g.split("####")[-1])


def last_number(text):
    """Last standalone number in the text (GSM8K fallback when no \\boxed)."""
    nums = re.findall(r"-?\d[\d,]*\.?\d*", text)
    return nums[-1] if nums else None


# Multiple choice. The option letter must be a capital A-D standing on its own, so
# the article "a" ("the answer is a flood") is never read as option A.
# Tier 1: explicit statements of the chosen answer.
_MC_STATEMENT = re.compile(
    r"(?i:\b(?:final\s+|correct\s+)?answer\b)"                     # "the correct answer is B)"
    r"(?:\s+(?i:is|would\s+be|should\s+be))?\s*[:=]?\s*(?:\*\*)?\s*[(\[]?([ABCD])(?![A-Za-z0-9'])"
    r"|(?i:\bcorrect\s+(?:option|choice)\b)(?:\s+(?i:is))?\s*[:=]?\s*(?:\*\*)?\s*[(\[]?([ABCD])(?![A-Za-z0-9'])"
    r"|\b([ABCD])\)?\s+(?i:is\s+the\s+(?:correct|right|best)\b)"   # "A is the correct answer"
    r"|(?i:\bis)\s*:?\s*(?:\*\*)?\s*([ABCD])\)"                     # "... is: **A) Fish**"
    r"|\A\s*(?:\*\*)?\s*([ABCD])\)")                                # final starts "D) confident"
# Tier 2: a bare "option X" / "choice X", used only when nothing is stated explicitly
# (an explanation that walks through "Option D is incorrect" must not override tier 1).
_MC_OPTION = re.compile(r"(?i:\b(?:option|choice)\b)\s*[:=]?\s*(?:\*\*)?\s*[(\[]?([ABCD])(?![A-Za-z0-9'])")
_MC_KEYWORD = re.compile(r"(?i:answer|option|choice|correct)\D{0,15}\b([ABCD])\b")


def extract_pred(gen, kind, final_text=""):
    b = last_boxed(gen)
    if kind == "mc":
        # A boxed letter, else the last explicit answer statement, else the last bare
        # "option X", else a keyword near the end followed by a capital letter. No
        # stated answer -> None (unanswered), never a guess from the reasoning.
        if b and re.fullmatch(r"\s*[ABCD]\s*", b):
            return b.strip().upper()
        text = final_text or gen
        for rx in (_MC_STATEMENT, _MC_OPTION):
            hits = [next(g for g in m.groups() if g) for m in rx.finditer(text)]
            if hits:
                return hits[-1]
        m = _MC_KEYWORD.findall(text[-400:])
        return m[-1] if m else None
    if kind == "gsm8k_num":
        # prefer boxed, else the last number in the answer section (then whole gen)
        if b is not None:
            return b
        return last_number(final_text) or last_number(gen)
    return b  # generic math (MATH500): rely on boxed


def is_correct(kind, pred, gold):
    if pred is None:
        return False
    if kind == "mc":
        return pred.strip().upper() == str(gold).strip().upper()
    if kind == "gsm8k_num":
        return norm_num(pred) is not None and norm_num(pred) == gold
    # generic math (MATH500) - math_verify needs the LaTeX wrapped in $...$ to parse
    if HAVE_MATH_VERIFY:
        try:
            return bool(mv_verify(mv_parse(f"${gold}$", **_MV_KWARGS),
                                  mv_parse(f"${pred}$", **_MV_KWARGS),
                                  **_MV_VERIFY_KWARGS))
        except Exception:
            pass
    return norm_num(pred) is not None and norm_num(pred) == norm_num(gold)
