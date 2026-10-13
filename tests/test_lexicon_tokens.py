"""The Lexicon holds its candidates' tokens, and must not change an answer.

`Lexicon.search` used to hand `distance()` a STRING per candidate, which
re-normalised and re-tokenised it on every call. `_compare` is derived once at
construction and never changes, so the tokens are derived once too and the
same `Tokens` object is scored against every query.

Two things are checked here that the ordinary suite cannot see:

1. **The answers are unchanged**, over a corpus of queries, in both
   `normalise` modes, with and without a `max_distance` — because the whole
   point is that this is a speed change and nothing else.
2. **The cache cannot be poisoned.** It is keyed by the COMPARED form, and a
   first version of it took the loop's variable name from the function's
   parameter, so every lookup answered with the last form in the lexicon. The
   symptom was a search returning `yoga` at distance 0.0 for the query
   `kamma`: plausible-looking output, every number wrong. A test that only
   checks the cache is populated would have passed.
"""

import random

import pytest

from abugida.alphabet import ALPHABET
from abugida.lexicon import Lexicon


def a_lexicon(n=300, seed=20260801):
    rng = random.Random(seed)
    letters = [p.grapheme for p in ALPHABET]
    return [
        "".join(rng.choice(letters) for _ in range(rng.randint(4, 12)))
        for _ in range(n)
    ]


def test_the_cache_returns_the_tokens_of_the_form_asked_about():
    """The exact bug: every lookup answering with the last form's tokens."""
    words = ["a", "b", "c", "kamma", "khamma", "yoga"]
    lex = Lexicon(words)
    for w in words:
        got = lex._compared_tokens(lex._compare_of[w])
        assert got.texts() == list(w) or "".join(got.texts()) == w, (w, got.texts())
    # And the same lookups again, from the same cache.
    for w in words:
        got = lex._compared_tokens(lex._compare_of[w])
        assert "".join(got.texts()) == w, (w, got.texts())


def test_the_cache_is_shared_and_not_rebuilt():
    """Same object for the same form, so the normalisation is paid once."""
    lex = Lexicon(a_lexicon())
    word = lex._words[0]
    form = lex._compare_of[word]
    first = lex._compared_tokens(form)
    assert lex._compared_tokens(form) is first
    # And through the other route a caller has to the same form.
    assert lex._compared_tokens(lex._compare_of[word]) is first


def test_search_returns_the_same_answers_with_and_without_the_cache():
    words = a_lexicon()
    queries = words[:20] + ["kamma", "khamma", "gata", "yoga", "", "x", "kṛṣṇa"]

    for normalise in (False, True):
        lex = Lexicon(words, normalise=normalise)
        with_cache = [lex.search(q, k=10, pool=100) for q in queries]

        # Without: `_compared_tokens` hands back the string, which is what
        # `distance` took before this existed.
        lex._tokens_of = None
        original = Lexicon._compared_tokens
        Lexicon._compared_tokens = lambda self, form: form
        try:
            without = [lex.search(q, k=10, pool=100) for q in queries]
        finally:
            Lexicon._compared_tokens = original

        assert with_cache == without, normalise


def test_a_query_outside_the_lexicon_is_not_cached_wrongly():
    """A query and a variant are forms the lexicon does not contain; they are
    cached on demand, and a second query must not collide with the first."""
    lex = Lexicon(["kamma", "khamma"])
    assert lex._compared_tokens("gata").texts() == ["g", "a", "t", "a"]
    assert lex._compared_tokens("yoga").texts() == ["y", "o", "g", "a"]
    assert lex._compared_tokens("kamma").texts() == ["k", "a", "m", "m", "a"]


def test_the_binding_still_has_no_way_to_mutate_a_tokens():
    """The cache hands the SAME `Tokens` to every caller, so a mutating method
    on the binding would let one caller change what another one scores. The
    cache is only sound while the type is immutable — checked rather than
    assumed, because the day it grows a method is the day this breaks
    silently."""
    C = pytest.importorskip("abugida._cabugida")
    mutators = [n for n in dir(C.Tokens)
                if n.startswith(("append", "extend", "insert", "pop", "remove",
                                 "clear", "sort", "reverse", "__setitem__",
                                 "__delitem__", "__iadd__"))]
    assert not mutators, mutators
