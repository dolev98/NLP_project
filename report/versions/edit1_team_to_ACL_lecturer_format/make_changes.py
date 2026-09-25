"""Rebuild 3_changes_marked/main.tex and main.pdf after you edit a version.

    python3 make_changes.py

Compares 1_original_team_version/report.tex with 2_edited_ACL_lecturer_format/report.tex.
Both sides are flattened first (generated tables inlined, bibliography inlined as
rendered by the ACL style), so table values and references are marked too.

Marks: deleted text in red strikethrough; added text in blue underline, or green
underline when a number was replaced by a different number. Figures are images and
show the edited version.

Needs a TeX installation with pdflatex, bibtex and latexdiff (TeX Live has all three).
"""
import os, re, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(HERE, "1_original_team_version")
NEW = os.path.join(HERE, "2_edited_ACL_lecturer_format")
OUT = os.path.join(HERE, "3_changes_marked")
TMP = tempfile.mkdtemp(prefix="changes_")


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def bbl(src, name):
    """The bibliography of src/report.tex rendered with the ACL style."""
    d = os.path.join(TMP, "bbl_" + name)
    shutil.copytree(src, d)
    shutil.copy(os.path.join(NEW, "acl_natbib.bst"), d)
    p = os.path.join(d, "report.tex")
    s = open(p).read().replace(r"\bibliographystyle{plainnat}", r"\bibliographystyle{acl_natbib}")
    open(p, "w").write(s)
    run("pdflatex -interaction=nonstopmode report", d)
    run("bibtex report", d)
    return open(os.path.join(d, "report.bbl")).read()


NEW_TEX = open(os.path.join(NEW, "report.tex")).read()
AUTHOR = re.search(r"\\author\{.*?\n\}\n", NEW_TEX, re.S).group(0)
TITLE = re.search(r"\\title\{[^\n]*\}\n", NEW_TEX).group(0)


def flatten(src, name):
    s = open(os.path.join(src, "report.tex")).read()
    def inl(m):
        f = os.path.join(src, "tables", m.group(1) + ".tex")
        return open(f).read().rstrip("\n") if os.path.exists(f) else m.group(0)
    s = re.sub(r"\\input\{tables/([A-Za-z0-9_]+)(?:\.tex)?\}", inl, s)
    s = re.sub(r"\\author\{.*?\n\}\n", lambda _: AUTHOR, s, flags=re.S)       # same title/authors,
    s = re.sub(r"\\title\{.*?\}\n", lambda _: TITLE, s, count=1, flags=re.S)  # so only content is marked
    s = s.replace(r"\bibliographystyle{acl_natbib}", "").replace(r"\bibliographystyle{plainnat}", "")
    s = s.replace(r"{\small\bibliography{custom}}", r"\bibliography{custom}")
    head, tail = s.split(r"\bibliography{custom}")
    return head + bbl(src, name) + tail


def skip_group(t, i):
    depth = 1
    while i < len(t) and depth:
        if t[i] == "\\":
            i += 2; continue
        depth += {"{": 1, "}": -1}.get(t[i], 0); i += 1
    return i


MARK = re.compile(r"\\DIF(add|del)(FL)?\{|\\DIF(?:add|del)(?:begin|end)(?:FL)?\b")
NUM = re.compile(r"(?<![A-Za-z])(?<![A-Za-z]-)\d+(?:[.,]\d+)*")   # not the 8 in GSM8K


def colour(t):
    """Green when an addition replaces a deletion with different numbers, else blue."""
    out, i, last_del, del_end, n = [], 0, "", 0, {"blue": 0, "green": 0}
    for m in MARK.finditer(t):
        if m.start() < i:
            continue
        out.append(t[i:m.start()])
        if m.group(1) is None:
            out.append(m.group(0)); i = m.end(); continue
        j = skip_group(t, m.end()); inner = t[m.end():j - 1]
        if m.group(1) == "del":
            out.append(t[m.start():j]); last_del, del_end, i = inner, j, j; continue
        gap = t[del_end:m.start()] if last_del else "x"
        paired = bool(last_del) and not re.sub(r"\\DIF(?:add|del)(?:begin|end)(?:FL)?|\s", "", gap)
        nums = set(NUM.findall(inner))
        green = paired and nums and nums != set(NUM.findall(last_del))
        c = "green" if green else "blue"; n[c] += 1
        out.append(("\\DIFaddG" if green else "\\DIFaddB") + (m.group(2) or "") + "{" + inner + "}")
        last_del, i = "", j
    out.append(t[i:])
    return "".join(out), n


