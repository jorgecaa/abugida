"""The integration adapter: search and variant generation, no algebra
knowledge required, no input ever raises."""

import pytest

from abugida.distance import INDEL_WEIGHT, cost
from abugida.iast import tokenize
from abugida.lexicon import ONE_MOVE, Lexicon, edit_tag

WORDS = [
    "kamma", "khamma", "dhamma", "dhammā", "pala", "pāla", "attha",
    "atha", "saṅgha", "saṃgha", "buddha", "yoga", "sīha", "citta",
]


@pytest.fixture(scope="module")
def lex():
    return Lexicon(WORDS)


def test_prepares_and_deduplicates(lex):
    assert len(lex) == len(WORDS)
    assert "kamma" in lex
    assert "Kamma" in lex  # normalisation applies to membership too
    assert "missing" not in lex
    assert len(Lexicon(["saṁgha", "saṃgha"])) == 1  # variant spellings merge


def test_search_ranks_phonologically(lex):
    top = lex.search("kamma", k=3)
    assert top[0][1] == "khamma"  # aspiration: the cheapest edit around
    assert top[0][0] == pytest.approx(cost("k", "kh"))


def test_search_never_raises(lex):
    """Typos, Sanskrit, garbage, empty — all handled, none raise."""
    # a typo query: the intact remainder discriminates (qīha → sīha)
    assert lex.search("qīha")[0][1] == "sīha"
    # an undiscriminating typo ties at 1.0 — a typo has no phonology
    assert lex.search("qamma")[0][0] == pytest.approx(1.0)
    assert lex.search("śaṅgha")  # Sanskrit sibilant: priced, not rejected
    assert lex.search("") == []
    assert lex.search("   ") == []


def test_max_distance_drops_noise(lex):
    """Pure-noise queries return nothing under a threshold, instead of
    far junk at distance 4."""
    assert lex.search("!!??", max_distance=1.5) == []
    assert lex.search("kamm", max_distance=1.5)  # near-miss still answers


def test_one_move_is_the_derived_anchor():
    """theta's default is the costliest single attested-variation move —
    a maximum over the elementary moves, not a hand-picked number.

    Which move is dearest is a fact about the calibration, not a definition:
    a trial re-warp of `cost` (since reverted) made it a single algebra move
    rather than the epenthetic indel. What the definition guarantees, and
    what this pins, is that NO elementary move ever falls outside the
    default theta — the property an alias silently lost."""
    for move in (INDEL_WEIGHT, cost("k", "kh"), cost("k", "g"),
                 cost("tt", "t"), cost("a", "ā")):
        assert move <= ONE_MOVE + 1e-12
    assert ONE_MOVE == max(INDEL_WEIGHT, cost("k", "kh"),
                           cost("tt", "t"), cost("a", "ā"))
    assert 0.4 < ONE_MOVE < 0.7


def test_variants_finds_the_attested_pairs(lex):
    pairs = {(a, b): (d, tag) for a, b, d, tag in lex.variants()}
    assert ("kamma", "khamma") in pairs  # one algebra move, 0.470
    assert ("atha", "attha") in pairs  # degemination, 0.470
    assert ("pala", "pāla") in pairs  # vowel length, 0.333
    assert ("dhamma", "dhammā") in pairs
    # unrelated words do not pair
    assert not any("yoga" in p or "sīha" in p for p in pairs)


def test_variants_yields_each_pair_once(lex):
    seen = [(a, b) for a, b, _, _ in lex.variants()]
    assert len(seen) == len(set(seen))
    assert all(a < b for a, b in seen)


def test_edit_tags_label_the_connection(lex):
    tags = {(a, b): tag for a, b, _, tag in lex.variants()}
    assert tags[("kamma", "khamma")] == "k↔kh"
    assert tags[("pala", "pāla")] == "a↔ā"
    assert tags[("atha", "attha")] == "th↔tth"  # degemination, one heavy unit
    assert edit_tag("idāni", "dāni") == "−i"
    assert edit_tag("sve", "suve") == "+u"
    assert edit_tag("kamma", "kamma") == ""


def test_variants_respects_theta(lex):
    strict = set(lex.variants(theta=0.35))
    broad = set(lex.variants(theta=1.0))
    assert strict < broad
    assert all(d <= 0.35 + 1e-9 for _, _, d, _ in strict)
    # saṅgha~saṃgha (0.755) appears only above the one-move anchor
    assert not any({a, b} == {"saṃgha", "saṅgha"}
                   for a, b, _, _ in lex.variants())
    assert any({a, b} == {"saṃgha", "saṅgha"}
               for a, b, _, _ in lex.variants(theta=0.8))


