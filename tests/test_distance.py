"""The phonological distance: properties, its link to the algebra, and the
contrast with Levenshtein."""

import itertools

import pytest

from abugida.algebra import ELEMENTS
from abugida.distance import (
    algebraic_cost,
    cost,
    distance,
    levenshtein,
    neighbors,
)
from abugida.lexicon import ONE_MOVE
from abugida.phonology import STOPS

#: 20 real words (attested in DPD) covering the whole alphabet.
WORDS = (
    "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
    "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
    "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha",
)


# --- Basic properties ------------------------------------------------------


def test_identity_and_symmetry():
    for w in WORDS:
        assert distance(w, w) == 0.0
    for w, q in itertools.combinations(WORDS[:8], 2):
        assert distance(w, q) == pytest.approx(distance(q, w))
        assert distance(w, q) > 0.0


def test_bounded_by_levenshtein():
    """Substituting costs ≤ 1, so between words whose units are aligned unit
    for unit the phonological distance stays under Levenshtein's count."""
    for w, q in itertools.combinations(WORDS[:10], 2):
        assert distance(w, q) <= levenshtein(w, q) + 1e-9


def test_a_unit_against_two_letters_can_exceed_levenshtein():
    """Not always under it, though: Levenshtein counts LETTERS and the
    distance counts heavy units. tatra~tattha is one Levenshtein edit
    (r -> th), but tth is one long consonant against the two articulations
    t, r, so the distance pays the unit change and a full deletion."""
    assert levenshtein("tatra", "tattha") == 1
    assert distance("tatra", "tattha") == pytest.approx(1.4697, abs=1e-4)


def test_digraphs_are_one_token_in_both():
    """kamma → khamma is ONE edit under both measures (kh = one letter)."""
    assert levenshtein("kamma", "khamma") == 1
    assert distance("kamma", "khamma") <= ONE_MOVE


# --- The link to the algebra -----------------------------------------------


def test_aspirating_balances_voicing():
    """The ρ* of §4 at work: k→kh and k→g cost exactly the same."""
    assert cost("k", "kh") == pytest.approx(cost("k", "g"))


def test_cost_grows_with_algebraic_moves():
    """Within a series, the phonological cost is monotone in the number of
    ⊗ generators separating the values (algebraic_cost)."""
    series = {}
    for p in STOPS:
        (place,) = p.places
        series.setdefault(place, []).append(p)
    for phonemes in series.values():
        for p, q in itertools.combinations(phonemes, 2):
            for p2, q2 in itertools.combinations(phonemes, 2):
                a1 = algebraic_cost(p.value, q.value)
                a2 = algebraic_cost(p2.value, q2.value)
                if a1 < a2:
                    assert cost(p.grapheme, q.grapheme) < cost(
                        p2.grapheme, q2.grapheme
                    ) + 1e-9


def test_algebraic_cost_is_a_group_metric():
    """0 iff equal; each axis contributes at most 1 (because + ⊗ + = −: any
    modifier change is ONE generator application)."""
    for x, y in itertools.product(ELEMENTS, repeat=2):
        d = algebraic_cost(x, y)
        assert (d == 0) == (x == y)
        assert 0 <= d <= 2
        assert d == algebraic_cost(y, x)


# --- What phonology sees and Levenshtein does not --------------------------


def test_levenshtein_is_blind_to_kinship():
    """To Levenshtein, khamma, yamma and samma are all equally far from
    kamma. To phonology they are not — that is the whole point.

    y is tāluja, so it shares the tongue body with k (the dorsal bridge,
    §4) and lands at 0.831 rather than the cap; s is dantaja with no organ
    in common with a guttural, and stays at a flat 1.0."""
    assert (
        levenshtein("kamma", "khamma")
        == levenshtein("kamma", "yamma")
        == levenshtein("kamma", "samma")
        == 1
    )
    assert distance("kamma", "khamma") <= ONE_MOVE
    assert 0.8 < distance("kamma", "yamma") < 1.0
    assert distance("kamma", "samma") == pytest.approx(1.0)


def test_manuscript_variants_are_close():
    """saṅgha ~ saṃgha (assimilated/unassimilated) and vowel length are real
    transmission variants: close phonologically, 1.0 for Levenshtein."""
    assert distance("saṅgha", "saṃgha") < cost("k", "p")
    assert distance("pala", "pāla") < cost("k", "kh")
    assert distance("nibbāna", "nibbana") < cost("k", "kh")


def test_gradient_within_the_series():
    """k→g (1 move) < k→gh (2 moves) < k→p (a different place)."""
    assert cost("k", "g") < cost("k", "gh") < cost("k", "p")


