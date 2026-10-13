"""The BK-tree: exactness, and the bound that makes the relative threshold
queryable.

Kept small on purpose. The index is the pure-Python fallback, not the main
prefilter — measured, it is 30–150x slower than rapidfuzz at identical
recall (see the module docstring). What must be pinned is that it is EXACT,
because a prefilter that silently drops candidates is worse than a slow one.
"""

import random

import pytest

from abugida import distance
from abugida.distance import INDEL_WEIGHT
from abugida.index import BKTree, radius_for_relative
from abugida.phonotactics import pseudoword


@pytest.fixture(scope="module")
def corpus():
    rng = random.Random(20260801)
    return sorted({pseudoword(rng) for _ in range(600)})


def test_within_matches_an_exhaustive_scan(corpus):
    """The pruning follows from the triangle inequality, so it must lose
    nothing. This is the property the whole structure rests on."""
    tree = BKTree(corpus)
    for query in corpus[:25]:
        for radius in (0.3, 0.6, 1.0, 1.7):
            got = {w for _, w in tree.within(query, radius)}
            expected = {w for w in corpus
                        if distance(query, w, lenient=True) <= radius}
            assert got == expected, (query, radius)


def test_within_is_exact_across_a_triangle_violation():
    """The pruning rests on the word-level triangle inequality, which the
    metric satisfies since the heavy units, so `within` is exact by proof;
    this is the check against an exhaustive scan anyway.

    The triples are the ones that VIOLATED the inequality before the units
    (`d("makka","saṅgha")` was 2.262 against 2.065 through `magga`), kept
    because they are where an index error would show first. Queried at radii
    both below and above the disputed distance, the tree must return exactly
    what an exhaustive scan returns.

    The guard on the module's docstring: if the pruning ever starts losing
    candidates, this fails here rather than in an integration."""
    triples = [
        ("makka", "magga", "saṅgha"),
        ("attha", "aṭṭha", "cmthkhsā"),
        ("tatra", "tattha", "makka"),
    ]
    for q, middle, other in triples:
        for order in ([middle, other, q], [other, middle, q],
                      [middle, q, other], [q, middle, other]):
            tree = BKTree(order)
            for radius in (0.3, 0.5, 1.0, 1.5, 2.0, 2.1, 2.25, 2.3, 3.0):
                got = {w for _, w in tree.within(q, radius)}
                expected = {w for w in order
                            if distance(q, w, lenient=True) <= radius}
                assert got == expected, (q, order, radius)


def test_nearest_is_exact_across_a_triangle_violation():
    """`nearest` is `within` at an adaptive radius, so it inherits the same
    guarantee — and the same test."""
    corpus = ["makka", "magga", "saṅgha", "tatra", "tattha", "atha",
              "attha", "aṭṭha", "kamma", "khamma", "kata", "gata"]
    tree = BKTree(corpus)
    for q in corpus:
        for k in (1, 2, 3, 5, 8):
            got = [w for _, w in tree.nearest(q, k=k)]
            expected = [w for _, w in
                        sorted((distance(q, w, lenient=True), w)
                               for w in corpus if w != q)[:k]]
            assert got == expected, (q, k)


def test_results_come_back_sorted_by_distance(corpus):
    tree = BKTree(corpus)
    found = tree.within(corpus[0], 1.5)
    assert [d for d, _ in found] == sorted(d for d, _ in found)


def test_duplicates_are_ignored(corpus):
    tree = BKTree(corpus[:50] + corpus[:50])
    assert len(tree) == 50


def test_nearest_returns_k_closest(corpus):
    tree = BKTree(corpus)
    q = corpus[0]
    got = tree.nearest(q, k=5)
    expected = sorted((distance(q, w, lenient=True), w)
                      for w in corpus if w != q)[:5]
    assert [w for _, w in got] == [w for _, w in expected]


def test_radius_for_relative_covers_the_threshold():
    """The bound must not under-search: every word whose RATIO is within
    theta has to fall inside the absolute radius."""
    rng = random.Random(20260801)
    words = sorted({pseudoword(rng) for _ in range(400)})
    from abugida.iast import tokenize

    theta = 0.22
    for q in words[:20]:
        r = radius_for_relative(q, theta)
        nq = len(tokenize(q, lenient=True))
        for w in words:
            d = distance(q, w, lenient=True)
            nw = len(tokenize(w, lenient=True))
            if d / max(nq, nw) <= theta:
                assert d <= r, (q, w, d, r)


def test_radius_refuses_an_unbounded_theta():
    """Above the indel weight the length difference stops limiting the
    candidate's length, so no finite radius covers the threshold. Saying so
    beats silently returning too little."""
    with pytest.raises(ValueError, match="no finite"):
        radius_for_relative("kata", INDEL_WEIGHT + 0.01)