def test_variants_left_side_restriction(lex):
    only = list(lex.variants(words=["kamma"]))
    assert only and all(a == "kamma" or b == "kamma" for a, b, _, _ in only)


# --- construction as a second criterion ------------------------------------


def test_construction_key_parses_the_dpd_shape():
    """Derivation chains keep their LAST link (the realised form), roots and
    affix markers are stripped, and the result is sorted — which is what
    makes it a multiset, so compound permutation keys the same as identical
    construction."""
    from abugida.lexicon import construction_key as key

    assert key("ati > aty > acc + √i > ay + *a + *ika") == (
        "*a", "*ika", "acc", "ay"
    )
    assert key("adanta + agutta + sutta") == ("adanta", "agutta", "sutta")
    assert key("sutta + adanta + agutta") == key("adanta + agutta + sutta")
    assert key("x + y\nz + w") == ("x", "y")  # only the first line


def test_construction_key_refuses_to_be_coarse():
    """Below two constituents the key groups thousands of lemmas (a single
    shared root: 979 candidates per lemma, measured) so it returns None."""
    from abugida.lexicon import construction_key as key

    assert key("") is None
    assert key(None) is None
    assert key("√gam") is None
    assert key("na > a") is None


def test_variants_uses_construction_to_reach_what_distance_cannot():
    """The measured win of Phase 1: pairs with the same formation but
    spellings too far apart for any usable θ. agamā~agā is 1.63, four times
    ONE_MOVE, and no threshold that admits it would be usable."""
    lex = Lexicon(["agamā", "agā", "kamma", "khamma"])
    cons = {"agamā": "a + √gam + ā", "agā": "a + √gam + ā"}

    plain = {(a, b) for a, b, _, _ in lex.variants()}
    assert ("agamā", "agā") not in plain

    withc = {(a, b): tag for a, b, _, tag in lex.variants(constructions=cons)}
    assert withc[("agamā", "agā")] == "=construction"
    assert withc[("kamma", "khamma")] == "k↔kh"  # metric pairs still tagged


def test_construction_pairs_are_not_yielded_twice():
    """A pair inside theta AND sharing a construction is yielded once, by the
    metric, keeping its informative edit tag."""
    lex = Lexicon(["kamma", "khamma"])
    cons = {"kamma": "√kar + ma", "khamma": "√kar + ma"}
    rows = list(lex.variants(constructions=cons))
    assert len(rows) == 1
    assert rows[0][3] == "k↔kh"


# --- normalise=True: the pipeline as a Lexicon setting ---------------------


def test_phonological_form_is_the_pipeline():
    from abugida.lexicon import phonological_form as pf

    assert pf("saṃgha") == "saṅgha"          # sandhi resolved
    assert pf("abhibhavati") == "abhibhoti"   # ava → o
    assert pf("kamma") == "kamma"             # nothing to do


def test_normalise_finds_pairs_the_raw_metric_misses():
    """saṃgha ~ saṅgha is 0.740 raw — above ONE_MOVE, so `variants` loses it.
    Through the pipeline the two are the same string."""
    words = ["saṃgha", "saṅgha", "kamma"]
    assert ("saṃgha", "saṅgha") not in {
        (a, b) for a, b, _, _ in Lexicon(words).variants()
    }
    piped = {(a, b): d for a, b, d, _ in
             Lexicon(words, normalise=True).variants()}
    assert piped[("saṃgha", "saṅgha")] == pytest.approx(0.0)


def test_normalise_returns_the_lexicon_s_own_words():
    """Measurement only. `contract_word` maps 533 distinct DPD lemma pairs
    onto identical strings, so normalising the stored words would merge
    entries the caller still needs apart."""
    lex = Lexicon(["abhibhavati", "abhibhoti"], normalise=True)
    assert lex._words == ["abhibhavati", "abhibhoti"]
    assert "abhibhavati" in lex
    found = {w for _, w in lex.search("abhibhavati", k=5)}
    assert found == {"abhibhoti"}


def test_normalise_off_by_default():
    """It changes numbers a caller may depend on, so it must be asked for."""
    words = ["saṃgha", "saṅgha"]
    assert Lexicon(words).search("saṃgha")[0][0] > 0.5
    assert Lexicon(words, normalise=True).search("saṃgha")[0][0] == 0.0


@pytest.fixture(params=["rapidfuzz", "fallback"])
def prefilter(request, monkeypatch):
    """Run a test on BOTH prefilters. The BK-tree fallback is only reached
    without rapidfuzz, so on a machine that has it the fallback went
    untested, and lost every pair whose compared forms are identical
    (fixed 2026-10-13)."""
    import abugida.lexicon as lexicon
    if request.param == "rapidfuzz" and not lexicon._HAVE_RAPIDFUZZ:
        pytest.skip("rapidfuzz not installed")
    if request.param == "fallback":
        monkeypatch.setattr(lexicon, "_HAVE_RAPIDFUZZ", False)
    return request.param


