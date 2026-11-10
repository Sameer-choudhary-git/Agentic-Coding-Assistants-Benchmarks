"""Basic text statistics."""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple

_WORD = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> List[str]:
    """Lower-case ``text`` and return its words.

    A word is a maximal run of ASCII letters, digits or apostrophes. Everything else
    (spaces, punctuation, hyphens) separates words. Leading/trailing apostrophes are stripped
    from each word and words that become empty are dropped.
    """
    words = []
    for raw in _WORD.findall(text.lower()):
        word = raw.strip("'")
        if word:
            words.append(word)
    return words


def word_count(text: str) -> int:
    """Return the number of words in ``text`` (0 for empty or whitespace-only text)."""
    return len(tokenize(text))


def top_words(text: str, n: int) -> List[Tuple[str, int]]:
    """Return the ``n`` most frequent words as ``(word, count)`` pairs.

    Sorted by count descending, then alphabetically. ``n`` must be >= 1 (``ValueError``
    otherwise). If there are fewer than ``n`` distinct words, all of them are returned.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    counts = Counter(tokenize(text))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:n]


def average_word_length(text: str) -> float:
    """Return the mean word length rounded to 2 decimals; 0.0 when there are no words."""
    words = tokenize(text)
    if not words:
        return 0.0
    return round(sum(len(w) for w in words) / len(words), 2)