def test_triangle_inequality_of_cost():
    """The truncated angular distance is a metric: exhaustive over 41³
    triples."""
    from abugida.alphabet import ALPHABET

    letters = [p.grapheme for p in ALPHABET]
    for x in letters:
        for y in letters:
            cxy = cost(x, y)
            for z in letters:
                assert cxy <= cost(x, z) + cost(z, y) + 1e-9


def test_triangle_inequality_of_distance():
    """Weighted edit distance inherits the metric (Wagner–Fischer): sampled."""
    sample = WORDS[:8]
    for w in sample:
        for q in sample:
            dwq = distance(w, q)
            for r in sample:
                assert dwq <= distance(w, r) + distance(r, q) + 1e-9


def test_neighbors_sorts_by_phonology():
    result = neighbors("citta", WORDS, k=3)
    assert len(result) == 3
    distances = [d for d, _, _ in result]
    assert distances == sorted(distances)


# --- alignment: the information the scalar aggregates away -----------------


def test_alignment_conserves_the_distance():
    """The edit script's costs sum exactly to the scalar: between the two
    views, no information is lost."""
    from abugida.distance import alignment

    for w, q in itertools.combinations(WORDS, 2):
        ops = alignment(w, q)
        assert sum(c for _, _, _, c in ops) == pytest.approx(distance(w, q))


def test_alignment_identifies_the_edit():
    from abugida.distance import alignment

    edits = [op for op in alignment("kamma", "khamma") if op[0] != "keep"]
    assert edits == [("sub", "k", "kh", pytest.approx(cost("k", "kh")))]
    edits = [op for op in alignment("sutta", "suttā") if op[0] != "keep"]
    assert edits == [("sub", "a", "ā", pytest.approx(cost("a", "ā")))]


def test_alignment_handles_insertions_and_deletions():
    from abugida.distance import alignment

    ops = alignment("gacchati", "gacchanti")
    # nt is one heavy unit: t -> nt, priced as the half that differs (t~n)
    changed = [op for op in ops if op[0] != "keep"]
    assert changed == [("sub", "t", "nt", pytest.approx(cost("t", "n")))]
    ops = alignment("kamma", "kama")
    assert [op[0] for op in ops if op[0] != "keep"] == ["sub"]
    ops = alignment("attha", "atha")
    subs = [op for op in ops if op[0] == "sub"]
    assert subs == [("sub", "tth", "th", pytest.approx(cost("tth", "th")))]


def test_alignment_of_identical_words_is_all_keeps():
    from abugida.distance import alignment

    ops = alignment("dhamma", "dhamma")
    assert all(op[0] == "keep" and op[3] == 0.0 for op in ops)


# --- the 1.0 cap flattens artifact, not signal -----------------------------


def test_the_cap_only_flattens_unrelated_pairs():
    """Measured basis for keeping the truncation (SPEC §9.2): every letter
    pair whose raw angular distance exceeds 1.0 (before the cap) shares NO
    place of articulation — beyond-orthogonal values are an artifact of the
    120° modifier representation, not phonological signal. Raw values reach
    at most ~1.06: a sliver."""
    import math

    from abugida.alphabet import ALPHABET
    from abugida.embed import NEUTRAL_MODIFIER_WEIGHT, cosine, embed
    from abugida.phonology import phoneme

    letters = [p.grapheme for p in ALPHABET]
    capped = 0
    for x, y in itertools.combinations(letters, 2):
        c = cosine(embed(x), embed(y), NEUTRAL_MODIFIER_WEIGHT)
        raw = math.acos(max(-1.0, min(1.0, c))) / (math.pi / 2)
        if raw > 1.0 + 1e-12:
            capped += 1
            assert not (phoneme(x).places & phoneme(y).places), (x, y)
            assert raw < 1.06
    assert capped > 0  # the cap is not vacuous: it does actively flatten


# --- lenient mode: support typos, report them as errors --------------------


def test_lenient_tokenize_absorbs_unknowns():
    from abugida.iast import tokenize

    assert tokenize("qamma", lenient=True) == ["q", "a", "m", "m", "a"]
    assert tokenize("kṛṣṇa", lenient=True) == ["k", "ṛ", "ṣ", "ṇ", "a"]
    with pytest.raises(ValueError):
        tokenize("qamma")  # strict stays strict


def test_lenient_distance_lets_the_rest_discriminate():
    """A typo has no phonology (cost 1, like any unrelated sound), but the
    intact remainder of the word still ranks candidates — the point of
    supporting typos at all."""
    assert distance("qamma", "kamma", lenient=True) == pytest.approx(1.0)
    assert distance("qamma", "kamma", lenient=True) < distance(
        "qamma", "magga", lenient=True
    )
    with pytest.raises(ValueError):
        distance("qamma", "kamma")  # strict stays strict


