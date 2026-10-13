"""The embedding faithfully represents the algebra and separates the
inventory."""

import itertools
import math

import pytest

from abugida.algebra import ELEMENTS, MINUS, compose, mult
from abugida.embed import (
    DIM,
    MODIFIER,
    NEUTRAL_MODIFIER_WEIGHT,
    compose_vec,
    cosine,
    embed,
    embed_value,
    mult_vec,
)
from abugida.phonology import (
    INVENTORY,
    NASAL,
    NIGGAHITA_PHONEME,
    STOPS,
    assimilate,
)

TOL = 1e-9


def _close(u, w):
    return all(abs(a - b) < TOL for a, b in zip(u, w))


def test_dimension():
    for p in INVENTORY:
        assert len(embed(p)) == DIM


def test_homomorphism():
    """The diagram commutes over all 36 pairs of A.

    Composing in the algebra then embedding == embedding then composing.
    This is what makes ⊗ arithmetic on vectors rather than a lookup table.
    """
    for x, y in itertools.product(ELEMENTS, repeat=2):
        assert _close(
            embed_value(compose(x, y)),
            compose_vec(embed_value(x), embed_value(y)),
        )


def test_mult_homomorphism():
    """The diagram commutes for ⊙ too, over all 36 pairs of A."""
    for x, y in itertools.product(ELEMENTS, repeat=2):
        assert _close(
            embed_value(mult(x, y)),
            mult_vec(embed_value(x), embed_value(y)),
        )


def test_multiplying_by_nasal_is_conjugation():
    """⊙ by 1− negates the modifier's angle: complex conjugation.

    2 ≡ −1 in F₃, and on the circle that is (cos, sin) → (cos, −sin).
    """
    nasal = embed_value(ELEMENTS[5])  # 1−
    assert ELEMENTS[5].mod == MINUS
    for x in ELEMENTS:
        if x.base == 0:
            continue  # the AND base switches voicing off; we watch the turn
        u = embed_value(x)
        cos_u, sin_u = u[MODIFIER]
        product = mult_vec(u, nasal)
        assert product[MODIFIER] == pytest.approx([cos_u, -sin_u])


def test_the_inventory_is_separated():
    """41 phonemes, 41 distinct vectors: the embedding collapses no
    contrast."""
    vectors = {tuple(embed(p)) for p in INVENTORY}
    assert len(vectors) == len(INVENTORY) == 41


def test_modifiers_equidistant_from_the_neutral():
    """+ and − sit 120° from ε, not on opposite sides of a line.

    Were the modifier a scalar (−1, 0, +1), aspirate and nasal would be
    collinear with the unmarked value and maximally distant from each other,
    which is false: both are marks on the same base.
    """
    base, plus, minus = (embed_value(x) for x in ELEMENTS[:3])
    d_plus = cosine(base, plus)
    d_minus = cosine(base, minus)
    assert abs(d_plus - d_minus) < TOL
    assert abs(cosine(plus, minus) - d_plus) < TOL


def test_unweighted_the_modifier_dominates_place():
    """A consequence of representing Z₃ faithfully, not a bug.

    The 120° rotation leaves ε, + and − at cosine −0.5 (anti-correlated),
    whereas two distinct places are merely orthogonal. On the raw vector `k`
    comes out closer to `p` than to `kh`.
    """
    k, kh, p = embed("k"), embed("kh"), embed("p")
    assert cosine(k, kh) == pytest.approx(0.25)
    assert cosine(k, p) == pytest.approx(0.5)


def test_weighting_the_modifier_groups_by_series():
    """Below the threshold ρ < √(2/3), the series groups again."""
    k, kh, p = embed("k"), embed("kh"), embed("p")
    rho = NEUTRAL_MODIFIER_WEIGHT
    assert rho < math.sqrt(2 / 3)
    assert cosine(k, kh, rho) > cosine(k, p, rho)


