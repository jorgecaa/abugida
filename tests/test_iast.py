"""The IAST layer: tokenisation, Unicode normalisation, rejection of
non-Pāli."""

import unicodedata

import pytest

from abugida.embed import DIM
from abugida.iast import normalize, tokenize, transcribe, vectors


# --- Longest match: digraphs are not split --------------------------------


@pytest.mark.parametrize(
    "word,expected",
    [
        ("saṅgha", ["s", "a", "ṅ", "gh", "a"]),
        ("buddha", ["b", "u", "d", "dh", "a"]),
        ("dhamma", ["dh", "a", "m", "m", "a"]),
        ("sañjāta", ["s", "a", "ñ", "j", "ā", "t", "a"]),
        ("taṇhā", ["t", "a", "ṇ", "h", "ā"]),
        ("saṃyutta", ["s", "a", "ṃ", "y", "u", "t", "t", "a"]),
        ("kaṇṭha", ["k", "a", "ṇ", "ṭh", "a"]),
    ],
)
def test_tokenize(word, expected):
    assert tokenize(word) == expected


def test_lh_is_a_cluster_not_a_digraph():
    """ruḷha: the traditional 41-sound alphabet analyses ḷh as ḷ + h."""
    assert tokenize("ruḷha") == ["r", "u", "ḷ", "h", "a"]


# --- Unicode ---------------------------------------------------------------


def test_normalize_nfd():
    """The decomposed niggahīta (m + U+0323) is the same as the composed
    one."""
    decomposed = unicodedata.normalize("NFD", "saṃyutta")
    assert decomposed != "saṃyutta"  # they really are different bytes
    assert tokenize(decomposed) == tokenize("saṃyutta")


def test_niggahita_variant():
    """ṁ (U+1E41) is accepted and canonicalised to ṃ."""
    assert normalize("evaṁ") == "evaṃ"
    assert tokenize("saṁyutta") == tokenize("saṃyutta")


def test_uppercase_and_editorial_marks():
    assert tokenize("Buddha") == tokenize("buddha")
    assert tokenize("tass'eva") == tokenize("tasseva")
    assert tokenize("dhamma-cakka") == tokenize("dhammacakka")


def test_normalize_is_idempotent():
    word = unicodedata.normalize("NFD", "Saṁyutta-Nikāya")
    assert normalize(normalize(word)) == normalize(word)


# --- Rejecting what is not Pāli --------------------------------------------


def test_rejects_sanskrit_iast():
    with pytest.raises(ValueError, match="Sanskrit"):
        tokenize("kṛṣṇa")


def test_rejects_foreign_characters():
    with pytest.raises(ValueError, match="not a Pāli grapheme"):
        tokenize("dharma!")  # the mark, not the r: dharma tokenises fine


def test_dharma_does_tokenize():
    """dharma is phonotactically odd for Pāli but graphemically valid: the
    tokeniser validates graphemes, not phonotactics."""
    assert tokenize("dharma") == ["dh", "a", "r", "m", "a"]


# --- Transcription and vectors ---------------------------------------------


def test_transcribe_yields_inventory_phonemes():
    phonemes = transcribe("saṅgha")
    assert [p.grapheme for p in phonemes] == ["s", "a", "ṅ", "gh", "a"]
    assert phonemes[2].value is not None  # ṅ is in A


def test_word_vectors():
    vs = vectors("buddha")
    assert len(vs) == 5
    assert all(len(v) == DIM for v in vs)
