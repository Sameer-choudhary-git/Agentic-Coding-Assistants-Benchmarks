import pytest

from textstats.stats import average_word_length, tokenize, top_words, word_count


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert tokenize("Hello, World! well-known") == ["hello", "world", "well", "known"]


def test_tokenize_strips_outer_apostrophes():
    assert tokenize("'quoted' don't ''") == ["quoted", "don't"]


def test_word_count_empty_and_whitespace():
    assert word_count("") == 0
    assert word_count("   \n\t") == 0
    assert word_count("one two  three") == 3


def test_top_words_counts_and_ties():
    text = "b a c a b d"
    assert top_words(text, 2) == [("a", 2), ("b", 2)]
    assert top_words(text, 4) == [("a", 2), ("b", 2), ("c", 1), ("d", 1)]


def test_top_words_case_insensitive():
    assert top_words("Apple apple APPLE pear", 1) == [("apple", 3)]


def test_top_words_fewer_than_n():
    assert top_words("x y", 5) == [("x", 1), ("y", 1)]
    assert top_words("", 3) == []


@pytest.mark.parametrize("n", [0, -2])
def test_top_words_invalid_n(n):
    with pytest.raises(ValueError):
        top_words("a b", n)


def test_top_words_exact_n():
    assert len(top_words("a b c d", 3)) == 3


def test_average_word_length():
    assert average_word_length("") == 0.0
    assert average_word_length("ab abc") == 2.5
    assert average_word_length("a bb bb") == 1.67