LEGEND = (r"\begin{center}\fbox{\parbox{0.95\linewidth}{\small\textbf{How changes are marked.} "
          r"\DIFdel{Red strikethrough}: deleted. \DIFaddB{Blue underline}: added (ACL format and writing). "
          r"\DIFaddG{Green underline}: a number replaced by a different one. Figures are images and "
          r"show the edited version. This file shows every change from the team's version to the "
          r"edited version in the lecturer's ACL format.}}\end{center}")


def main():
    d = os.path.join(TMP, "diff"); os.makedirs(d)
    open(os.path.join(d, "old.tex"), "w").write(flatten(OLD, "old"))
    open(os.path.join(d, "new.tex"), "w").write(flatten(NEW, "new"))
    r = run("latexdiff --type=UNDERLINE --math-markup=whole --append-safecmd=citep,citet old.tex new.tex > main.tex", d)
    if r.returncode:
        raise SystemExit("latexdiff failed:\n" + r.stderr)
    t = open(os.path.join(d, "main.tex")).read()
    # latexdiff makes \DIF..begin/end..FL robust; inside tables they break \midrule
    t = re.sub(r"(\\begin\{tabular\}.*?\\end\{tabular\})",
               lambda m: re.sub(r"\\DIF(?:add|del)(?:begin|end)FL\s*", "", m.group(1)), t, flags=re.S)
    # old and new values side by side widen tables: cap each at the line width
    t = re.sub(r"(?<!\{)(\\begin\{tabular\}.*?\\end\{tabular\})",
               lambda m: "\\adjustbox{max width=\\linewidth}{" + m.group(1) + "}", t, flags=re.S)
    k = t.index("\\begin{document}")
    pre, body = t[:k], t[k:]
    body, n = colour(body)
    body = re.sub(r"\\cmidrule\\DIFadd[BG]?(?:FL)?\{(\([^)]*\))\}\{\\DIFadd[BG]?(?:FL)?\{([^}]*)\}\}",
                  r"\\cmidrule\1{\2}", body)
    body = body.replace("\\maketitle", "\\maketitle\n" + LEGEND, 1)
    pre += ("\\usepackage{adjustbox}\n\\definecolor{DIFgreen}{rgb}{0,0.5,0.1}\n"
            "\\providecommand{\\DIFaddB}[1]{{\\protect\\color{blue}\\uwave{#1}}}\n"
            "\\providecommand{\\DIFaddBFL}[1]{\\DIFaddB{#1}}\n"
            "\\providecommand{\\DIFaddG}[1]{{\\protect\\color{DIFgreen}\\uwave{#1}}}\n"
            "\\providecommand{\\DIFaddGFL}[1]{\\DIFaddG{#1}}\n")
    open(os.path.join(OUT, "main.tex"), "w").write(pre + body)
    shutil.rmtree(os.path.join(OUT, "figures"), ignore_errors=True)
    shutil.copytree(os.path.join(NEW, "figures"), os.path.join(OUT, "figures"))
    for f in ("acl.sty", "acl_natbib.bst"):
        shutil.copy(os.path.join(NEW, f), OUT)
    for _ in range(2):
        run("pdflatex -interaction=nonstopmode main", OUT)
    errors = [l for l in open(os.path.join(OUT, "main.log"), errors="ignore") if l.startswith("! ")]
    for ext in ("aux", "log", "out"):
        p = os.path.join(OUT, "main." + ext)
        if os.path.exists(p): os.remove(p)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"3_changes_marked/main.pdf rebuilt: {n['blue']} blue and {n['green']} green additions, "
          f"{len(errors)} LaTeX errors")


if __name__ == "__main__":
    main()
