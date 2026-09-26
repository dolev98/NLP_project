# Review of the edit1 document: numbers check and a new Related Work

`edit1-review-team_suggestions.md` is the team's edit1 document (the shared doc,
exported to Markdown) with my suggestions marked as `~~old~~new`. The strikethrough
suggestions that were already in the document are left as they were.

Two things were done:

1. a check that every number in the document matches the validated results;
2. a rewrite of §2 Related Work, with the references it needs.

## 1. Numbers: all correct

- **Tables 1 to 8:** all 890 numeric cells match `report/tables/*.tex` at `f5d6c41`,
  apart from the two corrections below.
- **Table 9 (Appendix F):** recomputed from `Dolevabudi/silent-tax-results` at `b64e5b2`.
  Every cell matches: GSM8K 39, MATH-500 38, ARC 83, at most 17 of 500 in one condition.
- **Prose:** every number was checked against `report/numbers.txt` or recomputed. This
  includes the length medians (1,299.5 and 736), the GPQA figure (51.6% answered-only
  on 198 questions) and Figure 1 (against `results/gsm8k/figure1_example.json`).

In two cells the document is right and `make_assets.py` is not:

| Cell | `make_assets.py` gives | Correct | Why |
|---|---|---|---|
| Table 4 (`tab_grid`), ARC typo25_real10, p | 0.689 | 0.688 | The exact p is 0.68849974 (26/30 flips). The CSV stores 0.6885 and the table rounds it a second time. |
| Table 5 (`tab_realword_logit`), ARC relative-loss CI | [-52.4, 69.8] | n/a† | The ARC non-word coefficient's CI includes 0, so the ratio has no finite interval. The printed endpoints change with the bootstrap seed. |

If the tables are regenerated, both values come back. The fix belongs in
`make_assets.py`, and in `numbers.txt` line 100.

The other suggestions change statements, not numbers:

| Where | Change | Why |
|---|---|---|
| Fig. 5 and Table 7 captions | "second-guessing stays roughly flat" becomes "rises only modestly on GSM8K (mostly more 'wait'), flat on MATH-500 and ARC" | GSM8K second-guessing is 11.2 on clean and 12.5 to 13.5 on typo input. The Fig. 5 caption also said the split by final answer is in Table 7, which only has the ratio. |
| Conclusion | `ronshtricker/typo-reasoning-results` becomes `Dolevabudi/silent-tax-results`, plus "the steps in the repository README" | Ron's repo still has the 50 cut-off rows, so it reproduces the old 91.4% and 60.4%. |
| Abstract, Conclusion | Drop "consistently" | ARC at r=25 is on par with clean (Table 4), which §5.1 itself says. |
| §5.2 | Drop "consistent with its smaller number of corrupted words" | Per Table 1, MATH-500 receives almost as many typos as ARC (4.0 / 7.9 / 11.8 against 4.2 / 8.3 / 12.4), and ARC does show the effect. |
| Fig. 4 caption | Add "on GSM8K, flagging levels off above ρ=40" | 21.4, 25.4, 24.5 by ρ, as §5.3 already says. |
| Table 1 caption | ARC is the first 500 four-option questions | Three of the first 503 ARC questions do not have four options. |
| §5.5 | The spell checker only touches words of four or more letters | `apply_spellcheck` skips shorter words. |
| §1 | Drop "accidentally" | The generator targets real-word typos on purpose. |

## 2. Related Work, rewritten

The new §2 has four paragraphs: typos in NLP, typos and LLMs, what is missing, and
reasoning traces. It is 381 words, against about 400 before.

**The gap it states.**

1. **No prior work varies the share of real-word typos while keeping the number of
   typos fixed.** Real-word substitutions only appear as a separate perturbation type,
   such as the homophones of Mu et al. (2025). The distinction itself comes from
   spelling correction (Kukich, 1992).
2. **No prior work reads the reasoning trace.** Prior studies score final answers. Gan
   et al. (2024) show one chain-of-thought example and an attention map, but nothing
   systematic. Mu et al. (2025) test o1-mini and o3-mini, whose traces are hidden.

**The three proposal papers, read in full.**

- **Gan et al. (2024):** adversarial, gradient-guided search for 1 to 8 character edits
  on GSM8K, BBH and MMLU. The models are instruction-tuned ones with chain-of-thought
  prompting; there are no reasoning models. Accuracy is the metric.
- **Chai et al. (2024):** random character-level noise. Their central claim is that
  subword tokenization causes the damage. GSM8K is run without chain-of-thought.
- **Zhao et al. (2026, MulTypo):** four keyboard edits (replace, insert, delete,
  transpose), 18 open models and 12 languages. Only accuracy or BLEU is reported, and
  no thinking mode is used.

This is why the §1 edit attributes the tokenization link to Chai et al. only, and says
that prior work does not *systematically* analyze the reasoning process.

**Other edits.**

- §3.1 now credits MulTypo, because our generator reimplements its four edits.
- The Limitations now cite GPQA (Rein et al., 2024).

**References.**

- Removed, because the new §2 does not cite them: HotFlip, TextFooler, PromptRobust.
- Added: Kukich 1992, Wang et al. 2024, Mu et al. 2025, Fan et al. 2025, Rein et al. 2024.
- Fixed: missing page numbers, "Try ARC", and DeepSeek-R1 now points to the Nature version.

Every citation in the document now has an entry, and every entry is cited. Each new
reference was checked on its publisher or arXiv page (see Sources).

To move §2 into `report.tex`, your `custom.bib` already has almost everything. Only
these two entries are missing:

```bibtex
@article{mu2025robustness,
  title   = {Robustness of Prompting: Enhancing Robustness of Large Language Models Against Prompting Attacks},
  author  = {Mu, Lin and Chu, Guowei and Ni, Li and Sang, Lei and Zhang, Yiwen},
  journal = {arXiv preprint arXiv:2506.03627},
  year    = {2025}
}

@inproceedings{fan2025missing,
  title     = {Missing Premise exacerbates Overthinking: Are Reasoning Models losing Critical Thinking Skill?},
  author    = {Fan, Chenrui and Li, Ming and Sun, Lichao and Zhou, Tianyi},
  booktitle = {Second Conference on Language Modeling},
  year      = {2025}
}
```

## Notes

- **Page budget.** With every suggestion accepted, the body grows by about 25 words.
  Check that the Conclusion still ends on page 8.
- **Not cited on purpose.** Two August 2026 preprints test thinking models under typos:
  Hu et al., arXiv:2608.03970, and Zhu et al., arXiv:2608.22140 (accepted to EMNLP 2026).
  We left them out because they are very recent. Both report accuracy only and do not
  read the trace, so the gap as worded above still holds.

## Sources

- Kukich 1992: https://dl.acm.org/doi/10.1145/146370.146380
- Wang et al. 2024: https://aclanthology.org/2024.findings-emnlp.697/
- Mu et al. 2025: https://arxiv.org/abs/2506.03627
- Fan et al. 2025 (COLM 2025): https://openreview.net/forum?id=ufozo2Wc9e
- Rein et al. 2024 (COLM 2024): https://arxiv.org/abs/2311.12022
- Gan et al. 2024: https://aclanthology.org/2024.emnlp-main.584/
- Chai et al. 2024: https://aclanthology.org/2024.findings-emnlp.86/
- Zhao et al. 2026: https://aclanthology.org/2026.acl-long.729/
- DeepSeek-R1 in Nature: https://www.nature.com/articles/s41586-025-09422-z
