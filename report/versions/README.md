# Report versions

`report/report.pdf` is the submitted report. This folder keeps every earlier version,
unchanged, and a copy that marks every change between the team's version and the
submission.

| File | What it is |
|---|---|
| `1_team_version.pdf` | The team's report, 19 Sep 2026 (commit `452db83` of the working repo). |
| `2_review_acl_format.pdf` | Review, first step, 22 Sep 2026 (commit `b10dfe7`): ACL format within 8 pages, numeric fixes, findings in the introduction. |
| `3_review_related_work.pdf` | Review, second step, 23 Sep 2026 (commit `d307059`): related work and bibliography checked against the sources. |
| `4_submission.pdf` | The submitted report, a copy of `report/report.pdf`: results from the fixed code and repaired data, text updated to match. |
| `changes_team_to_submission.pdf` | The submission with every change since the team's version marked: deleted text in red strikethrough, added text in blue underline. Tables, the Figure 1 example, captions and references are marked too; figures are images and show the final version. |

The marked copy is built with `latexdiff` from the two sources, with the generated
tables and the bibliography inlined on both sides so that changed values are marked.
