"""The algebra A does what SPEC.md §1 claims it does."""

import itertools

import pytest

from abugida.algebra import (
    ELEMENTS,
    EPSILON,
    IDENTITY,
    NASAL,
    NIGGAHITA,
    ONE,
    VOICED,
    VOICED_ASPIRATED,
    VOICELESS,
    VOICELESS_ASPIRATED,
    ZERO,
    A,
    LATTICE_BOTTOM,
    LATTICE_TOP,
    and_,
    compose,
    compose_xor,
    inverse,
    inverse_mult,
    is_unit,
    is_unit_mult,
    mult,
    not_,
    or_,
    sum_,
)


def test_given_axioms():
    """The two starting axioms: + and − cancel, at each voicing level."""
    assert compose(VOICELESS_ASPIRATED, NIGGAHITA) == VOICELESS
    assert compose(VOICED_ASPIRATED, NASAL) == VOICED


def test_associativity():
    for x, y, z in itertools.product(ELEMENTS, repeat=3):
        assert compose(compose(x, y), z) == compose(x, compose(y, z))


def test_commutativity():
    for x, y in itertools.product(ELEMENTS, repeat=2):
        assert compose(x, y) == compose(y, x)


def test_identity():
    for x in ELEMENTS:
        assert compose(IDENTITY, x) == x


def test_modifier_is_z3_not_idempotent():
    """Forced by associativity: + ⊗ + = −, not +.

    If aspiration were idempotent the algebra would not be associative.
    """
    assert compose(VOICELESS_ASPIRATED, VOICELESS_ASPIRATED) == NIGGAHITA
    assert compose(VOICED_ASPIRATED, VOICED_ASPIRATED) == NASAL


def test_base_is_not_z2():
    """The base is the OR semilattice, not Z₂: 1 ⊗ 1 = 1, not 0."""
    assert compose(VOICED, VOICED) == VOICED


def test_voicing_absorbs():
    for x in ELEMENTS:
        assert compose(VOICED, x).base == 1


def test_units_are_exactly_the_voiceless():
    units = {x for x in ELEMENTS if is_unit(x)}
    assert units == {VOICELESS, VOICELESS_ASPIRATED, NIGGAHITA}
    for x in units:
        assert compose(x, inverse(x)) == IDENTITY


def test_the_niggahita_is_a_reversible_contradiction():
    """The paraconsistent point: 0− does not absorb, it undoes.

    In classical features `0−` is a voiceless nasal, i.e. voiced ∧ ¬voiced,
    and should trivialise the system. Here it is a unit. The absorbing
    element is `1`.
    """
    assert is_unit(NIGGAHITA)
    assert compose(NIGGAHITA, inverse(NIGGAHITA)) == IDENTITY
    assert {compose(NIGGAHITA, x) for x in ELEMENTS} == set(ELEMENTS)


def test_the_voiced_form_a_group_with_their_own_identity():
    voiced = [x for x in ELEMENTS if x.base == 1]
    for x in voiced:
        assert compose(VOICED, x) == x
        inv = next(y for y in voiced if compose(x, y) == VOICED)
        assert inv in voiced


def test_the_voiced_are_not_invertible_in_a():
    for x in (VOICED, VOICED_ASPIRATED, NASAL):
        with pytest.raises(ValueError):
            inverse(x)


@pytest.mark.parametrize("text", ["0", "0+", "0−", "0-", "1", "1+", "1−"])
def test_parse_round_trip(text):
    assert str(A.parse(text)) == text.replace("-", "−")