def test_lenient_identity_and_bound():
    assert distance("axta", "axta", lenient=True) == 0.0
    assert cost("x", "x") == 0.0 and cost("x", "q") == 1.0
    assert distance("qamma", "kamma", lenient=True) <= levenshtein(
        "qamma", "kamma", lenient=True
    )


def test_metric_survives_opaque_tokens():
    """Triangle inequality holds with opaque tokens in the domain."""
    from abugida.alphabet import ALPHABET

    letters = [p.grapheme for p in ALPHABET] + ["x", "q"]
    for x in letters:
        for y in letters:
            cxy = cost(x, y)
            for z in letters:
                assert cxy <= cost(x, z) + cost(z, y) + 1e-9


def test_lenient_alignment_marks_the_typo():
    from abugida.distance import alignment

    edits = [
        op for op in alignment("qamma", "kamma", lenient=True)
        if op[0] != "keep"
    ]
    assert edits == [("sub", "q", "k", 1.0)]


def test_diagnose_reports_and_never_raises():
    from abugida.iast import diagnose

    assert diagnose("dhamma") == []
    assert diagnose("qamma") == [(0, "q", "unknown")]
    assert [(c, k) for _, c, k in diagnose("kṛṣṇa")] == [
        ("ṛ", "sanskrit"),
        ("ṣ", "sanskrit"),
    ]
    assert diagnose("Saṁyutta-Nikāya") == []  # variants and marks are fine


# --- the karaṇa bridges: place adjacency where manuscripts confuse ---------


def test_coronal_bridge_orders_place_changes():
    """t↔ṭ (adjacent tongue-tip places, a real manuscript confusion) is now
    cheaper than k↔p (opposite ends) — the former limitation #1. No fake
    adjacency appears: dental↔labial and palatal↔cerebral stay at full
    place-change cost."""
    assert cost("t", "ṭ") < cost("k", "p")
    assert cost("th", "ṭh") < cost("k", "p")
    assert cost("n", "ṇ") < cost("t", "ṭ")  # nasals share more
    assert cost("l", "ḷ") < cost("n", "ṇ")  # laterals share even more
    assert cost("t", "p") == pytest.approx(cost("k", "p"))
    assert cost("c", "ṭ") == pytest.approx(cost("k", "p"))


def test_dorsal_bridge_orders_place_changes():
    """The mirror of the coronal bridge, one organ up: guttural (jivhāmūla)
    and palatal (jivhāmajjha) share the tongue BODY, so k↔c is cheap for the
    same reason t↔ṭ is. Second most frequent place substitution in DPD's
    var_phonetic (11.4%, after the tip's 73.1%)."""
    assert cost("k", "c") < cost("k", "p")
    assert cost("kh", "ch") < cost("k", "p")
    assert cost("ṅ", "ñ") < cost("k", "c")  # nasals share more, as with n↔ṇ
    assert cost("k", "c") == pytest.approx(cost("t", "ṭ"))  # same √½ split


def test_labial_bridges_to_nothing():
    """Labial is oṭṭhaja — the lower lip, no tongue at all — so it has no
    karaṇa to share and keeps full place-change cost against every other
    place. This is what stops the two bridges from becoming a general
    'adjacency in the tract': guttural is no nearer dental than labial is."""
    full = cost("k", "p")
    for other in ("k", "c", "ṭ", "t"):
        assert cost("p", other) == pytest.approx(full)
    assert cost("k", "t") == pytest.approx(full)  # body vs tip: no bridge
    assert cost("c", "t") == pytest.approx(full)


def test_mass_split_preserves_within_series_costs():
    """The √½/√½ ṭhāna/karaṇa split keeps every place at unit norm, so the
    balance principle holds in ALL series, bridged or not — and ρ* itself
    comes out numerically unchanged when a bridge is added."""
    assert cost("t", "d") == pytest.approx(cost("k", "g"))
    assert cost("t", "th") == pytest.approx(cost("k", "kh"))
    assert cost("ṭ", "ḍ") == pytest.approx(cost("k", "g"))
    assert cost("c", "j") == pytest.approx(cost("k", "g"))
    assert cost("p", "b") == pytest.approx(cost("k", "g"))


# --- epenthetic indel weights (Geiger-attested variation classes) ----------


