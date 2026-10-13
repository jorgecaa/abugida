"""Phonological distance between Pāli words — the C core, with a Python face.

This module is the one every consumer imports, and it is deliberately thin:
the metric is implemented once, in C (`csrc/abugida.c`, with the tables
generated from the Python definitions by `tools/generate_c_tables.py`), and
what happens here is choosing between that and the pure-Python reference in
`abugida._pure`.

    from abugida import distance
    distance("kamma", "khamma")   # 0.470, computed by the C core

WHICH IMPLEMENTATION RAN
========================

`USING_C` says. The C core is used whenever the extension compiled — which
is the supported configuration, and what the published numbers were measured
with (`docs/c-core.md` has the benchmark). If it did not, the pure-Python
implementation answers instead, with identical values, so a source checkout
without a compiler still works.

The two are not merely similar: `tests/test_c_parity.py` requires EXACT
agreement between them, over every grapheme pair, over the whole token
vocabulary and over a fixed-seed sample of words. That is only possible
because the C tables are literally `distance.cost` evaluated once per pair by
the generator, and the DP recurrences were written to match — the work of
making them match is what `docs/c-core.md` records.

WHAT IS NOT IN C, AND WHY
=========================

- **Unicode normalisation** (`iast.normalize`): NFC composition and case
  folding need the Unicode character database, and vendoring it to compute a
  distance would be a much larger dependency than the metric. The C core's
  contract is to receive NFC-normalised lowercase IAST, and the binding
  normalises first.
- **The experimental alternatives** (`weighted_cost`, `weighted_distance`):
  a componentwise L1 in place of the angle, measured worse and kept only as
  the runnable answer to "why an angle?" (SPEC §4). They stay in Python; the
  binding exposes the DP as `_edit`, so they still run the C recurrence.
- **`neighbors`, `sandhi_join`, `index`**: glue, not metric.

The theory — the algebra, the embedding, the derivation of every constant —
is in SPEC.md §14 and repeated in the docstrings of `abugida._pure`, which
is the reference the C core is verified against.
"""

from __future__ import annotations

from typing import List

from . import _pure

#: The C core, when it is there. The import is guarded because a source
#: checkout without a built extension must still work: the pure-Python
#: implementation answers instead, with the same values.
try:  # pragma: no cover - the branch taken depends on the build
    from . import _cabugida as _c

    USING_C = True
except ImportError:  # pragma: no cover
    _c = None
    USING_C = False


__all__ = [
    "USING_C",
    "algebraic_cost",
    "cost",
    "indel",
    "distance",
    "levenshtein",
    "neighbors",
    "alignment",
    "weighted_cost",
    "weighted_distance",
    "INDEL_WEIGHT",
    "EPENTHETIC",
    "ONE_MOVE",
    "L1_MODIFIER_WEIGHT",
]

# --- derived constants ----------------------------------------------------
# Read from the reference implementation, which derives them at import time
# from the embeddings. The C tables carry the same numbers, generated from
# here; that they agree is a property `tests/test_c_parity.py` checks rather
# than one this module assumes.
#
# `ONE_MOVE` is the costliest elementary move; it is DEFINED in `abugida._pure`
# (beside the constants it is the maximum of) and `abugida.lexicon` imports it
# from here, which is where callers have always found it.
ONE_MOVE = _pure.ONE_MOVE

EPENTHETIC = _pure.EPENTHETIC
INDEL_WEIGHT = _pure.INDEL_WEIGHT
L1_MODIFIER_WEIGHT = _pure.L1_MODIFIER_WEIGHT

#: The geminate vocabulary, re-exported for `eval/` scripts that consult it.
#: It is the REFERENCE dict; the C core has the same information as a table
#: generated from this one.
_GEMINATE_BASES = _pure._GEMINATE_BASES
_UNITS = _pure._UNITS

#: The algorithmically derived private helpers, kept for the same reason:
#: `eval/ablate_geminates.py` and `eval/karana_bridges.py` drive the DP
#: directly to price a design change, which is exactly what they are for.
_indel = _pure._indel
_vector = _pure._vector


# --- the metric -----------------------------------------------------------

def algebraic_cost(x, y) -> int:
    """Generator moves of ⊗ between two values of A: 0, 1 or 2.

    Arithmetic on the two coordinates, identical in both implementations; it
    is written here once rather than in C because it is a property of the
    algebra, not of the metric's geometry.
    """
    return _pure.algebraic_cost(x, y)


