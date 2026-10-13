"""The entry point: it must be correct on its own, and it must DEFEND itself.

`Lexicon` is deliberately permissive — lenient tokenisation baked in so a
search box cannot crash. That is wrong for a lexicon, where a Sanskrit
headword or a stray `*` would be indexed and compared in silence. These tests
pin the stricter contract.
"""

import pytest

from abugida import Comparator
from abugida.comparator import RECALL_SETTINGS


def test_it_indexes_pali_and_refuses_the_rest():
    cmp = Comparator(["kata", "gata", "kṛṣṇa", "qam*", ""])
    assert len(cmp) == 2
    assert set(cmp.rejected) == {"kṛṣṇa", "qam*"}
    assert "sanskrit" in cmp.rejected["kṛṣṇa"]
    assert "unknown" in cmp.rejected["qam*"]


def test_rejection_says_which_characters():
    """A refusal that does not say why is a bug report waiting to happen."""
    cmp = Comparator(["kṛṣṇa"])
    reason = cmp.rejected["kṛṣṇa"]
    assert "ṛ" in reason and "ṣ" in reason


def test_normalisation_still_applies_to_accepted_input():
    """Case and Unicode form are normalised, not rejected — they are not
    errors, they are spelling."""
    cmp = Comparator(["Dhamma", "dhammā"])
    assert len(cmp) == 2
    assert "dhamma" in cmp


def test_queries_are_validated_loudly():
    """A typo scored as an opaque token returns plausible nonsense, which is
    worse than an error."""
    cmp = Comparator(["kata", "gata"])
    with pytest.raises(ValueError, match="not Pāli"):
        cmp.neighbours("qam*")
    with pytest.raises(ValueError, match="not Pāli"):
        list(cmp.variants(words=["kṛṣṇa"]))


def test_the_pipeline_is_on_by_default():
    """saṃgha ~ saṅgha is 0.740 raw — outside any sane absolute threshold.
    Normalisation is part of the entry point, so it comes back at 0.0."""
    cmp = Comparator(["saṃgha", "saṅgha", "kata"])
    pairs = {(a, b): d for a, b, d, _ in cmp.variants()}
    assert pairs[("saṃgha", "saṅgha")] == pytest.approx(0.0)


def test_variants_restricted_still_returns_both_directions():
    """The regression that made the documented recipe score 47%."""
    cmp = Comparator(["kata", "gata", "kamma"])
    got = {(a, b) for a, b, _, _ in cmp.variants(words=["kata"])}
    assert ("gata", "kata") in got


def test_recall_settings_are_named_not_numeric():
    """Thresholds are not comparable across modes, so the entry point does
    not take one."""
    assert set(RECALL_SETTINGS) == {"precise", "balanced", "exhaustive"}
    assert (RECALL_SETTINGS["precise"] < RECALL_SETTINGS["balanced"]
            < RECALL_SETTINGS["exhaustive"])
    with pytest.raises(ValueError, match="recall must be one of"):
        Comparator(["kata"], recall="maximum")


def test_looser_recall_yields_at_least_as_much():
    words = ["kata", "gata", "kamma", "khamma", "kāta", "gāta", "kattha"]
    counts = [len(list(Comparator(words, recall=r).variants()))
              for r in ("precise", "balanced", "exhaustive")]
    assert counts == sorted(counts)


def test_constructions_reach_what_distance_cannot():
    cmp = Comparator(["agamā", "agā", "kata"],
                     constructions={"agamā": "a + √gam + ā",
                                    "agā": "a + √gam + ā"})
    tags = {(a, b): t for a, b, _, t in cmp.variants()}
    assert tags[("agamā", "agā")] == "=construction"


# --- Sanskritised Pāli, and the ways out -----------------------------------


def test_sanskritised_pali_is_indexed_not_rejected():
    """`tatra` beside `tattha`, `atra` beside `attha` are real DPD lemmas,
    not encoding errors: every grapheme is Pāli, so the gate passes them."""
    cmp = Comparator(["tatra", "tattha", "atra", "attha", "sarva", "sabba"])
    assert len(cmp) == 6
    assert cmp.rejected == {}


def test_sanskrit_correspondences_need_the_loose_setting():
    """Documented limitation, pinned so it cannot drift. tr→tth is SYSTEMATIC
    sound change and edit distance assumes independent edits. With heavy
    units it is further than it was: tth is one unit and the r of tr is
    deleted whole (tatra~tattha 1.470, it was 0.831), so no setting reaches
    it. Closing it would need a transducer of the sound laws: historical
    grammar, not distance between sounds, and out of scope."""
    words = ["tatra", "tattha"]
    assert not list(Comparator(words, recall="exhaustive").variants())


def test_sanskrit_graphemes_need_asking_for():
    """ś ṣ ṛ are refused by default — in a Pāli lexicon they are far more
    often an encoding mistake than a decision — but they are one flag away,
    because they carry real phonology in the comparison."""
    strict = Comparator(["kata", "kṛṣṇa"])
    assert "kṛṣṇa" in strict.rejected

    wide = Comparator(["kata", "kṛṣṇa"], accept="pali+sanskrit")
    assert wide.rejected == {}
    assert len(wide) == 2


def test_widening_the_gate_does_not_open_it():
    """`pali+sanskrit` admits three graphemes, not arbitrary input."""
    cmp = Comparator(["kata", "kṛṣṇa", "qam*", "ka∂a"],
                     accept="pali+sanskrit")
    assert set(cmp.rejected) == {"qam*", "ka∂a"}
    with pytest.raises(ValueError, match="accept must be one of"):
        Comparator(["kata"], accept="anything")


def test_lenient_queries_are_the_search_box_escape_hatch():
    """Strict by default because silent nonsense is worse than an error, but
    a search box needs a best effort."""
    cmp = Comparator(["kata", "gata"])
    with pytest.raises(ValueError, match="lenient=True"):
        cmp.neighbours("qam*")
    got = cmp.neighbours("qam*", k=1, lenient=True)
    assert got and got[0][1] in {"kata", "gata"}


def test_the_layer_below_is_reachable():
    """The class is narrow on purpose, not a wall: `.lexicon` is the
    documented way out for anything it does not allow."""
    cmp = Comparator(["kata", "gata"])
    from abugida import Lexicon

    assert isinstance(cmp.lexicon, Lexicon)
    assert cmp.lexicon.search("kata", k=1)[0][1] == "gata"


def test_recall_can_be_overridden_per_call():
    """The index does not depend on the recall setting — only a threshold
    does — so comparing settings must not require rebuilding. A caller
    benchmarking three settings on a 75k lexicon should build once."""
    words = ["kata", "gata", "kamma", "khamma", "kāta", "kattha"]
    cmp = Comparator(words, recall="precise")
    loose = list(cmp.variants(recall="exhaustive"))
    tight = list(cmp.variants())
    assert len(loose) >= len(tight)
    assert cmp.recall == "precise"  # the override does not stick
    with pytest.raises(ValueError, match="recall must be one of"):
        list(cmp.variants(recall="maximum"))
