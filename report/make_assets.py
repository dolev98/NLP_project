"""Build every figure, generated table and quoted number of the report.

Reads the analysis tables in results/<run>/ and writes
  report/figures/*.pdf      figures included by report.tex
  report/tables/*.tex       tables and the Figure 1 box included by report.tex
  report/numbers.txt        every number the prose quotes, with its source

Runs: gsm8k, math500, arc (main grid; 20,000-token cap for GSM8K, 17,000 for the
others) and gsm8k_warn, gsm8k_rewrite, gsm8k_spellcheck (mitigation arms).
Displayed values are computed from counts in the tables and rounded half up once.

    python report/make_assets.py
"""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

HERE = Path(__file__).resolve().parent
RESULTS = Path(os.environ.get("NLP_RESULTS", HERE.parent / "results"))
FIGDIR = HERE / "figures"
TABDIR = HERE / "tables"
FIGDIR.mkdir(exist_ok=True)
TABDIR.mkdir(exist_ok=True)

# --- palette -------------------------------------------------------------
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d8d7d2"

DATASETS = [("gsm8k", "GSM8K", BLUE),
            ("math500", "MATH-500", ORANGE),
            ("arc", "ARC-Challenge", AQUA)]
ARMS = [("warn", "gsm8k_warn"), ("rewrite", "gsm8k_rewrite"), ("spell", "gsm8k_spellcheck")]
RATES, RHOS = [25, 50, 75], [10, 40, 70]
TYPO = [f"typo{r}_real{p}" for r in RATES for p in RHOS]
ORDER = ["clean"] + TYPO

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "legend.fontsize": 7.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.6,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
})


# --- loading and exact formatting ---------------------------------------
def load(run, name):
    return pd.read_csv(RESULTS / run / f"{name}.csv")


def dec(x):
    """Exact decimal of a float's shortest repr (numpy scalars included)."""
    return Decimal(repr(float(x)))


def frac(num, den):
    return Decimal(int(num)) / Decimal(int(den))


def rnd(x, nd=1):
    """Round a Decimal (or exact int ratio) half up to nd decimals, as a string."""
    q = Decimal(1).scaleb(-nd) if nd else Decimal(1)
    return str(Decimal(x).quantize(q, ROUND_HALF_UP))


def pct(num, den, nd=1):
    return rnd(frac(num, den) * 100, nd)


def signed(x, nd=1):
    s = rnd(x, nd)
    return s if s.startswith("-") else "+" + s


def ratio(n1, d1, n2, d2, nd=2):
    """(n1/d1) / (n2/d2), exact."""
    return rnd(frac(n1, d1) / frac(n2, d2), nd)


def pfmt(p):
    if p < 1e-6:
        return r"$<$1e-6"
    return f"{p:.1e}" if p < 0.001 else f"{p:.3f}"


def acc_counts(run):
    a = load(run, "accuracy_per_config").set_index("config")
    return {c: (int(a.loc[c, "n_correct"]), int(a.loc[c, "n_answered"])) for c in a.index}