def test_epenthetic_indel_is_derived_and_bounded():
    """The weight is the extremal solution the metric allows, in (0, 1)."""
    from abugida.distance import EPENTHETIC, INDEL_WEIGHT, _indel

    assert 0.4 < INDEL_WEIGHT < 0.8
    assert _indel("a") == INDEL_WEIGHT and _indel("ṃ") == INDEL_WEIGHT
    assert _indel("k") == 1.0 and _indel("q") == 1.0  # opaque = full price
    # a heavy unit: the cheapest route through a single token, never more
    # than deleting its two letters one by one
    assert 1.0 < _indel("tt") < 2.0
    assert EPENTHETIC == frozenset("aāiīuūeo") | {"y", "v", "ṃ"}


def test_geiger_doublet_classes_are_cheap():
    """The attested variation: svarabhakti, aphaeresis, prothesis, final ṃ."""
    from abugida.distance import INDEL_WEIGHT

    for a, b in [("sve", "suve"), ("idāni", "dāni"),
                 ("uṭṭhita", "vuṭṭhita"), ("sakiṃ", "saki")]:
        assert distance(a, b) == pytest.approx(INDEL_WEIGHT)
    # degemination is not an indel at all: geminates collapse to LONG
    # consonants, so attha↔atha is a substitution on the LENGTH dimension —
    # one elementary move, like a↔ā in kind and like k↔kh in cost
    assert distance("attha", "atha") == pytest.approx(cost("tt", "t"))
    assert distance("attha", "atha") <= ONE_MOVE + 1e-9


def test_metric_conditions_on_extended_alphabet():
    """Triangle on Σ ∪ {ε} for every SEQUENCE token — letters, Sanskrit
    phonemes, opaque characters AND the heavy units, which since the
    one-segmentation design are tokens of the sequence like any other:
    |indel(x)−indel(y)| ≤ cost(x,y) and cost(x,y) ≤ indel(x)+indel(y).
    With the cost triangle below, these are the conditions under which edit
    distance over one sequence per word is a metric (Wagner–Fischer)."""
    from abugida._pure import _UNITS
    from abugida.alphabet import ALPHABET
    from abugida.distance import _indel
    from abugida.phonology import FOREIGN

    letters = ([p.grapheme for p in ALPHABET] + list(FOREIGN) + ["x", "q"]
               + sorted(_UNITS))
    for x in letters:
        for y in letters:
            c = cost(x, y)
            assert abs(_indel(x) - _indel(y)) <= c + 1e-9 or x == y
            assert c <= _indel(x) + _indel(y) + 1e-9


def test_cost_triangle_includes_geminate_tokens():
    """The substitution metric's triangle holds over every token: letters,
    Sanskrit phonemes and all heavy units (geminates and nasal+stop
    clusters), 126 tokens, exhaustively."""
    from abugida._pure import _UNITS
    from abugida.alphabet import ALPHABET
    from abugida.phonology import FOREIGN

    letters = ([p.grapheme for p in ALPHABET] + list(FOREIGN)
               + sorted(_UNITS))
    for x in letters:
        for y in letters:
            cxy = cost(x, y)
            for z in letters:
                assert cxy <= cost(x, z) + cost(z, y) + 1e-9


def test_triangle_inequality_with_indels_word_level():
    """Word-level triangle re-verified under the new indel weights,
    including words of different lengths (where indels bind)."""
    words = ("sve", "suve", "sotthi", "suvatthi", "idāni", "dāni",
             "sakiṃ", "saki", "kamma", "upekkhā")
    for a in words:
        for b in words:
            dab = distance(a, b)
            for c in words:
                assert dab <= distance(a, c) + distance(c, b) + 1e-9


# --- foreign Sanskrit phonemes in lenient mode -----------------------------


def test_foreign_sibilants_have_phonology():
    """ś/ṣ price by geometry, not as opaque typos; ṣ→s is cheaper (shares
    the coronal bridge). Strict mode still rejects them."""
    assert cost("ṣ", "s") < cost("ś", "s") < 1.0
    assert cost("ṛ", "a") < 1.0
    assert distance("śānti", "santi", lenient=True) == pytest.approx(
        cost("ś", "s") + cost("a", "ā")
    )
    with pytest.raises(ValueError):
        distance("śānti", "santi")  # strict unchanged


def test_foreign_stays_out_of_the_inventory():
    from abugida import is_possible, tokenize
    from abugida.phonology import FOREIGN, INVENTORY

    assert not any(p.grapheme in FOREIGN for p in INVENTORY)
    assert not is_possible("śānti")
    with pytest.raises(ValueError):
        tokenize("ṛju")


# --- geminates as consonant length -----------------------------------------


