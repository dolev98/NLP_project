# Report versions

`report/report.pdf` is the submitted report. This folder keeps every earlier version,
unchanged, and change-marked copies for reviewing what changed.

| File | What it is |
|---|---|
| `1_team_version.pdf` | The team's report, 19 Sep 2026 (commit `452db83` of the working repo). |
| `2_review_acl_format.pdf` | Review, first step, 22 Sep 2026 (commit `b10dfe7`): ACL format within 8 pages, numeric fixes, findings in the introduction. |
| `3_review_related_work.pdf` | Review, second step, 23 Sep 2026 (commit `d307059`): related work and bibliography checked against the sources. |
| `4_submission.pdf` | The submitted report, a copy of `report/report.pdf`: results from the fixed code and repaired data, text updated to match. |
| `changes_all_team_to_submission.pdf` | Every change from the team's version (1) to the submission (4) in one file. |
| `changes_step1_team_to_acl_format.pdf` | Changes from 1 to 2 only. |
| `changes_step2_related_work_and_bibliography.pdf` | Changes from 2 to 3 only. |
| `changes_step3_results_rebuild.pdf` | Changes from 3 to 4 only. |
| `edit1_team_to_ACL_lecturer_format/` | Editable LaTeX of the first edit (1 to 2) in the exact format of the lecturer's template: the team's version, the edited version, and a change-marked copy that `make_changes.py` rebuilds after edits. See its README. |

How the change-marked copies are coloured:

- **red strikethrough**: deleted text;
- **blue underline**: added in the ACL-format, writing and bibliography review (steps 1 and 2);
- **green underline**: added because of the results checks: a number replaced by a
  different one in step 1, and everything in step 3 (new numbers from the fixed code
  and repaired data, regenerated tables and Figure 1, text corrected to match the data).

In the combined file each added passage is coloured by the step that introduced it,
found by tracing its words back through the versions; a passage that mixes a review
rewrite with a new result number is shown green. Tables, the Figure 1 example,
captions and references are marked too; figures are images and show the newer
version. The copies are built with `latexdiff`, with the generated tables and the
bibliography inlined on both sides so that changed values are marked.