def style(ax, ygrid=True):
    """Recessive axes: no top/right spine, faint horizontal grid only."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if ygrid:
        ax.set_axisbelow(True)
        ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.tick_params(length=2.5, width=0.6)


def w(name, body):
    (TABDIR / name).write_text(body + "\n", encoding="utf-8")


# =====================================================================
# Figures
# =====================================================================
def fig_accuracy():
    """Accuracy and reasoning length against the typo rate (Section 5.1)."""
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 1.82))
    a, b, c = axes
    for ds, label, color in DATASETS:
        acc = acc_counts(ds)
        tok = load(ds, "reasoning_length_absolute").set_index("config")
        clean = acc["clean"][0] / acc["clean"][1] * 100
        per_rate = {r: [acc[f"typo{r}_real{p}"][0] / acc[f"typo{r}_real{p}"][1] * 100
                        for p in RHOS] for r in RATES}
        xs = [0] + RATES
        ys = [clean] + [sum(per_rate[r]) / 3 for r in RATES]
        a.plot(xs, ys, color=color, marker="o", markersize=4, label=label,
               markeredgecolor="white", markeredgewidth=0.7)
        a.fill_between(xs, [clean] + [min(per_rate[r]) for r in RATES],
                       [clean] + [max(per_rate[r]) for r in RATES],
                       color=color, alpha=0.13, linewidth=0)
        b.plot(xs, [y - clean for y in ys], color=color, marker="o", markersize=4,
               label=label, markeredgecolor="white", markeredgewidth=0.7)
        mean_tok = lambda cfg: tok.loc[cfg, "sum_tok"] / tok.loc[cfg, "n_answered"]
        c.plot(xs, [1.0] + [sum(mean_tok(f"typo{r}_real{p}") for p in RHOS) / 3 / mean_tok("clean")
                            for r in RATES],
               color=color, marker="o", markersize=4, label=label,
               markeredgecolor="white", markeredgewidth=0.7)
    a.set_ylabel("accuracy, answered-only (%)")
    a.set_title("(a) accuracy", loc="left", color=INK2)
    b.axhline(0, color=GRID, linewidth=0.8)
    b.set_ylabel("change vs. clean (pp)")
    b.set_title("(b) accuracy tax", loc="left", color=INK2)
    c.axhline(1.0, color=GRID, linewidth=0.8)
    c.set_ylabel("generated tokens / clean")
    c.set_title("(c) reasoning length", loc="left", color=INK2)
    for ax in axes:
        ax.set_xlabel("corrupted words (%)")
        ax.set_xticks([0] + RATES)
        style(ax)
    a.legend(frameon=False, loc="lower left", handlelength=1.4)
    fig.tight_layout(w_pad=1.4)
    fig.savefig(FIGDIR / "fig_accuracy.pdf", metadata={"CreationDate": None})
    plt.close(fig)


def fig_realword():
    """Per-typo damage and the controlled paired contrast (Section 5.2)."""
    fig, (a, b) = plt.subplots(2, 1, figsize=(3.30, 3.75))
    short = {"GSM8K": "GSM8K", "MATH-500": "MATH-500", "ARC-Challenge": "ARC"}
    xs = range(len(DATASETS))
    real, nonword = [], []
    for ds, _, _ in DATASETS:
        lg = load(ds, "realword_pertypo_logit").iloc[0]
        real.append((1 - math.exp(lg.coef_num_real)) * 100)
        nonword.append((1 - math.exp(lg.coef_num_nonword)) * 100)
    wd = 0.34
    a.bar([x - wd / 2 - 0.01 for x in xs], real, wd, color=BLUE, label="real-word")
    a.bar([x + wd / 2 + 0.01 for x in xs], nonword, wd, color=ORANGE, label="non-word")
    for x, (rv, nv) in enumerate(zip(real, nonword)):
        a.text(x - wd / 2 - 0.01, rv + 0.15, rnd(dec((rv))), ha="center",
               fontsize=6.5, color=INK2)
        a.text(x + wd / 2 + 0.01, nv + 0.15, rnd(dec((nv))), ha="center",
               fontsize=6.5, color=INK2)
    a.set_xticks(list(xs))
    a.set_xticklabels([short[d[1]] for d in DATASETS])
    a.set_ylabel("odds lost per typo (%)", fontsize=7.5)
    a.set_title("(a) per-typo damage (logistic fit)", loc="left", color=INK2, fontsize=7.5)
    a.legend(frameon=False, handlelength=1.1, fontsize=6.8, ncol=2,
             loc="upper center", bbox_to_anchor=(0.5, 1.02))
    a.set_ylim(top=max(real + nonword) * 1.32)
    style(a)

    w2 = 0.26
    for i, (ds, label, color) in enumerate(DATASETS):
        rp = load(ds, "realword_paired")
        rp = rp[rp["compare"] == "real10_to_real70"].set_index("rate")
        vals = [(rp.loc[r, "w2r"] - rp.loc[r, "r2w"]) / rp.loc[r, "n_both"] * 100 for r in RATES]
        ps = [rp.loc[r, "mcnemar_p"] for r in RATES]
        pos = [j + (i - 1) * (w2 + 0.02) for j in range(len(RATES))]
        b.bar(pos, vals, w2, color=color, label=short[label])
        for x, v, p in zip(pos, vals, ps):
            if p < 0.05:
                b.text(x, v - 0.9, "*", ha="center", fontsize=8, color=INK)
    b.axhline(0, color=GRID, linewidth=0.8)
    b.set_xticks(range(len(RATES)))
    b.set_xticklabels([f"{r}%" for r in RATES])
    b.set_xlabel("corrupted words", fontsize=7.5)
    b.set_ylabel(r"$\Delta$ accuracy (pp)", fontsize=7.5)
    b.set_title(r"(b) same words, $\rho$: 10% $\to$ 70%", loc="left", color=INK2, fontsize=7.5)
    b.legend(frameon=False, handlelength=1.1, fontsize=6.8, ncol=3,
             loc="lower center", bbox_to_anchor=(0.5, -0.02))
    lo = min(b.get_ylim()[0], -17)
    b.set_ylim(bottom=lo)
    style(b)
    for ax in (a, b):
        ax.tick_params(labelsize=7)
    fig.tight_layout(h_pad=1.1)
    fig.savefig(FIGDIR / "fig_realword.pdf", metadata={"CreationDate": None})
    plt.close(fig)


REPAIR_CATS = [("silent_fix_n", "silent fix", BLUE), ("flagged_n", "flagged", ORANGE),
               ("misread_n", "misread", AQUA), ("not_used_n", "not used", YELLOW)]


def repair_shares(per, configs):
    """Shares (%) of the four categories, pooled over the word counts of configs."""
    sub = per.loc[configs]
    total = sub["n_corrupt_words"].sum()
    return [sub[col].sum() / total * 100 for col, _, _ in REPAIR_CATS]


def fig_repair():
    """How every corrupted word is handled, against the typo rate and the
    real-word ratio (Section 5.3). Pooled from word counts."""
    fig, axes = plt.subplots(2, 3, figsize=(7.1, 2.92), sharey=True)
    for col_i, (ds, label, _) in enumerate(DATASETS):
        per = load(ds, "repair_wordlevel_per_config").set_index("config")
        groups = [("typo rate", [f"{r}%" for r in RATES],
                   [[f"typo{r}_real{p}" for p in RHOS] for r in RATES]),
                  ("real-word typos", [f"{p}%" for p in RHOS],
                   [[f"typo{r}_real{p}" for r in RATES] for p in RHOS])]
        for row_i, (xlabel, ticks, grouping) in enumerate(groups):
            ax = axes[row_i][col_i]
            vals = [repair_shares(per, g) for g in grouping]
            bottom = [0.0] * len(grouping)
            for k, (_, name, color) in enumerate(REPAIR_CATS):
                heights = [v[k] for v in vals]
                ax.bar(range(len(grouping)), heights, 0.6, bottom=bottom, color=color,
                       label=name, edgecolor="white", linewidth=1.0)
                bottom = [bb + h for bb, h in zip(bottom, heights)]
            ax.set_xticks(range(len(grouping)))
            ax.set_xticklabels(ticks)
            ax.set_xlabel(xlabel)
            ax.set_ylim(0, 100)
            ax.yaxis.set_major_locator(MultipleLocator(25))
            style(ax, ygrid=False)
            if row_i == 0:
                ax.set_title(label, loc="center", color=INK2, pad=4)
    for row_i, tag in enumerate(("(a) by typo rate", "(b) by real-word ratio")):
        axes[row_i][0].set_ylabel("share of words (%)", fontsize=7.5)
        axes[row_i][0].set_title(tag, loc="left", fontsize=7.5, color=INK2, pad=4)
    handles, lbls = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, lbls, frameon=False, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 1.055), handlelength=1.1, columnspacing=1.6)
    fig.tight_layout(w_pad=1.0, h_pad=0.9, rect=(0, 0, 1, 0.955))
    fig.savefig(FIGDIR / "fig_repair.pdf", metadata={"CreationDate": None})
    plt.close(fig)


def fig_doubt():
    """Marker density across the grid (Section 5.4)."""
    fig, a = plt.subplots(1, 1, figsize=(7.1, 2.05))
    labels = ["clean"] + [f"{r}/{p}" for r in RATES for p in RHOS]
    for ds, label, color in DATASETS:
        sd = load(ds, "self_doubt_per_config").set_index("config")
        dens = lambda cfg, cat: sd.loc[cfg, f"{cat}_n"] / sd.loc[cfg, "words"] * 1000
        a.plot(range(len(ORDER)), [dens(c, "uncertainty") for c in ORDER], color=color,
               marker="o", markersize=3.2, label=label, markeredgecolor="white",
               markeredgewidth=0.6)
        a.plot(range(len(ORDER)), [dens(c, "second_guess") for c in ORDER], color=color,
               linestyle=(0, (3, 2)), linewidth=1.2, alpha=0.85)
    a.set_ylabel("markers per 1k reasoning words")
    a.set_title("uncertainty (solid) vs. second-guessing (dashed)", loc="left", color=INK2)
    a.set_xticks(range(len(ORDER)))
    a.set_xticklabels(labels, rotation=45, ha="right")
    a.set_xlabel(r"configuration ($r$/$\rho$)")
    style(a)
    handles, lbls = a.get_legend_handles_labels()
    fig.legend(handles, lbls, frameon=False, ncol=3, loc="upper center",
               bbox_to_anchor=(0.5, 1.045), fontsize=6.8, handlelength=1.3, columnspacing=1.6)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    fig.savefig(FIGDIR / "fig_doubt.pdf", metadata={"CreationDate": None})
    plt.close(fig)


# =====================================================================
# Tables
# =====================================================================
def tab_datastats():
    """Dataset and corruption statistics (Table 1)."""
    cs = {ds: load(ds, "corruption_stats").set_index("config") for ds, _, _ in DATASETS}

    def row(label, fn):
        return label + " & " + " & ".join(fn(cs[ds]) for ds, _, _ in DATASETS) + r" \\"

    def typos(d, r):
        return sum(int(d.loc[f"typo{r}_real{p}", "typos_total"]) for p in RHOS)

    def real_ratio(d, p):
        cfgs = [f"typo{r}_real{p}" for r in RATES]
        return rnd(frac(sum(int(d.loc[c, "real_typos_total"]) for c in cfgs),
                        sum(int(d.loc[c, "typos_total"]) for c in cfgs)), 3)

    n = lambda d: int(d.loc["clean", "n_questions"])
    rows = [row("questions", lambda d: f"{n(d)}"),
            row("mean words per question", lambda d: rnd(frac(d.loc["clean", "words_total"], n(d)))),
            row("median words per question", lambda d: rnd(dec((float(d.loc["clean", "words_median"]))), 0)),
            row("eligible words per question", lambda d: rnd(frac(d.loc["clean", "eligible_total"], n(d)))),
            r"\midrule"]
    rows += [row(f"typos per question, $r{{=}}{r}\\%$",
                 lambda d, r=r: rnd(frac(typos(d, r), 3 * n(d)))) for r in RATES]
    rows += [r"\midrule"]
    rows += [row(f"achieved real-word ratio, $\\rho{{=}}{p}\\%$",
                 lambda d, p=p: real_ratio(d, p)) for p in RHOS]
    rows += [r"\midrule",
             row("total corrupted words",
                 lambda d: f"{sum(typos(d, r) for r in RATES):,}".replace(",", "{,}"))]
    w("tab_datastats.tex", "\n".join([
        r"\begin{tabular}{lrrr}", r"\toprule",
        r" & GSM8K & MATH-500 & ARC-C \\", r"\midrule", *rows,
        r"\bottomrule", r"\end{tabular}"]))


def fig_example():
    """The worked example of Figure 1, from results/gsm8k/figure1_example.json."""
    ex = json.load(open(RESULTS / "gsm8k" / "figure1_example.json", encoding="utf-8"))

    def tex(s):
        return (s.replace("\\", r"\textbackslash{}").replace("$", r"\$").replace("%", r"\%")
                 .replace("&", r"\&").replace("#", r"\#").replace("_", r"\_").replace("’", "'"))

    # Bold the words that differ from the clean question, aligned by position.
    import difflib
    cw, tw = ex["clean_question"].split(), ex["typo_question"].split()
    changed = set()
    for op, _, _, j1, j2 in difflib.SequenceMatcher(a=cw, b=tw).get_opcodes():
        if op != "equal":
            changed.update(range(j1, j2))
    shown = " ".join(r"\textbf{" + tex(t) + "}" if j in changed else tex(t)
                     for j, t in enumerate(tw))
    real = [t for t in ex["typos"] if t["real_word"]]
    rate, rho = ex["config"].replace("typo", "").split("_real")
    verdict = lambda ok: "correct" if ok else "wrong"
    w("fig_example.tex", "\n".join([
        r"\fbox{\begin{minipage}{0.94\columnwidth}",
        rf"\textbf{{Clean}} (model answers {ex['clean_answer']}, {verdict(ex['clean_correct'])})",
        "", r"\smallskip",
        r"\noindent\emph{" + tex(ex["clean_question"]) + "}",
        "", r"\medskip\hrule\medskip", "",
        rf"\textbf{{$r{{=}}{rate}\%$, $\rho{{=}}{rho}\%$}} (model answers {ex['typo_answer']}, "
        rf"{verdict(ex['typo_correct'])})",
        "", r"\smallskip",
        r"\noindent\emph{" + shown + "}",
        r"\end{minipage}}",
    ]))
    words_ = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "eleven", "twelve"]
    num = lambda k: words_[k] if k < len(words_) else str(k)
    def pair(t):
        return rf"\texttt{{{tex(t['original'])}\arrow {tex(t['typo'])}}}"
    accepted = [t for t in real if t["spellchecker_accepts"]]
    flagged = [t for t in real if not t["spellchecker_accepts"]]
    text = (f"{num(len(real)).capitalize()} of the {num(len(ex['typos']))} typos are "
            r"\emph{real words} (" + ", ".join(pair(t) for t in real) + ")")
    if not flagged:
        text += " and are invisible to a spell checker. "
    elif not accepted:
        text += "; the spell checker of \\S\\ref{sec:fixes} flags all of them. "
    else:
        text += (f"; {num(len(accepted))} of them "
                 f"({', '.join(pair(t) for t in accepted)}) are accepted by the spell checker "
                 f"of \\S\\ref{{sec:fixes}}. ")
    w("fig_example_caption.tex", "\\newcommand{\\FigExampleCaption}{"
      "A single GSM8K item under our generator. Numbers and \\LaTeX{} are protected; "
      "only alphabetic words are corrupted. " + text +
      f"The model answers {ex['typo_answer']} instead of {ex['gold']}." + "}")


def tab_accuracy_flips():
    """Every configuration: accuracy, answered count, tokens, paired flips (Table A1)."""
    acc = {ds: acc_counts(ds) for ds, _, _ in DATASETS}
    tok = {ds: load(ds, "reasoning_length_absolute").set_index("config") for ds, _, _ in DATASETS}
    flip = {ds: load(ds, "flips_vs_clean").set_index("config") for ds, _, _ in DATASETS}
    rows = []
    for c in ORDER:
        cells = []
        for ds, _, _ in DATASETS:
            k, na = acc[ds][c]
            tk = rnd(frac(tok[ds].loc[c, "sum_tok"], tok[ds].loc[c, "n_answered"]), 0)
            if c == "clean":
                cells += [pct(k, na), f"{na}", tk, "--", "--", "--"]
            else:
                f = flip[ds].loc[c]
                cells += [pct(k, na), f"{na}", tk, f"{int(f.r2w)}", f"{int(f.w2r)}",
                          pfmt(f.mcnemar_p)]
        rows.append(c.replace("_", r"\_") + " & " + " & ".join(cells) + r" \\")
    head = (r"\textbf{config} & " +
            " & ".join([r"acc & $n_a$ & tok & r$\to$w & w$\to$r & $p$"] * 3) + r" \\")
    w("tab_grid.tex", "\n".join([
        r"\begin{tabular}{l rrrrrr rrrrrr rrrrrr}", r"\toprule",
        r"& \multicolumn{6}{c}{\textbf{GSM8K}} & \multicolumn{6}{c}{\textbf{MATH-500}}"
        r" & \multicolumn{6}{c}{\textbf{ARC-Challenge}} \\",
        r"\cmidrule(lr){2-7}\cmidrule(lr){8-13}\cmidrule(lr){14-19}",
        head, r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def tab_realword_paired():
    """The controlled paired contrast at every rate and rho pair (Table A3)."""
    paired = {ds: load(ds, "realword_paired").set_index(["rate", "compare"])
              for ds, _, _ in DATASETS}
    rows = []
    for rate in RATES:
        for lo, hi in ((10, 70), (10, 40), (40, 70)):
            key = (rate, f"real{lo}_to_real{hi}")
            cells = []
            for ds, _, _ in DATASETS:
                r = paired[ds].loc[key]
                star = r"$^{*}$" if r.mcnemar_p < 0.05 else ""
                cells += [signed(frac(r.w2r - r.r2w, r.n_both) * 100) + star,
                          f"{int(r.r2w)}/{int(r.w2r)}", pfmt(r.mcnemar_p)]
            rows.append(f"{rate} & {lo}$\\to${hi} & " + " & ".join(cells) + r" \\")
    w("tab_realword_paired.tex", "\n".join([
        r"\begin{tabular}{ll rrr rrr rrr}", r"\toprule",
        r"& & \multicolumn{3}{c}{\textbf{GSM8K}} & \multicolumn{3}{c}{\textbf{MATH-500}}"
        r" & \multicolumn{3}{c}{\textbf{ARC-Challenge}} \\",
        r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}\cmidrule(lr){9-11}",
        r"\textbf{$r$} & \textbf{$\rho$} & " + " & ".join([r"$\Delta$acc & r/w & $p$"] * 3) + r" \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def odds_lost(coef):
    return dec(((1 - math.exp(coef)) * 100))


def tab_realword_logit():
    """The per-typo logistic fit, one column per dataset (Table A2)."""
    lg = {ds: load(ds, "realword_pertypo_logit").iloc[0] for ds, _, _ in DATASETS}

    def row(label, fn):
        return label + " & " + " & ".join(fn(lg[ds]) for ds, _, _ in DATASETS) + r" \\"

    rows = [
        row(r"traces in the fit, $n$", lambda d: f"{int(d.n)}"),
        row(r"intercept", lambda d: f"{d.intercept:+.3f}"),
        row(r"coefficient, real-word", lambda d: f"{d.coef_num_real:+.4f}"),
        row(r"coefficient, non-word", lambda d: f"{d.coef_num_nonword:+.4f}"),
        row(r"odds multiplier, real-word", lambda d: rnd(dec((math.exp(d.coef_num_real))), 3)),
        row(r"odds multiplier, non-word", lambda d: rnd(dec((math.exp(d.coef_num_nonword))), 3)),
        row(r"odds lost per real-word typo", lambda d: rnd(odds_lost(d.coef_num_real)) + r"\%"),
        row(r"odds lost per non-word typo", lambda d: rnd(odds_lost(d.coef_num_nonword)) + r"\%"),
        r"\midrule",
        row(r"\textbf{relative loss, real / non-word}",
            lambda d: r"\textbf{" + rnd(dec((d.relative_loss_real_vs_nonword))) + r"$\times$}"),
        row(r"\quad 95\% CI (bootstrap over questions)",
            lambda d: f"[{rnd(dec(d.relative_loss_ci_lo))}, {rnd(dec(d.relative_loss_ci_hi))}]"),
        row(r"non-word coefficient, 95\% CI",
            lambda d: f"[{d.coef_nonword_ci_lo:+.4f}, {d.coef_nonword_ci_hi:+.4f}]"),
    ]
    w("tab_realword_logit.tex", "\n".join([
        r"\begin{tabular}{lrrr}", r"\toprule",
        r"& \textbf{GSM8K} & \textbf{MATH-500} & \textbf{ARC-C} \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def tab_support():
    """Token length and marker densities (Table A4)."""
    abs_ = {ds: load(ds, "reasoning_length_absolute").set_index("config") for ds, _, _ in DATASETS}
    lout = {ds: load(ds, "length_by_outcome").set_index("config") for ds, _, _ in DATASETS}
    sd = {ds: load(ds, "self_doubt_per_config").set_index("config") for ds, _, _ in DATASETS}
    sdo = {ds: load(ds, "self_doubt_by_outcome").set_index("config") for ds, _, _ in DATASETS}
    rows = []
    for c in ORDER:
        cells = []
        for ds, _, _ in DATASETS:
            a, lo, s, so = abs_[ds].loc[c], lout[ds].loc[c], sd[ds].loc[c], sdo[ds].loc[c]
            cells += [rnd(frac(a.sum_tok, a.n_answered), 0),
                      rnd(frac(lo.sum_tok_correct, lo.n_correct), 0),
                      rnd(frac(lo.sum_tok_wrong, lo.n_wrong), 0),
                      rnd(frac(s.uncertainty_n * 1000, s.words)),
                      rnd(frac(s.second_guess_n * 1000, s.words)),
                      ratio(so.un_n_wrong, so.words_wrong, so.un_n_correct, so.words_correct)]
        rows.append(c.replace("_", r"\_") + " & " + " & ".join(cells) + r" \\")
    w("tab_support.tex", "\n".join([
        r"\begin{tabular}{l rrrrrr rrrrrr rrrrrr}", r"\toprule",
        r"& \multicolumn{6}{c}{\textbf{GSM8K}} & \multicolumn{6}{c}{\textbf{MATH-500}}"
        r" & \multicolumn{6}{c}{\textbf{ARC-Challenge}} \\",
        r"\cmidrule(lr){2-7}\cmidrule(lr){8-13}\cmidrule(lr){14-19}",
        r"\textbf{config} & " +
        " & ".join([r"tok & tok$_{c}$ & tok$_{w}$ & uncert. & 2nd-g. & u.w/c"] * 3) + r" \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def judge_tables(ds):
    per = load(ds, "judge_scalar_per_config").set_index("config")
    rea = load(ds, "judge_scalar_by_real").set_index("real_ratio")
    out = load(ds, "judge_scalar_by_outcome").set_index("config")
    return per, rea, out


def tab_judge():
    """LLM-judge scores by rate, rho and final answer (Table 2). Every row pools
    the judged traces of its group; the final-answer rows use typo traces only."""
    J = {ds: judge_tables(ds) for ds, _, _ in DATASETS}

    def cells(fn):
        return " & ".join(fn(ds) for ds, _, _ in DATASETS)

    def pooled(per, cfgs, col):
        return rnd(frac(sum(per.loc[c, col] for c in cfgs), sum(per.loc[c, "n"] for c in cfgs)), 2)

    rows = [r"\multicolumn{7}{l}{\emph{clean}} \\",
            "\\quad --- & " + cells(lambda ds: pooled(J[ds][0], ["clean"], "sum_repair_understanding")
                                    + " & " + pooled(J[ds][0], ["clean"], "sum_self_doubt")) + r" \\",
            r"\midrule \multicolumn{7}{l}{\emph{by typo rate }$r$} \\"]
    for r in RATES:
        cfgs = [f"typo{r}_real{p}" for p in RHOS]
        rows.append(f"\\quad {r}\\% & " + cells(
            lambda ds, cfgs=cfgs: pooled(J[ds][0], cfgs, "sum_repair_understanding") + " & "
            + pooled(J[ds][0], cfgs, "sum_self_doubt")) + r" \\")
    rows.append(r"\midrule \multicolumn{7}{l}{\emph{by real-word ratio }$\rho$} \\")
    for p in RHOS:
        rows.append(f"\\quad {p}\\% & " + cells(
            lambda ds, p=p: rnd(frac(J[ds][1].loc[p, "sum_repair_understanding"], J[ds][1].loc[p, "n"]), 2)
            + " & " + rnd(frac(J[ds][1].loc[p, "sum_self_doubt"], J[ds][1].loc[p, "n"]), 2)) + r" \\")
    rows.append(r"\midrule \multicolumn{7}{l}{\emph{by final answer (typo configs)}} \\")
    for key in ("correct", "wrong"):
        rows.append(f"\\quad {key} & " + cells(
            lambda ds, key=key: rnd(frac(J[ds][2].loc["__typo__", f"sum_repair_{key}"],
                                         J[ds][2].loc["__typo__", f"n_{key}"]), 2)
            + " & " + rnd(frac(J[ds][2].loc["__typo__", f"sum_doubt_{key}"],
                               J[ds][2].loc["__typo__", f"n_{key}"]), 2)) + r" \\")
    w("tab_judge.tex", "\n".join([
        r"\begin{tabular}{l rr rr rr}", r"\toprule",
        r"& \multicolumn{2}{c}{\textbf{GSM8K}} & \multicolumn{2}{c}{\textbf{MATH-500}}"
        r" & \multicolumn{2}{c}{\textbf{ARC-C}} \\",
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
        r"\textbf{condition} & " + " & ".join([r"repair & doubt"] * 3) + r" \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def tab_repair_words():
    """Word-level handling per configuration, and misread by outcome (Table A5)."""
    per = {ds: load(ds, "repair_wordlevel_per_config").set_index("config") for ds, _, _ in DATASETS}
    out = {ds: load(ds, "repair_wordlevel_by_outcome").set_index("config") for ds, _, _ in DATASETS}
    rows = []
    for c in TYPO:
        cells = []
        for ds, _, _ in DATASETS:
            r_, o_ = per[ds].loc[c], out[ds].loc[c]
            n = r_.n_corrupt_words
            cells += [pct(r_.silent_fix_n, n), pct(r_.flagged_n, n), pct(r_.misread_n, n),
                      pct(r_.not_used_n, n), pct(o_.misread_n_correct, o_.words_correct),
                      pct(o_.misread_n_wrong, o_.words_wrong)]
        rate, rho = c.replace("typo", "").split("_real")
        rows.append(f"{rate} & {rho} & " + " & ".join(cells) + r" \\")
    w("tab_repair.tex", "\n".join([
        r"\begin{tabular}{ll rrrrrr rrrrrr rrrrrr}", r"\toprule",
        r"& & \multicolumn{6}{c}{\textbf{GSM8K}} & \multicolumn{6}{c}{\textbf{MATH-500}}"
        r" & \multicolumn{6}{c}{\textbf{ARC-Challenge}} \\",
        r"\cmidrule(lr){3-8}\cmidrule(lr){9-14}\cmidrule(lr){15-20}",
        r"\textbf{$r$} & \textbf{$\rho$} & " +
        " & ".join([r"silent & flag & mis. & unused & mis$_{c}$ & mis$_{w}$"] * 3) + r" \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


def fix_deltas():
    """{arm: {config: exact accuracy change vs. the unmodified prompt, in pp}}."""
    base = acc_counts("gsm8k")
    out = {}
    for name, run in ARMS:
        arm = acc_counts(run)
        out[name] = {c: (frac(*arm[c]) - frac(*base[c])) * 100 for c in TYPO}
    return out


def tab_fixes():
    """GSM8K accuracy under each mitigation (Table 3)."""
    base = acc_counts("gsm8k")
    arms = {name: acc_counts(run) for name, run in ARMS}
    deltas = fix_deltas()
    rows = []
    for c in TYPO:
        r_, p_ = c.replace("typo", "").split("_real")
        cells = [pct(*base[c])]
        for name, _ in ARMS:
            cells += [pct(*arms[name][c]), signed(deltas[name][c])]
        rows.append(f"{r_}/{p_} & " + " & ".join(cells) + r" \\")
    means = [sum(deltas[name].values()) / len(TYPO) for name, _ in ARMS]
    rows.append(r"\midrule \textbf{mean} & & " +
                " & ".join(r"& \textbf{%s}" % signed(m) for m in means) + r" \\")
    w("tab_fixes.tex", "\n".join([
        r"\begin{tabular}{lr rr rr rr}", r"\toprule",
        r"& \textbf{no fix} & \multicolumn{2}{c}{\textbf{warn}}"
        r" & \multicolumn{2}{c}{\textbf{rewrite}}"
        r" & \multicolumn{2}{c}{\textbf{spell check}} \\",
        r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}",
        r"\textbf{$r$/$\rho$} & acc & acc & $\Delta$ & acc & $\Delta$ & acc & $\Delta$ \\",
        r"\midrule", *rows, r"\bottomrule", r"\end{tabular}"]))


# =====================================================================
# Every number quoted in the prose
# =====================================================================
def numbers():
    """report/numbers.txt: one line per number the prose quotes, with its source."""
    lines = []

    def put(key, value, source):
        lines.append(f"{key:58s} {value:>14s}   {source}")

    for ds, label, _ in DATASETS:
        acc = acc_counts(ds)
        src = f"results/{ds}/accuracy_per_config.csv"
        put(f"{ds}: accuracy clean (%)", pct(*acc["clean"]), src)
        put(f"{ds}: accuracy typo75_real70 (%)", pct(*acc["typo75_real70"]), src)
        put(f"{ds}: drop clean -> typo75_real70 (pp)",
            rnd((frac(*acc["clean"]) - frac(*acc["typo75_real70"])) * 100), src)
        a = load(ds, "accuracy_per_config").set_index("config")
        put(f"{ds}: strict accuracy clean (%)", pct(acc["clean"][0], a.loc["clean", "n"]), src)
        put(f"{ds}: strict accuracy typo75_real70 (%)",
            pct(acc["typo75_real70"][0], a.loc["typo75_real70", "n"]), src)
        f = load(ds, "flips_vs_clean").set_index("config")
        fs = f"results/{ds}/flips_vs_clean.csv"
        r = f.loc["typo75_real70"]
        put(f"{ds}: typo75_real70 flips right->wrong / wrong->right / n_both",
            f"{int(r.r2w)}/{int(r.w2r)}/{int(r.n_both)}", fs)
        put(f"{ds}: typo75_real70 McNemar p", f"{r.mcnemar_p:.3g}", fs)
        sig = [c for c in TYPO if f.loc[c, "mcnemar_p_holm"] < 0.05]
        put(f"{ds}: configs significant after Holm", f"{len(sig)}/9", fs)
        put(f"{ds}:   ... which", ",".join(sig) or "none", fs)
        # strict drop = completion part + quality part (accuracy_flips.py), exact from counts
        (k0, a0), (k1, a1) = acc["clean"], acc["typo75_real70"]
        n0, n1 = int(a.loc["clean", "n"]), int(a.loc["typo75_real70", "n"])
        delta = frac(k1, n1) - frac(k0, n0)
        completion = frac(k1, a1) * (frac(a1, n1) - frac(a0, n0))
        if delta:
            share = lambda x: rnd(x / delta * 100, 0).replace("-0", "0") if abs(x / delta) < Decimal("0.005") \
                else rnd(x / delta * 100, 0)
            put(f"{ds}: typo75_real70 share of strict drop from wrong answers (%)",
                share(delta - completion), src)
            put(f"{ds}: typo75_real70 share of strict drop from unanswered (%)", share(completion), src)
        t = load(ds, "reasoning_length_absolute").set_index("config")
        ts = f"results/{ds}/reasoning_length_absolute.csv"
        mt = {c: frac(t.loc[c, "sum_tok"], t.loc[c, "n_answered"]) for c in ORDER}
        top = max(TYPO, key=lambda c: mt[c])
        put(f"{ds}: mean generated tokens clean", rnd(mt["clean"], 0), ts)
        put(f"{ds}: mean generated tokens typo75_real70", rnd(mt["typo75_real70"], 0), ts)
        put(f"{ds}: max mean generated tokens (config)", f"{rnd(mt[top], 0)} ({top})", ts)
        lo = load(ds, "length_by_outcome").set_index("config")
        longer = all(lo.loc[c, "sum_tok_wrong"] * lo.loc[c, "n_correct"]
                     > lo.loc[c, "sum_tok_correct"] * lo.loc[c, "n_wrong"] for c in ORDER)
        put(f"{ds}: wrong answers longer than correct in every config", str(longer),
            f"results/{ds}/length_by_outcome.csv")

        lg = load(ds, "realword_pertypo_logit").iloc[0]
        put(f"{ds}: per-typo relative loss real/non-word (x) [95% CI]",
            f"{rnd(dec(lg.relative_loss_real_vs_nonword))} [{rnd(dec(lg.relative_loss_ci_lo))}, "
            f"{rnd(dec(lg.relative_loss_ci_hi))}]", f"results/{ds}/realword_pertypo_logit.csv")
        put(f"{ds}: non-word coefficient [95% CI]",
            f"{lg.coef_num_nonword:+.4f} [{lg.coef_nonword_ci_lo:+.4f}, {lg.coef_nonword_ci_hi:+.4f}]",
            f"results/{ds}/realword_pertypo_logit.csv")
        rp = load(ds, "realword_paired").set_index(["rate", "compare"])
        rs = f"results/{ds}/realword_paired.csv"
        for rate in RATES:
            for lo_, hi in ((10, 70), (10, 40), (40, 70)):
                x = rp.loc[(rate, f"real{lo_}_to_real{hi}")]
                put(f"{ds}: paired r={rate} rho {lo_}->{hi}: delta pp | p | p_holm",
                    f"{signed(frac(x.w2r - x.r2w, x.n_both) * 100)} | {x.mcnemar_p:.3g} | "
                    f"{x.mcnemar_p_holm:.3g}", rs)

        per = load(ds, "repair_wordlevel_per_config").set_index("config")
        ws = f"results/{ds}/repair_wordlevel_per_config.csv"
        for r in RATES:
            cfgs = [f"typo{r}_real{p}" for p in RHOS]
            s = repair_shares(per, cfgs)
            put(f"{ds}: repair pooled r={r}: silent/flagged/misread/unused (%)",
                "/".join(rnd(dec((v))) for v in s), ws)
        for p in RHOS:
            cfgs = [f"typo{r}_real{p}" for r in RATES]
            s = repair_shares(per, cfgs)
            put(f"{ds}: repair pooled rho={p}: silent/flagged/misread/unused (%)",
                "/".join(rnd(dec((v))) for v in s), ws)
        put(f"{ds}: silent fix typo25_real10 / typo75_real10 (%)",
            pct(per.loc["typo25_real10", "silent_fix_n"], per.loc["typo25_real10", "n_corrupt_words"])
            + " / " + pct(per.loc["typo75_real10", "silent_fix_n"], per.loc["typo75_real10", "n_corrupt_words"]), ws)
        put(f"{ds}: words excluded by the clean-baseline control (%)",
            pct(per["n_excluded"].sum(), per["n_excluded"].sum() + per["n_corrupt_words"].sum()), ws)
        ob = load(ds, "repair_wordlevel_by_outcome").set_index("config")
        rat = [frac(ob.loc[c, "misread_n_wrong"], ob.loc[c, "words_wrong"])
               / frac(ob.loc[c, "misread_n_correct"], ob.loc[c, "words_correct"])
               for c in TYPO if ob.loc[c, "misread_n_correct"] > 0]
        put(f"{ds}: misread wrong/correct ratio, min-max over configs",
            f"{rnd(min(rat))}-{rnd(max(rat))}", f"results/{ds}/repair_wordlevel_by_outcome.csv")

        sd = load(ds, "self_doubt_per_config").set_index("config")
        ss = f"results/{ds}/self_doubt_per_config.csv"
        dens = lambda c, cat: frac(sd.loc[c, f"{cat}_n"] * 1000, sd.loc[c, "words"])
        put(f"{ds}: uncertainty per 1k words clean / typo25_real10 / typo75_real10",
            " / ".join(rnd(dens(c, "uncertainty")) for c in ("clean", "typo25_real10", "typo75_real10")), ss)
        put(f"{ds}: second-guessing per 1k words clean / typo75_real70",
            " / ".join(rnd(dens(c, "second_guess")) for c in ("clean", "typo75_real70")), ss)
        so = load(ds, "self_doubt_by_outcome").set_index("config")
        uwc = [frac(so.loc[c, "un_n_wrong"], so.loc[c, "words_wrong"])
               / frac(so.loc[c, "un_n_correct"], so.loc[c, "words_correct"]) for c in TYPO]
        put(f"{ds}: uncertainty wrong/correct, min-max over typo configs",
            f"{rnd(min(uwc))}-{rnd(max(uwc))}", f"results/{ds}/self_doubt_by_outcome.csv")

        per_j, rea_j, out_j = judge_tables(ds)
        js = f"results/{ds}/judge_scalar_*.csv"
        ans = sum(int(load(ds, "self_doubt_per_config").set_index("config").loc[c, "n_answered"]) for c in ORDER)
        put(f"{ds}: judge: scored / answered traces", f"{int(per_j['n'].sum())} / {ans}", js)
        byp = [frac(rea_j.loc[p, "sum_self_doubt"], rea_j.loc[p, "n"]) for p in RHOS]
        put(f"{ds}: judge doubt by rho 10/40/70", "/".join(rnd(v, 2) for v in byp), js)
        put(f"{ds}: judge doubt spread over rho", rnd(max(byp) - min(byp), 2), js)
        o = out_j.loc["__typo__"]
        put(f"{ds}: judge repair wrong vs correct (typo configs)",
            f"{rnd(frac(o.sum_repair_wrong, o.n_wrong), 2)} vs {rnd(frac(o.sum_repair_correct, o.n_correct), 2)}", js)

    deltas = fix_deltas()
    for name, run in ARMS:
        d = list(deltas[name].values())
        put(f"gsm8k {name}: mean / min / max accuracy change (pp)",
            f"{signed(sum(d) / 9)} / {signed(min(d))} / {signed(max(d))}",
            f"results/{run}/accuracy_per_config.csv")
        put(f"gsm8k {name}: configs improved / hurt", f"{sum(x > 0 for x in d)}/{sum(x < 0 for x in d)}",
            f"results/{run}/accuracy_per_config.csv")
    acc_sp = acc_counts("gsm8k_spellcheck")
    put("gsm8k spell: accuracy typo75_real70 (%)", pct(*acc_sp["typo75_real70"]),
        "results/gsm8k_spellcheck/accuracy_per_config.csv")
    med = lambda run: sorted(load(run, "reasoning_length_absolute").set_index("config").loc[TYPO, "median_tok"])[4]
    put("gsm8k: median of per-config median tokens, no fix / rewrite",
        f"{med('gsm8k'):g} / {med('gsm8k_rewrite'):g}", "results/*/reasoning_length_absolute.csv")
    sr = load("gsm8k_spellcheck", "spellcheck_recovery_by_real").set_index("real")
    for p in RHOS:
        put(f"gsm8k spell: typos restored rho={p}: pooled / mean of rates (%)",
            f"{pct(sr.loc[p, 'restored_exact_n'], sr.loc[p, 'total_typo_words'])} / "
            f"{rnd(dec((sr.loc[p, 'restored_mean_of_rates_pct'])))}",
            "results/gsm8k_spellcheck/spellcheck_recovery_by_real.csv")
    ex = json.load(open(RESULTS / "gsm8k" / "figure1_example.json", encoding="utf-8"))
    put("figure 1: answers clean / typo (gold)",
        f"{ex['clean_answer']} / {ex['typo_answer']} ({ex['gold']})", "results/gsm8k/figure1_example.json")
    put("figure 1: typos / real-word typos",
        f"{len(ex['typos'])} / {sum(t['real_word'] for t in ex['typos'])}", "results/gsm8k/figure1_example.json")
    (HERE / "numbers.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    for f in (fig_accuracy, fig_realword, fig_repair, fig_doubt, fig_example, tab_datastats,
              tab_accuracy_flips, tab_support, tab_realword_paired, tab_realword_logit,
              tab_judge, tab_repair_words, tab_fixes, numbers):
        f()
        print("  ", f.__name__)
    print("done ->", FIGDIR, TABDIR, HERE / "numbers.txt")
