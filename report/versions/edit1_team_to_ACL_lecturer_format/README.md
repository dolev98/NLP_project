# Edit 1: team version -> ACL format of the lecturer's template

| Folder | What it is | Main file |
|---|---|---|
| `1_original_team_version/` | The team's report, 19 Sep 2026 (commit `452db83`), unchanged | `report.tex` |
| `2_edited_ACL_lecturer_format/` | The first edit (ACL migration, 22 Sep, commit `b10dfe7`) in the exact format of the lecturer's template: same preamble, author block, section order (Discussion, Limitations, AI Disclosure, Conclusion) and appendix layout | `report.tex` |
| `3_changes_marked/` | Every change from 1 to 2: red strikethrough = deleted, blue underline = added, green underline = a number replaced by a different one | `main.tex` |

Each folder compiles on its own with pdflatex (folders 1 and 2 also need bibtex):

    pdflatex report && bibtex report && pdflatex report && pdflatex report

On Overleaf: upload one folder as a project and set its main file.

After you edit folder 2, rebuild the marked copy (needs pdflatex, bibtex and latexdiff):

    python3 make_changes.py

Known points about folder 2: the Conclusion falls on page 9 (the template order puts
it after Limitations and AI Disclosure); Tables 1 and 2 are slightly wider than the
column, as they were in the 22 Sep version.