class TestSemiring:
    """A ≅ B × F₃ is a commutative semiring: ⊗ is the sum, ⊙ the product."""

    def test_mult_associative_and_commutative(self):
        for x, y, z in itertools.product(ELEMENTS, repeat=3):
            assert mult(mult(x, y), z) == mult(x, mult(y, z))
        for x, y in itertools.product(ELEMENTS, repeat=2):
            assert mult(x, y) == mult(y, x)

    def test_one_is_neutral_for_mult(self):
        """The multiplicative unit is 1+ — the voiced aspirate."""
        assert ONE == VOICED_ASPIRATED
        for x in ELEMENTS:
            assert mult(ONE, x) == x

    def test_zero_absorbs_in_mult(self):
        """The absorbing element ⊗ lacked, ⊙ has: 0 ⊙ x = 0."""
        assert ZERO == VOICELESS == IDENTITY
        for x in ELEMENTS:
            assert mult(ZERO, x) == ZERO

    def test_distributivity(self):
        """⊙ distributes over ⊗ — the law that ties both operations."""
        for x, y, z in itertools.product(ELEMENTS, repeat=3):
            assert mult(x, compose(y, z)) == compose(mult(x, y), mult(x, z))

    def test_multiplicative_units_are_z2(self):
        """Invertible under ⊙: exactly {1+, 1−} ≅ Z₂.

        The mirror image of the additive units (the voiceless ones, ≅ Z₃).
        Each operation has its own unit group, complementary in character.
        """
        units = {x for x in ELEMENTS if is_unit_mult(x)}
        assert units == {VOICED_ASPIRATED, NASAL}
        for x in units:
            assert mult(x, inverse_mult(x)) == ONE

    def test_nasal_times_nasal_is_aspirate(self):
        """1− is an involution: 2 · 2 ≡ 1 in F₃."""
        assert mult(NASAL, NASAL) == VOICED_ASPIRATED

    def test_the_unmarked_absorbs_the_mark(self):
        """On the modifier axis, ε = 0 of F₃: multiplying by something
        unmarked erases the mark. ⊙ is coincidence, ⊗ was accumulation."""
        for x in ELEMENTS:
            assert mult(VOICED, x).mod == 0  # 1 carries ε: erases every mark
        assert mult(VOICED, VOICED_ASPIRATED) == VOICED
        assert mult(VOICELESS_ASPIRATED, NASAL) == A.parse("0−")


class TestNoRing:
    """Theorem: under the given axioms, A admits no ring structure with ⊗.

    A ring requires one operation to be an abelian group and the other to
    have an absorbing zero. ⊗ fits neither role; hence A is a semiring (a
    ring without subtraction) and not a ring. Being unable to subtract is
    the algebraic form of "voicing cannot be undone".
    """

    def test_compose_is_not_a_group(self):
        """1 has no inverse under ⊗: the base never returns to 0.

        A direct consequence of the axiom 1+ ⊗ 1− = 1 (voicing absorption).
        Making the base Z₂ would supply the inverse — and break that axiom.
        """
        assert all(compose(VOICED, x) != IDENTITY for x in ELEMENTS)

    def test_compose_has_no_absorbing_element(self):
        """No z satisfies z ⊗ x = z for every x: the modifier always turns.

        So ⊗ cannot be a ring's multiplication either, which requires an
        absorbing 0 · x = 0.
        """
        for z in ELEMENTS:
            assert any(compose(z, x) != z for x in ELEMENTS)


