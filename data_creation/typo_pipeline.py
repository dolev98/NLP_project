#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Controlled real-word typo injection for one question.

For every question the generator corrupts a fixed share of the eligible prose
words (the typo rate r) and tries to make a target share of those typos land on
another valid English word (the real-word ratio rho); the rest become non-words.

  * Eligible words are ASCII-letter runs of length >= 2 outside protected spans
    (LaTeX math, LaTeX commands, numbers) and outside a small function-word list.
  * Words are chosen before rho is applied, so for a fixed r and seed the same
    words are corrupted at every rho; only the kind of typo changes.
  * Each typo is one keyboard edit (replace / delete / insert / transpose), or
    two edits with probability two_edit_prob.
  * A typo is a "real word" if it is in nltk.corpus.words. Real-word typos are
    drawn from every real word reachable with that many edits, weighted by how
    likely the edit is; if a word has none, it gets a non-word typo instead.
  * Seeding is per row (seed + row index), so every row is reproducible on its own.

generate_variants.py applies this to whole datasets.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Config:
    """One dataset variant: source dataset plus typo rate and real-word ratio."""

    dataset_name: str = "openai/gsm8k"
    dataset_config_name: Optional[str] = "main"
    dataset_split: str = "test"
    subset_size: int = 10**9       # first N rows of the source split
    text_field: str = "question"    # only this field receives typos

    typo_rate: float = 0.25          # fraction of eligible words to corrupt
    target_real_fraction: float = 0.10   # target share of typos that are real words
    # Edit weights: replace = adjacent-key substitution, transpose = swap two
    # adjacent letters, delete = drop a letter, insert = add a neighbouring key.
    typo_weights: Tuple[Tuple[str, float], ...] = (
        ("delete", 0.20),
        ("insert", 0.20),
        ("replace", 0.40),
        ("transpose", 0.20),
    )
    min_word_len: int = 2              # shorter words are never corrupted
    two_edit_prob: float = 0.10        # probability a typo gets 2 edits instead of 1
    nonword_retry_attempts: int = 10   # redraws to avoid an accidental real word

    num_proc: int = 1
    seed: int = 42

    @property
    def typo_weights_dict(self) -> Dict[str, float]:
        return {name: w for name, w in self.typo_weights}


CONFIG = Config()


# ---------------------------------------------------------------------------
# Math / number protection
# ---------------------------------------------------------------------------

# Spans matched here are never corrupted.
# Order matters: display math ($$...$$) must be tried before inline math.
_PROTECTED_PATTERN = re.compile(
    r"\$\$.*?\$\$"          # display math  $$ ... $$
    r"|\$.*?\$"             # inline math   $ ... $
    r"|\\\[.*?\\\]"         # display math  \[ ... \]
    r"|\\\(.*?\\\)"         # inline math   \( ... \)
    r"|\\[a-zA-Z]+"         # LaTeX command names, e.g. \frac, \sqrt, \times
    r"|\d+(?:[.,]\d+)?",    # bare numbers (integers / decimals)
    re.DOTALL,
)

# Candidate prose words: runs of ASCII letters only. Anything containing a
# digit or backslash therefore cannot match and stays untouched.
_WORD_PATTERN = re.compile(r"[A-Za-z]+")



def find_protected_spans(text: str) -> List[Tuple[int, int]]:
    """Return ``(start, end)`` character spans that must not be corrupted."""
    return [(m.start(), m.end()) for m in _PROTECTED_PATTERN.finditer(text)]


