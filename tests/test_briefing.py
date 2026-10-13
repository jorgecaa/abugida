"""Every claim in `docs/using-abugida.md`, executed.

That document is written to be pasted into a prompt or handed to someone
integrating the library, which means nobody will be reading the source
alongside it. A briefing that drifts from the code is worse than none, so
each figure and each call in it is pinned here.
"""

import pytest

from abugida import Comparator
from abugida.comparator import RECALL_SETTINGS

LEMMAS = ["dhamma", "dhammā", "damma", "kamma", "saṃgha", "saṅgha", "kṛṣṇa"]


@pytest.fixture
def cmp():
    return Comparator(LEMMAS)


def test_the_five_calls_shown_all_work(cmp):
    assert cmp.neighbours("dhamma", k=5)
    assert list(cmp.variants())
    assert list(cmp.variants(words=["dhamma"]))
    assert cmp.rejected == {
        "kṛṣṇa": "not Pāli: 'ṛ' (sanskrit), 'ṣ' (sanskrit)"
    }
    assert "dhamma" in cmp


def test_the_neighbours_output_shown_is_the_real_one(cmp):
    """The doc prints [(0.333, 'dhammā'), (0.344, 'damma'), …]."""
    got = cmp.neighbours("dhamma", k=2)
    assert [w for _, w in got] == ["dhammā", "damma"]
    assert got[0][0] == pytest.approx(0.333, abs=0.001)
    assert got[1][0] == pytest.approx(0.344, abs=0.001)


def test_each_pair_is_yielded_once(cmp):
    rows = [(a, b) for a, b, _, _ in cmp.variants()]
    assert len(rows) == len(set(rows))
    assert all(a < b for a, b in rows)


def test_the_recall_table(cmp):
    """Named settings, ordered as the table says."""
    assert RECALL_SETTINGS["precise"] == 0.12
    assert RECALL_SETTINGS["balanced"] == 0.16
    assert RECALL_SETTINGS["exhaustive"] == 0.22
    assert Comparator(LEMMAS).recall == "balanced"  # the documented default


def test_the_distance_scale():
    """0.333 vowel length · 0.470 one algebra move · 0.601 a shared-organ
    place change · 0.889 a change of place · 1.0 unrelated."""
    from abugida import cost

    assert cost("a", "ā") == pytest.approx(0.333, abs=0.001)
    assert cost("k", "kh") == pytest.approx(0.470, abs=0.001)
    assert cost("k", "g") == pytest.approx(0.470, abs=0.001)
    assert cost("tt", "t") == pytest.approx(0.470, abs=0.001)
    assert cost("t", "ṭ") == pytest.approx(0.601, abs=0.001)
    assert cost("k", "c") == pytest.approx(0.601, abs=0.001)
    assert cost("k", "p") == pytest.approx(0.889, abs=0.001)
    assert cost("b", "s") == pytest.approx(1.0, abs=0.001)


def test_zero_after_normalisation(cmp):
    """"0 identical after normalisation" — saṃgha/saṅgha is the case."""
    pairs = {(a, b): d for a, b, d, _ in cmp.variants()}
    assert pairs[("saṃgha", "saṅgha")] == pytest.approx(0.0)


def test_input_rules(cmp):
    with pytest.raises(ValueError):
        cmp.neighbours("dhamm@")
    assert cmp.neighbours("dhamm@", k=1, lenient=True)  # never raises
    assert "kṛṣṇa" in Comparator(LEMMAS, accept="pali+sanskrit")


def test_constructions_pair_identical_formations():
    cmp = Comparator(["agamā", "agā"],
                     constructions={"agamā": "a + √gam + ā",
                                    "agā": "a + √gam + ā"})
    assert [t for *_, t in cmp.variants()] == ["=construction"]


def test_the_stated_limits_are_the_real_ones():
    """Sanskritised doublets fall outside every setting, sarva~sabba too:
    the geminate is one heavy unit and cannot align letter by letter with a
    cluster of two articulations (tatra ~ tattha 1.47)."""
    tatra = ["tatra", "tattha"]
    assert not list(Comparator(tatra, recall="exhaustive").variants())
    assert not list(Comparator(["sarva", "sabba"],
                               recall="exhaustive").variants())


def test_the_escape_hatch_is_public(cmp):
    from abugida import Lexicon

    assert isinstance(cmp.lexicon, Lexicon)
