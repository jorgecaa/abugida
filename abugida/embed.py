"""A 14-dimensional embedding for the phonemes of Pāli.

See SPEC.md §4. The design point: the modifier axis of A is Z₃, and Z₃ is
faithfully represented as a 120° rotation in the plane. With that choice ⊗
stops being a table and becomes arithmetic on vectors — `compose_vec` is a
homomorphism, verified in tests/test_embed.py.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from .algebra import A
from .phonology import (
    CEREBRAL,
    DENTAL,
    GUTTURAL,
    PALATAL,
    PLACE_INDEX,
    Phoneme,
    is_voiced,
    phoneme,
)

#: Mass split for the places that share a karaṇa: half the identity in the
#: place's own column (the ṭhāna, the passive target), half in the shared
#: karaṇa column (the active articulator). √½ each keeps every place at unit
#: norm, so within-series costs and the balance principle are untouched;
#: only the bridge between the places sharing an organ appears.
_SPLIT = math.sqrt(0.5)

DIM = 14

# Dimension layout: 0-4 are the five places (phonology.PLACES).
VOICING = 5
MODIFIER = slice(6, 8)
SYLLABIC = 8
LENGTH = 9
CONTINUANT = 10
LATERAL = 11
#: Shared active articulator (karaṇa): the tongue TIP. Cerebral (jivhopagga,
#: the underside of the tip) and dental (jivhagga, the tip) both use it.
CORONAL = 12
#: Shared active articulator (karaṇa): the tongue BODY. Guttural (jivhāmūla,
#: the root of the tongue) and palatal (jivhāmajjha, its middle) both use it.
DORSAL = 13

#: The two karaṇa bridges, place → shared column. The tradition splits
#: articulation into ṭhāna (passive place) and karaṇa (active organ), and
#: four of the five ṭhāna pair up under an organ: the tip (cerebral, dental)
#: and the body (guttural, palatal). Labial is oṭṭhaja — the lower lip, no
#: tongue at all — so it bridges to nothing and keeps full place-change cost
#: against everything.
#:
#: This is what makes t↔ṭ (0.601) and k↔c (0.601) cheaper than k↔p (0.889),
#: and those are exactly the two confusions transmission attests (Oberlies,
#: Pali §14.5 and §18.2), and the two DPD lists most: in DPD's
#: `var_phonetic` (computed by DPD's rules, not curated), cerebral~dental
#: is 72.7% of all place substitutions between simple consonants and guttural~palatal a further 11.4% — 84.1%
#: between them, against 15.9% spread over the eight non-bridging pairs.
#: That count is measured over alignments the bridges themselves influence,
#: so `eval/karana_bridges.py` re-counts it positionally over the
#: equal-length pairs, where no cost is consulted: 90.1% shared organ, same
#: ranking. The bridges are worth +1.46 points of agreement with DPD, each layout at its
#: own ONE_MOVE.
#:
#: Not a tuned axis, and not one free parameter per pair: the equal √½/√½
#: split is fixed by giving ṭhāna and karaṇa the same weight, every place
#: keeps unit norm, and within-series costs — hence the balance principle
#: and ρ* itself — come out numerically identical. Derived from the places
#: at embedding level: the inventory's five traditional ṭhāna stay untouched.
_KARANA = {
    CEREBRAL: CORONAL,
    DENTAL: CORONAL,
    GUTTURAL: DORSAL,
    PALATAL: DORSAL,
}


Vector = List[float]

# The three cube roots of unity, rounded so that an exact 0 does not show up
# as -1e-16 and the homomorphism checks out with a clean tolerance.
_ANGLES = [2 * math.pi * k / 3 for k in range(3)]
_ROTATION = [(round(math.cos(t), 12), round(math.sin(t), 12)) for t in _ANGLES]


def mod_to_vector(mod: int) -> tuple[float, float]:
    """The Z₃ modifier as a point on the unit circle."""
    return _ROTATION[mod % 3]


def vector_to_mod(cos_t: float, sin_t: float) -> int:
    """Inverse of `mod_to_vector`: the Z₃ element nearest the given point."""
    angle = math.atan2(sin_t, cos_t) % (2 * math.pi)
    return round(angle / (2 * math.pi / 3)) % 3


def embed(p: Phoneme | str) -> Vector:
    """The 14-dimensional vector for a phoneme (or its roman grapheme)."""
    if isinstance(p, str):
        p = phoneme(p)

    v = [0.0] * DIM
    for place in p.places:
        karana = _KARANA.get(place)
        if karana is not None:
            v[PLACE_INDEX[place]] = _SPLIT
            v[karana] = _SPLIT
        else:
            v[PLACE_INDEX[place]] = 1.0

    if p.value is not None:
        v[VOICING] = float(p.value.base)
        v[MODIFIER] = list(mod_to_vector(p.value.mod))
    else:
        # ⊥: no value in A. ZERO norm in the modifier plane — distinct from
        # ε, which has norm 1 at angle 0. "No value" and "unmarked value"
        # stop being conflated (this was issue §5.4). Voicing comes from the
        # inventory (`voiced`), not from a special case here (issue §5.5).
        v[MODIFIER] = [0.0, 0.0]
        v[VOICING] = 1.0 if is_voiced(p) else 0.0

    v[SYLLABIC] = float(p.syllabic)
    v[LENGTH] = float(p.long)
    v[CONTINUANT] = float(p.continuant)
    v[LATERAL] = float(p.lateral)
    return v


def embed_value(x: A) -> Vector:
    """Only the algebraic part (dims 5–7), with the rest zeroed."""
    v = [0.0] * DIM
    v[VOICING] = float(x.base)
    v[MODIFIER] = list(mod_to_vector(x.mod))
    return v


def compose_vec(u: Sequence[float], w: Sequence[float]) -> Vector:
    """⊗ directly on vectors.

    place     → union (componentwise maximum)
    voicing   → maximum (the OR semilattice: voicing absorbs)
    modifier  → sum of angles, i.e. complex multiplication

    The remaining dimensions go by maximum, which is the neutral choice for
    binary features with no algebraic structure of their own.
    """
    v = [max(a, b) for a, b in zip(u, w)]
    ua, ub = u[MODIFIER]
    wa, wb = w[MODIFIER]
    if ua == ub == 0.0:
        # ⊥ is NEUTRAL for ⊗: no information + information = information.
        v[MODIFIER] = [wa, wb]
    elif wa == wb == 0.0:
        v[MODIFIER] = [ua, ub]
    else:
        v[MODIFIER] = [
            round(ua * wa - ub * wb, 12),
            round(ua * wb + ub * wa, 12),
        ]
    return v


#: Weight of the modifier block when measuring similarity. See `cosine`. It
#: used to be a magic 0.5; it is now DERIVED from the balance principle: the
#: elementary moves in A must cost the same — aspirating (k→kh) as much as
#: voicing (k→g). It is the unique solution of cosine(k,kh,ρ) = cosine(k,g,ρ)
#: in (0,1), computed by bisection at the end of this module (≈ 0.458 <
#: √(2/3), so the series still groups, as the threshold in `cosine` requires).
NEUTRAL_MODIFIER_WEIGHT: float  # assigned at the end of the module


def _weighted(v: Sequence[float], weight: float) -> Vector:
    out = list(v)
    out[MODIFIER] = [a * weight for a in out[MODIFIER]]
    return out


def mult_vec(u: Sequence[float], w: Sequence[float]) -> Vector:
    """⊙ directly on vectors.

    base      → minimum (boolean AND)
    modifier  → product in F₃, which acts on the circle as Galois does:
                ·0 collapses to the neutral point, ·1 is the identity, ·2 is
                COMPLEX CONJUGATION (2 ≡ −1 mod 3: negate the angle).

    Unlike ⊗ (complex multiplication, bilinear), ⊙ is not bilinear on the
    plane — the circular representation is that of the additive group, and
    the field's product acts on it by automorphisms. Hence the
    decode → multiply → encode. It remains an exact homomorphism:
    test_embed.py::test_mult_homomorphism verifies it over all 36 pairs.

    The remaining dimensions go by minimum (coincidence of binary features).
    """
    v = [min(a, b) for a, b in zip(u, w)]
    ua, ub = u[MODIFIER]
    wa, wb = w[MODIFIER]
    if (ua == ub == 0.0) or (wa == wb == 0.0):
        # ⊥ ABSORBS in ⊙: coincidence with the unknown is unknown.
        v[MODIFIER] = [0.0, 0.0]
    else:
        mu = vector_to_mod(ua, ub)
        mw = vector_to_mod(wa, wb)
        v[MODIFIER] = list(mod_to_vector((mu * mw) % 3))
    return v


def cosine(
    u: Sequence[float], w: Sequence[float], modifier_weight: float = 1.0
) -> float:
    """Cosine similarity between two phonemes.

    `modifier_weight` scales dims 6–7 before measuring, and it is needed
    because faithful representation and similarity metric pull in opposite
    directions.

    Representing Z₃ as a 120° rotation is what makes ⊗ exact, but it places
    ε, + and − at cosine −0.5 from each other: mutually *anti*-correlated.
    Two distinct places, by contrast, are merely orthogonal (cosine 0). With
    weight 1.0 the upshot is that differing in modifier is penalised more
    than differing in place, and `k` comes out closer to `p` than to `kh`.

    Exact threshold: with weight ρ, `cosine(k,kh) = (1 − ρ²/2)/(1 + ρ²)` and
    `cosine(k,p) = ρ²/(1 + ρ²)`, so the series groups if and only if
    ρ < √(2/3) ≈ 0.816.

    The default 1.0 is the embedding as it stands, untouched. To group by
    series use `NEUTRAL_MODIFIER_WEIGHT`. The arithmetic of `compose_vec`
    requires the unweighted vector; the weight is for measuring only.
    """
    if modifier_weight != 1.0:
        u = _weighted(u, modifier_weight)
        w = _weighted(w, modifier_weight)
    dot = sum(a * b for a, b in zip(u, w))
    nu = math.sqrt(sum(a * a for a in u))
    nw = math.sqrt(sum(b * b for b in w))
    if nu == 0.0 or nw == 0.0:
        return 0.0
    return dot / (nu * nw)


def _balanced_weight() -> float:
    """The ρ of the balance principle (see NEUTRAL_MODIFIER_WEIGHT).

    f(ρ) = cosine(k,kh,ρ) − cosine(k,g,ρ) is continuous, positive as ρ→0
    (k and kh differ only in modifier: unweighted they are identical) and
    negative at ρ=1 (0.25 < 0.816): one root, found by bisection over the
    inventory's actual vectors — if the embedding layout ever changes, ρ
    recomputes itself.
    """
    k, kh, g = embed("k"), embed("kh"), embed("g")
    lo, hi = 1e-6, 1.0
    for _ in range(60):
        rho = (lo + hi) / 2.0
        if cosine(k, kh, rho) > cosine(k, g, rho):
            lo = rho
        else:
            hi = rho
    return (lo + hi) / 2.0


NEUTRAL_MODIFIER_WEIGHT = _balanced_weight()