def _overlaps_any(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    """True if ``[start, end)`` overlaps any protected span."""
    for s, e in spans:
        if start < e and end > s:
            return True
    return False


# ---------------------------------------------------------------------------
# Shared resources, built once per process
# ---------------------------------------------------------------------------

_WORD_SET: Optional[frozenset] = None
_GENERATOR = None


def get_nltk_word_set() -> frozenset:
    """Lower-cased nltk.corpus.words, downloading the corpus on first use."""
    global _WORD_SET
    if _WORD_SET is None:
        import nltk
        from nltk.corpus import words as nltk_words
        try:
            nltk_words.words()
        except LookupError:
            nltk.download("words", quiet=True)
        _WORD_SET = frozenset(w.lower() for w in nltk_words.words())
    return _WORD_SET


def get_generator():
    """The keyboard typo generator (see keyboard_typos.py), cached per process."""
    global _GENERATOR
    if _GENERATOR is None:
        from keyboard_typos import KeyboardTypoGenerator
        _GENERATOR = KeyboardTypoGenerator(
            use_excluding_set=True,
            typo_distribution=CONFIG.typo_weights_dict.copy(),
        )
    return _GENERATOR


# ---------------------------------------------------------------------------
# Typo generation
# ---------------------------------------------------------------------------


@dataclass
class TypoResult:
    """Outcome of corrupting a single piece of text."""

    text: str          # the corrupted text
    total: int         # number of words actually changed
    real: int          # how many changes are valid English words
    nonword: int       # how many changes are non-words
    # Per-typo metadata (parallel lists, one entry per corrupted word):
    originals: List[str] = field(default_factory=list)    # word before corruption
    corrupted: List[str] = field(default_factory=list)    # word after corruption
    techniques: List[str] = field(default_factory=list)   # e.g. "replace" or "delete+insert"
    edit_counts: List[int] = field(default_factory=list)  # 1 or 2 edits
    real_flags: List[bool] = field(default_factory=list)  # real-word typo?


def _apply_one_typo(
    generator,
    word: str,
    typo_types: List[str],
    type_weights: List[float],
) -> Tuple[str, bool, Optional[str]]:
    """
    Corrupt a single word with one typo, guaranteeing a change when possible.

    A typo type is sampled according to ``type_weights``; if it happens to be
    inapplicable (e.g. ``transpose`` on a word with no swappable pair) the
    remaining types are tried as fallbacks. ``delete`` always changes a word
    of length >= 2, so a change is effectively always produced. Returns
    ``(new_word, changed, technique)``.
    """
    first = random.choices(typo_types, weights=type_weights, k=1)[0]
    order = [first] + [t for t in typo_types if t != first]
    for typo_type in order:
        new_word, changed = generator.apply_single_typo(word, typo_type)
        if changed:
            return new_word, True, typo_type
    return word, False, None


def _splice_replacements(
    text: str, replacements: List[Tuple[int, int, str]]
) -> str:
    """Splice replacements back in, right-to-left so offsets stay valid."""
    new_text = text
    for start, end, new_word in sorted(replacements, key=lambda r: r[0], reverse=True):
        new_text = new_text[:start] + new_word + new_text[end:]
    return new_text


def _real_word_choices(
    generator, word: str, word_set: frozenset, n_edits: int
) -> List[Tuple[str, str, float]]:
    """Real-word outcomes reachable with exactly n_edits edits, as
    (candidate, technique, natural probability)."""
    weights = CONFIG.typo_weights_dict
    if not hasattr(generator, "candidate_distribution"):
        return []
    dist1 = generator.candidate_distribution(word, weights)
    word_lower = word.lower()

    if n_edits == 1:
        return [
            (cand, tech, p)
            for cand, tech, p in dist1
            if cand.lower() in word_set and cand.lower() != word_lower
        ]

    choices: List[Tuple[str, str, float]] = []
    for cand1, tech1, p1 in dist1:
        for cand2, tech2, p2 in generator.candidate_distribution(cand1, weights):
            cand2_lower = cand2.lower()
            if cand2_lower in word_set and cand2_lower != word_lower:
                choices.append((cand2, f"{tech1}+{tech2}", p1 * p2))
    return choices


def _generate_nonword_typo(
    generator,
    word: str,
    word_set: frozenset,
    typo_types: List[str],
    type_weights: List[float],
    n_edits: int,
) -> Tuple[str, List[str], bool]:
    """Corrupt word with n_edits random edits, redrawing to avoid real words."""
    fallback: Optional[Tuple[str, List[str]]] = None
    for _ in range(max(1, CONFIG.nonword_retry_attempts)):
        current = word
        techs: List[str] = []
        for _ in range(n_edits):
            new_word, changed, tech = _apply_one_typo(
                generator, current, typo_types, type_weights
            )
            if changed:
                current = new_word
                techs.append(tech)
        if not techs or current == word:
            continue
        if fallback is None:
            fallback = (current, techs)
        if current.lower() not in word_set:
            return current, techs, True
    if fallback is None:
        return word, [], False
    return fallback[0], fallback[1], True


def apply_typos_controlled(
    text: str,
    generator,
    word_set: frozenset,
) -> TypoResult:
    """Inject typos so that ~CONFIG.target_real_fraction of them are real
    words. The corrupted words are chosen before the quota is applied;
    shortfalls are filled with non-words and the achieved ratio is recorded."""
    protected = find_protected_spans(text)
    ignore_set = getattr(generator, "ignore_set", set())

    eligible = [
        m
        for m in _WORD_PATTERN.finditer(text)
        if (m.end() - m.start()) >= CONFIG.min_word_len
        and not _overlaps_any(m.start(), m.end(), protected)
        and m.group().lower() not in ignore_set
    ]

    if not eligible:
        return TypoResult(text=text, total=0, real=0, nonword=0)

    n_target = max(1, round(CONFIG.typo_rate * len(eligible)))
    n_target = min(n_target, len(eligible))
    chosen = random.sample(eligible, n_target)

    # Probabilistic rounding of the real-word quota: floor + Bernoulli(frac).
    target = float(CONFIG.target_real_fraction)
    quota = int(target * n_target)
    frac = target * n_target - quota
    if frac > 0 and random.random() < frac:
        quota += 1
    quota = min(quota, n_target)

    typo_types = list(CONFIG.typo_weights_dict.keys())
    type_weights = list(CONFIG.typo_weights_dict.values())

    result = TypoResult(text=text, total=0, real=0, nonword=0)
    replacements: List[Tuple[int, int, str]] = []
    n_real_assigned = 0

    for match in random.sample(chosen, len(chosen)):
        original = match.group()
        n_edits = 2 if random.random() < CONFIG.two_edit_prob else 1

        new_word: Optional[str] = None
        techs: List[str] = []
        is_real = False

        if n_real_assigned < quota:
            # 2-edit real-word typos may not exist; fall back to 1 edit.
            for edits in ((2, 1) if n_edits == 2 else (1,)):
                choices = _real_word_choices(generator, original, word_set, edits)
                if choices:
                    idx = random.choices(
                        range(len(choices)),
                        weights=[p for _, _, p in choices],
                        k=1,
                    )[0]
                    cand, tech_label, _ = choices[idx]
                    new_word = cand
                    techs = tech_label.split("+")
                    is_real = True
                    n_real_assigned += 1
                    break

        if new_word is None:  # non-word slot (by class or real-word shortfall)
            new_word, techs, changed = _generate_nonword_typo(
                generator, original, word_set, typo_types, type_weights, n_edits
            )
            if not changed:
                continue
            is_real = new_word.lower() in word_set  # accidental real word: count honestly
            if is_real:
                n_real_assigned += 1

        result.total += 1
        if is_real:
            result.real += 1
        else:
            result.nonword += 1
        result.originals.append(original)
        result.corrupted.append(new_word)
        result.techniques.append("+".join(techs))
        result.edit_counts.append(len(techs))
        result.real_flags.append(bool(is_real))
        replacements.append((match.start(), match.end(), new_word))

    result.text = _splice_replacements(text, replacements)
    return result


# ---------------------------------------------------------------------------
# Per-row processing (used by datasets.map; must be top-level / picklable)
# ---------------------------------------------------------------------------


def process_row(example: dict, idx: int, config: Optional[Config] = None) -> dict:
    """
    Corrupt one dataset row and attach typo statistics.

    New columns
    -----------
    problem_typo      : str   -> the corrupted problem text
    num_total         : int   -> number of words actually changed
    num_real          : int   -> changes that are real English words
    num_nonword       : int   -> changes that are non-words
    real_ratio        : float -> P = num_real / num_total (in [0, 1])
    target_real_ratio : float -> the variant's target P
    typo_originals    : list[str]  -> corrupted words, before
    typo_replacements : list[str]  -> corrupted words, after
    typo_techniques   : list[str]  -> e.g. "replace" or "delete+insert"
    typo_edit_counts  : list[int]  -> 1 or 2 edits per typo
    typo_is_real      : list[bool] -> per-typo real-word flag
    """
    global CONFIG
    if config is not None:
        CONFIG = config

    # Deterministic, per-row seeding so runs are reproducible even in parallel.
    random.seed(CONFIG.seed + idx)

    generator = get_generator()
    word_set = get_nltk_word_set()

    result = apply_typos_controlled(
        text=example[CONFIG.text_field],
        generator=generator,
        word_set=word_set,
    )

    real_ratio = result.real / result.total if result.total > 0 else float("nan")
    target = CONFIG.target_real_fraction

    return {
        "problem_typo": result.text,
        "num_total": result.total,
        "num_real": result.real,
        "num_nonword": result.nonword,
        "real_ratio": real_ratio,
        "target_real_ratio": float(target),
        "typo_originals": result.originals,
        "typo_replacements": result.corrupted,
        "typo_techniques": result.techniques,
        "typo_edit_counts": result.edit_counts,
        "typo_is_real": result.real_flags,
    }


def load_source(config: Config):
    """First config.subset_size rows of the source dataset from the Hub."""
    from datasets import load_dataset

    if config.dataset_config_name:
        dataset = load_dataset(config.dataset_name, config.dataset_config_name,
                               split=config.dataset_split)
    else:
        dataset = load_dataset(config.dataset_name, split=config.dataset_split)
    return dataset.select(range(min(config.subset_size, len(dataset))))