if USING_C:
    def cost(g1: str, g2: str) -> float:
        """Cost of substituting grapheme `g1` with `g2`, in [0, 1] — a METRIC.

        Truncated angular distance between the 14-dimensional embeddings:
        min(1, θ/(π/2)), weighted by the derived balance weight ρ*. The
        derivation, the noisy-channel reading that fixes the LINEAR form, and
        the measured reason a concave warping is wrong here are all in
        `abugida._pure.cost`, which is the same function.

        Characters outside the inventory (a typo, in lenient mode) are opaque:
        1.0 against every real grapheme, 0.0 against themselves.
        """
        return _c.cost(g1, g2)

    def indel(g: str) -> float:
        """Insertion/deletion cost of a grapheme: the derived epenthetic
        weight for the class Geiger attests as ordinary transmission
        variation, 1.0 for everything else."""
        return _c.indel(g)

    def distance(w1: str, w2: str, lenient: bool = False) -> float:
        """Phonological distance between two IAST words.

        With `lenient=True`, characters outside the Pāli alphabet become
        opaque tokens (cost 1 against everything) instead of raising: the
        comparison degrades gracefully and the intact remainder of the word
        still discriminates. Report the absorbed characters with
        `iast.diagnose`.
        """
        return _c.distance(w1, w2, lenient)

    def levenshtein(w1: str, w2: str, lenient: bool = False) -> int:
        """Classic Levenshtein over the SAME tokens (kh = one letter)."""
        return _c.levenshtein(w1, w2, lenient)

    def alignment(w1: str, w2: str, lenient: bool = False) -> List[tuple]:
        """The optimal edit script between two words — the information the
        scalar `distance` aggregates away.

        Returns a list of operations (op, from_grapheme, to_grapheme, cost)
        with op ∈ {"keep", "sub", "del", "ins"}; "keep" carries cost 0.0,
        "del"/"ins" carry 1.0 and None on the missing side. The costs sum
        exactly to `distance(w1, w2)` (tested), so nothing is lost between the
        two views: `distance` answers "how far", `alignment` answers "along
        which path".
        """
        return _c.alignment(w1, w2, lenient)

    def _edit(t1, t2, substitution, indel=_pure._indel,
              geminates: bool = True) -> float:
        """Edit distance with the given substitution and indel costs (DP),
        over heavy units when `geminates` is set (the default).

        The DP is the C one; `substitution` and `indel` are Python callables
        taking TOKEN STRINGS, which is the signature `eval/` scripts use
        (`_edit(tokens(w1), tokens(w2), cost, geminates=False)` prices the
        heavy units by switching them off). They are adapted to the
        binding's token-id signature here, once per call.
        """
        if substitution is cost:
            sub = _c.PHONOLOGICAL
        else:
            _sub = substitution
            sub = lambda a, b: _sub(_c.text_of(a), _c.text_of(b))  # noqa: E731
        if indel is _pure._indel:
            ind = _c.indel_derived
        else:
            _ind = indel
            ind = lambda tok: _ind(_c.text_of(tok))  # noqa: E731
        if not geminates:
            # The binding has no switch for this: dropping the units means a
            # DP over the letters as they come. `_pure` implements
            # that flag, and this path exists only for the ablation scripts,
            # so it takes the reference route deliberately.
            return _pure._edit(t1, t2, substitution, indel, geminates=False)
        return _c.edit(_c.ids_of(t1), _c.ids_of(t2), sub, ind)

else:  # pragma: no cover - exercised only without a built extension
    cost = _pure.cost
    indel = _pure._indel
    distance = _pure.distance
    levenshtein = _pure.levenshtein
    alignment = _pure.alignment
    _edit = _pure._edit


def neighbors(word: str, candidates, k: int = 5, lenient: bool = False
              ) -> List[tuple]:
    """The k phonologically nearest candidates, with both measures."""
    rows = [
        (distance(word, c, lenient), levenshtein(word, c, lenient), c)
        for c in candidates
        if c != word
    ]
    return sorted(rows)[:k]


# --- EXPERIMENTAL: the componentwise weighted distance --------------------
# Not used by anything: `distance` and `cost` above are untouched. Kept
# runnable because "why an angle instead of a weighted sum of components?" is
# a reasonable question about §14, and the answer is measured, not asserted.
# See SPEC §4, and `abugida._pure` for the derivation and the measurements.

weighted_cost = _pure.weighted_cost


def weighted_distance(w1: str, w2: str, lenient: bool = False) -> float:
    """`distance` with `weighted_cost` in place of `cost`. EXPERIMENTAL.

    Same DP, same heavy units, same epenthetic indels — only the
    substitution cost differs, so the comparison isolates the geometry. The
    DP runs in C when the extension is present: the substitution is a Python
    callable, which is exactly what `_edit`'s extension point is for.
    """
    from .iast import tokenize

    return _edit(tokenize(w1, lenient), tokenize(w2, lenient), weighted_cost)
