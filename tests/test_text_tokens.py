"""Tokenisation has to work in every language the product is sold in.

An ASCII-only pattern here does not fail loudly — it produces zero tokens, so
semantic memory quietly stops recalling anything a Russian- or Uzbek-speaking
user ever told it. These tests exist so that cannot come back.
"""

from __future__ import annotations

from jarvis.memory.embeddings import HashingEmbedder
from jarvis.utils.text import tokenize_words


def test_russian_is_tokenised():
    assert tokenize_words("Я живу в Ташкенте!") == ["я", "живу", "в",
                                                    "ташкенте"]


def test_uzbek_keeps_its_apostrophe():
    assert tokenize_words("O'zbekiston poytaxti") == ["o'zbekiston",
                                                      "poytaxti"]


def test_english_and_digits_still_work():
    assert tokenize_words("I don't know 42 things") == ["i", "don't", "know",
                                                        "42", "things"]


def test_punctuation_and_underscores_separate_words():
    assert tokenize_words("KER — привет_мир") == ["ker", "привет", "мир"]


def test_a_russian_sentence_produces_a_real_embedding():
    """A zero vector cannot match anything, which is how the bug showed up."""
    vector = HashingEmbedder(dimensions=64).embed("Меня зовут Сержод")
    assert any(value != 0.0 for value in vector)


def test_russian_texts_that_share_words_are_close():
    embedder = HashingEmbedder(dimensions=256)
    from jarvis.memory.embeddings import cosine_similarity
    a = embedder.embed("Я живу в Ташкенте")
    b = embedder.embed("Где я живу")
    c = embedder.embed("Совершенно другая тема")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)