class TestXorVariant:
    """`compose_xor` (EXPERIMENTAL): what the base being Z₂ would cost.

    Not an alternative implementation of ⊗ — a counterfactual kept runnable,
    so the reason the base is the OR semilattice stays checkable rather than
    merely asserted. See `algebra.compose_xor`.
    """

    def test_it_contradicts_the_second_axiom(self):
        """The reason it is not ⊗. `1+ ⊗ 1− = 1` is the given datum; XOR
        makes it voiceless."""
        assert compose(VOICED_ASPIRATED, NASAL) == VOICED
        assert compose_xor(VOICED_ASPIRATED, NASAL) == VOICELESS

    def test_it_is_the_cyclic_group_of_order_six(self):
        """Z₂ × Z₃ ≅ Z₆, generated by 1+ — the semiring's ONE."""
        walk, x = [], VOICED_ASPIRATED
        for _ in range(6):
            walk.append(x)
            x = compose_xor(x, VOICED_ASPIRATED)
        assert len(set(walk)) == 6  # generates the whole algebra
        assert walk[-1] == VOICELESS  # …and closes on the neutral element
        assert set(walk) == set(ELEMENTS)

    def test_everything_becomes_invertible(self):
        """The cost: no absorbing element, so no ideal — and with it the
        paraconsistent reading of §2 has nothing to say. Under ⊗ exactly the
        voiceless values are units."""
        for x in ELEMENTS:
            assert any(compose_xor(x, y) == VOICELESS for y in ELEMENTS)
        assert [x for x in ELEMENTS if is_unit(x)] == [
            VOICELESS, VOICELESS_ASPIRATED, NIGGAHITA
        ]

    def test_voicing_stops_being_irreversible(self):
        """Under ⊗ voicing absorbs (1 ⊗ 1 = 1): once voiced, never undone.
        XOR devoices by composition, which Pāli does not do."""
        assert compose(VOICED, VOICED) == VOICED
        assert compose_xor(VOICED, VOICED) == VOICELESS

    def test_it_is_exactly_the_ring_of_integers_mod_six(self):
        """The sharp form of the counterfactual. ⊙ still distributes, 0 still
        absorbs and 1+ is still neutral, so the XOR variant is a commutative
        ring — and by CRT, F₂ × F₃ ≅ Z/6Z. The map 1+ ↦ 1 carries BOTH
        operations, which is what makes it an isomorphism of rings and not a
        coincidence of addition.

        §1.5 proves no ring is possible with ⊗. This pins the complement:
        the ring is reachable, and the axiom `1+ ⊗ 1− = 1` is its price."""
        for a, b, c in itertools.product(ELEMENTS, repeat=3):
            assert mult(a, compose_xor(b, c)) == compose_xor(
                mult(a, b), mult(a, c)
            )
        assert all(mult(ZERO, x) == ZERO for x in ELEMENTS)
        assert all(mult(ONE, x) == x for x in ELEMENTS)

        iso, x = {}, VOICED_ASPIRATED
        for n in range(1, 7):
            iso[x] = n % 6
            x = compose_xor(x, VOICED_ASPIRATED)
        assert iso[VOICED_ASPIRATED] == 1 and iso[ZERO] == 0
        for a, b in itertools.product(ELEMENTS, repeat=2):
            assert iso[compose_xor(a, b)] == (iso[a] + iso[b]) % 6
            assert iso[mult(a, b)] == (iso[a] * iso[b]) % 6