def test_gemination_is_one_elementary_move():
    """A doubled consonant is ONE heavy unit of the word: degemination prices
    on the weight coordinate (the LENGTH dimension) — like vowel length in
    kind, like one algebra move in cost — instead of as a full-price
    deletion, and a geminate counts once against another."""
    assert cost("tt", "t") == pytest.approx(cost("k", "kh"), abs=1e-3)
    assert distance("attha", "atha") == pytest.approx(cost("tth", "th"))
    assert distance("attha", "atha") < distance("attha", "akkha")
    assert distance("kamma", "kama") < 0.5
    # unit against unit: the halves differ by k~g, and that is the price
    assert distance("magga", "makka") == pytest.approx(cost("gg", "kk"))
    assert cost("gg", "kk") == pytest.approx(cost("g", "k"))


def test_geminate_against_cluster_is_the_half_that_differs():
    """The battery caught an earlier collapse-based design breaking
    geminate-vs-cluster words; with the cluster a unit too, the two units
    differ only in their first half."""
    assert distance("citta", "cinta") == pytest.approx(cost("t", "n"))
    assert distance("puñña", "puñja") == pytest.approx(cost("ñ", "j"))
    assert distance("citta", "cinta") < distance("citta", "cimta")


# --- EXPERIMENTAL: the componentwise weighted alternative ------------------


class TestWeightedCost:
    """`weighted_cost` (EXPERIMENTAL): Σ wᵢ|xᵢ−yᵢ| instead of an angle.

    A metric, calibratable by the same balance principle, and measurably
    worse than the angular cost. Pinned so the comparison stays checkable.
    See `distance.weighted_cost`.
    """

    def test_it_is_a_metric(self):
        from abugida.alphabet import ALPHABET
        from abugida.distance import weighted_cost as wc

        letters = [p.grapheme for p in ALPHABET]
        for x in letters:
            assert wc(x, x) == 0.0
            for y in letters:
                assert wc(x, y) == pytest.approx(wc(y, x))
                assert 0.0 <= wc(x, y) <= 1.0
        for x in letters:
            for y in letters:
                wxy = wc(x, y)
                for z in letters:
                    assert wxy <= wc(x, z) + wc(z, y) + 1e-9

    def test_the_balance_principle_transfers(self):
        """L1_MODIFIER_WEIGHT is derived exactly as ρ* is, and works: the
        elementary moves cost the same. Calibration is not the objection."""
        from abugida.distance import L1_MODIFIER_WEIGHT
        from abugida.distance import weighted_cost as wc

        assert wc("k", "kh") == pytest.approx(wc("k", "g"))
        assert 0.0 < L1_MODIFIER_WEIGHT < 1.0

    def test_asymmetric_weights_are_not_a_metric(self):
        """The general Σ|xᵢcᵢ − yᵢdᵢ| with c ≠ d is not a candidate at all:
        it loses both symmetry and identity. Only c = d survives."""
        from abugida.embed import DIM, embed

        c = [1.0] * DIM
        c[5] = 2.0  # voicing weighted differently on one side
        d = [1.0] * DIM
        asym = lambda x, y: sum(  # noqa: E731
            abs(embed(x)[i] * c[i] - embed(y)[i] * d[i]) for i in range(DIM)
        )
        assert asym("g", "g") != 0.0  # identity fails
        assert asym("k", "g") != asym("g", "k")  # symmetry fails

    def test_it_ties_where_the_angular_cost_separates(self):
        """The diagnosis for its weaker battery score: an L1 sum cannot see
        that the same displacement means more for a lightly specified
        segment. Vowel length, aspiration and voicing all collapse together;
        the angle keeps them apart."""
        from abugida.distance import weighted_cost as wc

        assert wc("a", "ā") == pytest.approx(wc("k", "kh"))
        assert wc("a", "ā") == pytest.approx(wc("k", "g"))
        assert cost("a", "ā") != pytest.approx(cost("k", "kh"))

    def test_it_almost_never_saturates_against_the_indel(self):
        """Its scale sits far lower against the indels. Normalising by the
        inventory maximum puts a few pairs at 1.0 by construction, but the
        cap is reached by 0.4% of letter pairs against the angular cost's
        22.8%, so delete+insert is almost never competitive and the DP loses
        in practice a degree of freedom the angular version keeps."""
        from abugida.alphabet import ALPHABET
        from abugida.distance import weighted_cost as wc

        pairs = list(itertools.combinations([p.grapheme for p in ALPHABET], 2))
        capped = lambda f: sum(1 for x, y in pairs if f(x, y) >= 0.9999)  # noqa
        assert capped(wc) / len(pairs) < 0.01
        assert capped(cost) / len(pairs) > 0.20