def test_the_weight_threshold_is_as_documented():
    """(1 − ρ²/2)/(1 + ρ²) against ρ²/(1 + ρ²); they cross at ρ = √(2/3)."""
    k, kh, p = embed("k"), embed("kh"), embed("p")
    for rho in (0.3, 0.5, 0.7, 0.9, 1.0):
        assert cosine(k, kh, rho) == pytest.approx(
            (1 - rho**2 / 2) / (1 + rho**2)
        )
        assert cosine(k, p, rho) == pytest.approx(rho**2 / (1 + rho**2))
    crossing = math.sqrt(2 / 3)
    assert cosine(k, kh, crossing) == pytest.approx(cosine(k, p, crossing))


def test_niggahita_occupies_every_place():
    """Under the glut reading, ṃ is the overdetermined one, not the empty
    one. The four bridged places carry √½ in their own column (the other
    half lives in their shared karaṇa column, counted once per organ);
    labial, which bridges to nothing, keeps its full 1.0.

    Total mass: 4×½ (the ṭhāna halves) + 1 (labial) + ½ + ½ (the two karaṇa
    columns, each counted once however many places feed it) = 4.0."""
    import math

    from abugida.embed import CORONAL, DORSAL

    v = embed(NIGGAHITA_PHONEME)
    assert all(x > 0 for x in v[0:5])
    assert v[CORONAL] == pytest.approx(math.sqrt(0.5))
    assert v[DORSAL] == pytest.approx(math.sqrt(0.5))
    assert sum(x * x for x in v[0:5]) + v[CORONAL] ** 2 + v[
        DORSAL
    ] ** 2 == pytest.approx(4.0)


@pytest.mark.parametrize(
    "following,expected",
    [("gh", "ṅ"), ("j", "ñ"), ("ḍ", "ṇ"), ("d", "n"), ("b", "m")],
)
def test_assimilation(following, expected):
    """saṃ+gha → saṅgha, saṃ+jāta → sañjāta, …"""
    assert assimilate(following).grapheme == expected


def test_assimilation_before_a_vowel_does_not_resolve():
    """With no single place to select, ṃ stays as it is.

    This is exactly where glut and gap diverge: here it stays overdetermined
    (residual nasalisation); under gap it would be left empty.
    """
    assert assimilate("a").grapheme == "ṃ"


def test_bottom_differs_from_epsilon():
    """"No value" (⊥, norm 0) is no longer conflated with "unmarked"
    (ε, norm 1).

    This was issue §5.4: a vowel and k shared modifier coordinates.
    """
    assert embed("a")[MODIFIER] == [0.0, 0.0]  # ⊥
    assert embed("k")[MODIFIER] == [1.0, 0.0]  # ε
    assert embed("y")[MODIFIER] == [0.0, 0.0]


def test_bottom_is_neutral_for_compose_vec():
    """Composing a vowel into an akṣara does not erase the rest's modifier:
    no information + information = information."""
    dh_a = compose_vec(embed("dh"), embed("a"))
    assert dh_a[MODIFIER] == pytest.approx(embed("dh")[MODIFIER])
    a_dh = compose_vec(embed("a"), embed("dh"))
    assert a_dh[MODIFIER] == pytest.approx(embed("dh")[MODIFIER])


def test_bottom_absorbs_in_mult_vec():
    """Coincidence with the unknown is unknown."""
    assert mult_vec(embed("a"), embed("dh"))[MODIFIER] == [0.0, 0.0]


def test_voicing_comes_from_the_inventory():
    """s is the only voiceless segment outside A; h and the semivowels are
    voiced.

    This used to be decided by a string comparison in embed.py (issue §5.5);
    it is now inventory data (the `voiced` field).
    """
    assert embed("s")[5] == 0.0
    for g in ("h", "y", "r", "l", "ḷ", "a", "ā"):
        assert embed(g)[5] == 1.0


def test_nasals_are_voiced_but_the_niggahita_is_not():
    for p in STOPS:
        if p.value == NASAL:
            assert embed(p)[5] == 1.0
    assert embed(NIGGAHITA_PHONEME)[5] == 0.0