class TestLatticeOps:
    """`or_`/`and_`/`not_`/`sum_` (EXPERIMENTAL): what a boolean reading of A
    can and cannot reach.

    The payoff is negative and precise: the lattice is De Morgan but not
    boolean, so the symmetric difference built from it is not XOR — a lattice
    cannot express the cyclicity of Z₃. See `algebra.sum_`.
    """

    def test_it_is_a_distributive_de_morgan_algebra(self):
        for x in ELEMENTS:
            assert not_(not_(x)) == x
        for a, b in itertools.product(ELEMENTS, repeat=2):
            assert not_(or_(a, b)) == and_(not_(a), not_(b))
            assert not_(and_(a, b)) == or_(not_(a), not_(b))
        for a, b, c in itertools.product(ELEMENTS, repeat=3):
            assert and_(a, or_(b, c)) == or_(and_(a, b), and_(a, c))
            assert or_(a, and_(b, c)) == and_(or_(a, b), or_(a, c))

    def test_the_aspirates_have_no_complement(self):
        """Where boolean fails: the MODIFIER `+` is fixed by 2−m, so the
        modifier of `x ∧ ¬x` stays at `+` and never reaches bottom, however
        the base cancels. (The element is not fixed: not_(0+) = 1+.) A
        three-value chain with an order-reversing involution is Kleene's
        algebra, not Boole's."""
        assert not_(VOICELESS_ASPIRATED) == VOICED_ASPIRATED
        assert and_(VOICELESS_ASPIRATED, not_(VOICELESS_ASPIRATED)).mod == (
            VOICELESS_ASPIRATED.mod
        )
        complemented = [
            x for x in ELEMENTS
            if and_(x, not_(x)) == LATTICE_BOTTOM
            and or_(x, not_(x)) == LATTICE_TOP
        ]
        assert complemented == [VOICELESS, NIGGAHITA, VOICED, NASAL]
        assert VOICELESS_ASPIRATED not in complemented
        assert VOICED_ASPIRATED not in complemented

    def test_the_derived_sum_is_not_xor(self):
        """(a∧¬b)∨(¬a∧b) is XOR in a boolean algebra. Here it agrees with
        `compose_xor` on exactly 20 of 36 pairs, and the rule is sharp: they
        agree iff at least one operand is unmarked."""
        agree = [
            (a, b) for a, b in itertools.product(ELEMENTS, repeat=2)
            if sum_(a, b) == compose_xor(a, b)
        ]
        assert len(agree) == 20
        for a, b in itertools.product(ELEMENTS, repeat=2):
            unmarked = a.mod == EPSILON or b.mod == EPSILON
            assert (sum_(a, b) == compose_xor(a, b)) is unmarked

    def test_the_derived_sum_is_a_monoid_but_not_a_group(self):
        """Associative and commutative with 0 neutral — but the aspirate is
        its own sum, so it has no inverse and there is no group."""
        for a, b, c in itertools.product(ELEMENTS, repeat=3):
            assert sum_(sum_(a, b), c) == sum_(a, sum_(b, c))
        for a, b in itertools.product(ELEMENTS, repeat=2):
            assert sum_(a, b) == sum_(b, a)
        for a in ELEMENTS:
            assert sum_(a, ZERO) == a
        assert sum_(VOICELESS_ASPIRATED, VOICELESS_ASPIRATED) == (
            VOICELESS_ASPIRATED
        )
        assert not all(
            any(sum_(a, b) == ZERO for b in ELEMENTS) for a in ELEMENTS
        )

    def test_no_lattice_reconstructs_the_cyclic_cancellation(self):
        """The one fact the whole block exists to pin: ⊗ and XOR both send
        + ⊗ + to −, and the lattice sum sends it back to +. Cyclicity is
        arithmetic in Z₃, not order-theoretic."""
        plus = VOICELESS_ASPIRATED
        assert compose(plus, plus) == NIGGAHITA  # ε + 1 + 1 = 2 = −
        assert compose_xor(plus, plus) == NIGGAHITA
        assert sum_(plus, plus) == plus  # the lattice cannot cancel

    def test_no_product_ordering_at_all_reconstructs_it(self):
        """The previous test uses one chain (ε < + < −). This one closes the
        escape route: over ALL 3!×2! assignments of ranks to the modifier and
        the base, the lattice sum reproduces neither ⊗ nor `compose_xor`.
        The choice of order is not what makes the construction fail."""
        for mperm in itertools.permutations(range(3)):
            for bperm in itertools.permutations(range(2)):
                rank = lambda x: (bperm[x.base], mperm[x.mod])  # noqa: E731
                back = {
                    (bperm[b], mperm[m]): A(b, m)
                    for b in range(2)
                    for m in range(3)
                }
                jn = lambda x, y: back[(  # noqa: E731
                    max(rank(x)[0], rank(y)[0]), max(rank(x)[1], rank(y)[1]))]
                mt = lambda x, y: back[(  # noqa: E731
                    min(rank(x)[0], rank(y)[0]), min(rank(x)[1], rank(y)[1]))]
                cp = lambda x: back[(1 - rank(x)[0], 2 - rank(x)[1])]  # noqa
                s = lambda a, b: jn(mt(a, cp(b)), mt(cp(a), b))  # noqa: E731
                assert not all(
                    s(a, b) == compose_xor(a, b)
                    for a, b in itertools.product(ELEMENTS, repeat=2)
                )
                assert not all(
                    s(a, b) == compose(a, b)
                    for a, b in itertools.product(ELEMENTS, repeat=2)
                )
