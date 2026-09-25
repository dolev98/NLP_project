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
    # the edited version lets the long Hub name break; give the original the same hint
    s = s.replace(r"\texttt{ronshtricker/typo-reasoning-results}",
                  r"\texttt{ronshtricker/\allowbreak typo-reasoning-results}")
    head, tail = s.split(r"\bibliography{custom}")
    return head + bbl(src, name) + tail


FLOAT = re.compile(r"\\begin\{(figure\*?|table\*?)\}.*?\\end\{\1\}", re.S)


def pull_floats(s):
    """Replace every labelled figure/table by a placeholder line; return text and {label: float}."""
    floats = {}
    def rep(m):
        lab = re.search(r"\\label\{([^}]*)\}", m.group(0))
        if not lab:
            return m.group(0)
        floats[lab.group(1)] = m.group(0)
        return "\n\\FLOATPLACEHOLDER{" + lab.group(1) + "}\n"
    return FLOAT.sub(rep, s), floats


def latexdiff_fragment(old, new):
    d = tempfile.mkdtemp(dir=TMP)
    open(os.path.join(d, "a.tex"), "w").write(old)
    open(os.path.join(d, "b.tex"), "w").write(new)
    r = run("latexdiff --type=UNDERLINE --math-markup=whole --append-safecmd=citep,citet a.tex b.tex", d)
    return r.stdout


def caption_of(f):
    m = re.search(r"\\caption\{", f)
    j = skip_group(f, m.end())
    return f[m.end():j - 1], m.start(), j


def strike_block(body):
    """Old minipage body with every text paragraph struck through (for redesigned boxes)."""
    out = []
    for para in re.split(r"\n\s*\n", body.strip()):
        p = para.strip()
        if not p or re.fullmatch(r"(\\(smallskip|medskip|bigskip|hrule|noindent)\s*)+", p):
            out.append(p); continue
        p = p.replace("\\\\", " ").replace("\\noindent", "")
        out.append("\\noindent\\DIFdelFL{" + p + "}")
    return "\n\n".join(out)


def float_diff(label, old, new):
    """Diff of one figure/table (the float itself when unchanged)."""
    if old == new:
        return new
    d = latexdiff_fragment(old, new)
    structural = re.search(r"%DIFDELCMD <.*\\(begin|end)\{(minipage|tabular)\}", d)
    if not structural:
        return d
    # a table whose rows are unchanged but whose wrapper changed (e.g. scaled to the
    # column): show the new table as it is and mark only the caption
    tab = re.compile(r"\\begin\{tabular\}.*?\\end\{tabular\}", re.S)
    ot, nt = tab.search(old), tab.search(new)
    if ot and nt and ot.group(0) == nt.group(0):
        oc, _, _ = caption_of(old)
        nc, ns, ne = caption_of(new)
        cap = latexdiff_fragment("\\caption{" + oc + "}", "\\caption{" + nc + "}").strip()
        return new[:ns] + cap + new[ne:]
    # the box/table itself was redesigned: show the old one struck through above the new one
    oc, _, _ = caption_of(old)
    nc, ns, ne = caption_of(new)
    om = re.search(r"\\begin\{minipage\}\{[^}]*\}(.*?)\\end\{minipage\}", old, re.S)
    nm = re.search(r"\\fbox\{\\begin\{minipage\}.*?\\end\{minipage\}\}", new, re.S)
    if not (om and nm):
        return d
    cap = latexdiff_fragment("\\caption{" + oc + "}", "\\caption{" + nc + "}").strip()
    head = new[:new.index(nm.group(0))]
    old_box = "\\fbox{\\begin{minipage}{0.93\\columnwidth}\n" + strike_block(om.group(1)) + "\n\\end{minipage}}"
    return (head + "{\\scriptsize\\color{red}\\textbf{Old version of this box (deleted):}}\\\\[2pt]\n" + old_box
            + "\n\n\\medskip{\\scriptsize\\color{blue}\\textbf{New version of this box:}}\\\\[2pt]\n"
            + nm.group(0) + "\n" + cap + new[ne:])


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
    old_text, old_floats = pull_floats(flatten(OLD, "old"))
    new_text, new_floats = pull_floats(flatten(NEW, "new"))
    open(os.path.join(d, "old.tex"), "w").write(old_text)
    open(os.path.join(d, "new.tex"), "w").write(new_text)
    r = run("latexdiff --type=UNDERLINE --math-markup=whole --append-safecmd=citep,citet old.tex new.tex > main.tex", d)
    if r.returncode:
        raise SystemExit("latexdiff failed:\n" + r.stderr)
    t = open(os.path.join(d, "main.tex")).read()
    # put the floats back: each diffed on its own, at its place in the edited version
    def put(m):
        lab = m.group(1)
        if lab in new_floats:
            return float_diff(lab, old_floats.get(lab), new_floats[lab]) if lab in old_floats else new_floats[lab]
        return m.group(0)
    lines = []
    for line in t.split("\n"):
        c = re.search(r"(?<!\\)%", line)                   # the comment part holds deleted text
        code, comment = (line[:c.start()], line[c.start():]) if c else (line, "")
        code = re.sub(r"\\FLOATPLACEHOLDER\{([^}]*)\}", lambda m: put(m), code)
        line = code + comment
        m = re.search(r"\\FLOATPLACEHOLDER\{([^}]*)\}", comment)
        if m and m.group(1) not in new_floats:              # a float that was removed
            cap, _, _ = caption_of(old_floats[m.group(1)])
            line += "\n\\begin{center}\\fbox{\\parbox{0.9\\linewidth}{\\small\\DIFdel{Removed " + \
                    ("table" if m.group(1).startswith("tab") else "figure") + ": " + \
                    re.sub(r"\\(label|ref)\{[^}]*\}", "", cap) + "}}}\\end{center}"
        lines.append(line)
    t = "\n".join(lines)
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
    body = body.replace("\\begin{table}[!ht]", "\\begin{table}[H]")
    pre += ("\\usepackage{adjustbox}\n\\usepackage{float}\n\\definecolor{DIFgreen}{rgb}{0,0.5,0.1}\n"
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