def test_normalise_pairs_survive_either_prefilter(prefilter):
    """saṃgha and saṅgha share one compared form; the prefilter must still
    hand the partner to the scorer."""
    lex = Lexicon(["saṃgha", "saṅgha", "kata"], normalise=True)
    assert lex.search("saṃgha", k=1) == [(0.0, "saṅgha")]
    pairs = {(a, b): d for a, b, d, _ in lex.variants()}
    assert pairs[("saṃgha", "saṅgha")] == pytest.approx(0.0)


def test_search_never_returns_the_query_itself(prefilter):
    """`search` drops the query word, by word and not by compared form."""
    lex = Lexicon(WORDS, normalise=True)
    for w in WORDS:
        assert w not in {c for _, c in lex.search(w, k=len(WORDS))}


# --- relative threshold: a budget that scales with the word ----------------


def test_relative_threshold_reaches_long_words():
    """A fixed budget is progressively stricter on long words: three cheap
    vowel alternations in a compound cost as much as three in a short word,
    but mean far less. The relative cut-off scales with length."""
    words = ["parisuddhasilakkhandha", "parisuddhasīlakkhandhā", "kata"]
    lex = Lexicon(words, normalise=True)
    pair = ("parisuddhasilakkhandha", "parisuddhasīlakkhandhā")

    strict = {(a, b) for a, b, _, _ in lex.variants(theta=0.5)}
    assert pair not in strict          # 0.67 raw: over a tight absolute θ
    loose = {(a, b) for a, b, _, _ in lex.variants(theta=0.5, relative=True)}
    assert pair in loose               # 0.67/22 tokens: comfortably inside


def test_relative_theta_defaults_from_the_caller_s_lexicon():
    """No constant is picked here: the default is ONE_MOVE divided by the
    median length of the words the caller actually supplied."""
    lex = Lexicon(["kata", "gata", "kamma", "khamma"])
    lengths = sorted(len(tokenize(w)) for w in
                     ["kata", "gata", "kamma", "khamma"])
    assert lex.median_length() == lengths[len(lengths) // 2]
    assert list(lex.variants(relative=True))  # usable, not degenerate


def test_relative_mode_does_not_break_early():
    """`search` is sorted by distance, but distance/length is not monotone in
    it, so the absolute mode's early `break` would silently drop pairs."""
    lex = Lexicon(["kata", "gata", "katakatavihara", "katakatavihāra"],
                  normalise=True)
    got = {(a, b) for a, b, _, _ in lex.variants(theta=0.1, relative=True)}
    assert ("katakatavihara", "katakatavihāra") in got


def test_the_ratio_is_not_a_metric_and_distance_still_is():
    """Why the ratio lives in `variants` and not in `distance`: dividing by a
    function of the arguments breaks the triangle inequality (measured: 6
    violations in 314,432 triples). `distance` keeps the guarantee."""
    from abugida import distance

    ratio = lambda a, b: distance(a, b) / max(  # noqa: E731
        len(tokenize(a)), len(tokenize(b)))
    x, y, z = "khāma", "kata", "kamma"
    assert ratio(x, y) > ratio(x, z) + ratio(z, y)
    assert distance(x, y) <= distance(x, z) + distance(z, y) + 1e-9


def test_variants_restricted_to_words_yields_both_directions():
    """REGRESSION. Pairs are emitted once, ordered (a < b). On a full sweep
    `w < c` is enough because the pair is reached from the other side too;
    under `words=` it is not — the partner may never be visited — and half
    the pairs vanished silently. Caught by asking why a documented recipe
    scored 47% where the measurement said 96%."""
    lex = Lexicon(["kata", "gata", "kamma"], normalise=True)
    restricted = {(a, b) for a, b, _, _ in
                  lex.variants(words=["kata"], theta=1.0)}
    assert restricted == {("gata", "kata"), ("kamma", "kata")}
    # and the full sweep is unchanged, still one row per pair
    full = [(a, b) for a, b, _, _ in lex.variants(theta=1.0)]
    assert len(full) == len(set(full))
    assert set(full) == restricted


def test_normalise_never_raises_on_foreign_input():
    """REGRESSION. `Lexicon`'s contract is that no input raises, and
    `phonological_form` tokenises strictly — one Sanskrit headword made the
    constructor throw."""
    lex = Lexicon(["kata", "kṛṣṇa", "gata"], normalise=True)
    assert len(lex) == 3
    assert lex.search("kata", k=2)[0][1] == "gata"
    from abugida.lexicon import phonological_form
    assert phonological_form("kṛṣṇa") == "kṛṣṇa"  # passed through
