"""A BK-tree over the phonological distance.

WHAT IT IS FOR, after measurement: the pure-Python fallback when rapidfuzz is
absent. It is **2.4× faster** than the length-window scan `Lexicon` falls
back to today (548 ms against 1,295 ms per query over DPD's 75k lemmas), and
exact rather than approximate.

WHAT IT IS NOT FOR: replacing rapidfuzz. That was the hypothesis this module
was built to test, and the test refuted it. Against the character prefilter
at three thresholds on DPD:

    θ      system      recall   cand/lemma   ms/query
    0.09   rapidfuzz    79.9%       1.89        15.0
    0.09   BK-tree      79.9%       1.89       470.3
    0.16   rapidfuzz    91.1%       8.63        14.9
    0.16   BK-tree      91.1%      10.69      1359.0
    0.22   rapidfuzz    95.3%      25.20        14.5
    0.22   BK-tree      95.3%      53.33      2167.1

Identical recall, equal or worse volume, and 30–150× slower. The reasoning
that motivated it — that a character prefilter must be dropping pairs the
metric would rank highly — was half right and already fixed elsewhere: the
pairs being lost (`nayati ~ neti`, distance ZERO once normalised) were lost
because the pool was built over RAW forms. `Lexicon(..., normalise=True)`
prefilters on the compared forms and recovers them; nothing was left for an
index to fix.

The timing failure is structural, and worth stating so nobody retries it. A
BK-tree prunes well at SMALL radii. Here the radii are large relative to the
spread of distances — 1.36 for θ=0.09 on a typical word — so most of the tree
falls inside the bound, it visits nearly everything, and it degenerates to a
scan with tree overhead on top.

HOW IT PRUNES. For a query q, a node n and a radius r, the triangle
inequality gives |d(q,n) − d(n,c)| ≤ d(q,c) for every descendant c, so any
subtree whose stored distance falls outside [d(q,n) − r, d(q,n) + r] cannot
hold a match and is skipped unvisited. This is the first thing in the package
to actually USE the metric guarantee that `distance` carries.

THE BOUND IS NOW A THEOREM. Since the heavy units (SPEC §9.4) every word has
one segmentation and `distance` is a true metric, so the pruning interval
above is sound and `within` is exact by proof. It was not always so: the
alignment transitions the units replaced broke the word-level inequality
(`d("makka","saṅgha")` was 2.262 against 2.065 through `magga`), and the
tree was exact then only by measurement. The account of why, kept because
`tests/test_index.py` still runs the old counterexample's words:

What made `within` exact even then was the DIRECTION of the failure, and it
is worth spelling out because it is not obvious. A descendant c is only skipped
when the stored distance d(n,c) falls outside [d(q,n) − r − w, d(q,n) + r + w],
i.e. when |d(q,n) − d(n,c)| > r + w. If c were a genuine match (d(q,c) ≤ r),
the triangle inequality would give

    |d(q,n) − d(n,c)| ≤ d(q,c) ≤ r  <  r + w

so a match can only be lost if the inequality fails by MORE than the bucket
widening w. Measured over the vocabulary where it does fail, it never does:
across every violating triple among 20 real Pāli words, the largest margin is
0.409, and no candidate at any radius up to 6.0 satisfies both "within the
radius" and "outside the pruning window". The widening (one bucket, 0.25 by
default) is what absorbs the rest.

The margin is therefore EMPIRICAL, not structural, which is exactly why the
exactness of this class rests on a test rather than on the theorem above:
`tests/test_index.py` checks `within` and `nearest` against an exhaustive
scan, including corpora built from the counterexample triples, and that test
is the guarantee. If the metric changes — a new transition, a recalibrated
indel — re-measure before trusting this docstring.

Distances are continuous, so children are bucketed by `resolution` rather
than keyed by integer distance as in the classical construction, and the
bound is widened by one bucket to compensate. Exactness is verified against
exhaustive scan in `tests/test_index.py`.

THE RELATIVE THRESHOLD NEEDS A BOUND, NOT A RADIUS. `Lexicon.variants(
relative=True)` cuts on d/max(len), which is NOT a metric and cannot be
queried directly. But it can be bounded: each token of length difference
costs at least one epenthetic indel, so a candidate satisfying d/n_c ≤ θ must
have n_c ≤ n_q · INDEL/(INDEL − θ) — for θ=0.22 that is 1.54·n_q — and
therefore d ≤ θ · 1.54 · n_q. `radius_for_relative` computes it, and
searching to that radius loses nothing.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple

from .distance import INDEL_WEIGHT, distance
from .iast import tokenize

#: Bucket width for the children of a node. Distances are continuous, so
#: they are grouped rather than used as exact keys.
RESOLUTION = 0.25


class _Node:
    __slots__ = ("word", "children")

    def __init__(self, word: str):
        self.word = word
        self.children = {}


def radius_for_relative(query: str, theta: float,
                        indel: float = INDEL_WEIGHT) -> float:
    """The absolute radius that safely covers a relative threshold.

    A candidate `c` passes `d/max(n_q, n_c) ≤ θ`. If `c` is the longer one,
    the length difference alone costs at least `(n_c − n_q)·indel`, so
    `(n_c − n_q)·indel ≤ θ·n_c`, giving `n_c ≤ n_q·indel/(indel − θ)`. The
    radius is then `θ·n_c` at that bound. Requires `θ < indel`; above it the
    length difference stops being limiting and no finite bound exists, so the
    caller is told rather than silently under-searching.
    """
    if theta >= indel:
        raise ValueError(
            f"theta {theta} exceeds the indel weight {indel:.4f}: no finite "
            "radius bounds the relative threshold. Search exhaustively."
        )
    n_q = max(1, len(tokenize(query, lenient=True)))
    return theta * n_q * indel / (indel - theta)


class BKTree:
    """Metric index over a word list. Build once, query many times."""

    def __init__(self, words: Iterable[str],
                 metric: Callable[[str, str], float] = None,
                 resolution: float = RESOLUTION):
        self._metric = metric or (lambda a, b: distance(a, b, lenient=True))
        self._resolution = resolution
        self._root: Optional[_Node] = None
        self._size = 0
        for w in words:
            self.add(w)

    def __len__(self) -> int:
        return self._size

    def add(self, word: str) -> None:
        if self._root is None:
            self._root = _Node(word)
            self._size = 1
            return
        node = self._root
        while True:
            d = self._metric(word, node.word)
            if d == 0.0 and word == node.word:
                return  # already present
            bucket = int(d / self._resolution)
            child = node.children.get(bucket)
            if child is None:
                node.children[bucket] = _Node(word)
                self._size += 1
                return
            node = child

    def within(self, query: str, radius: float) -> List[Tuple[float, str]]:
        """Every word within `radius`, as (distance, word).

        Exact: the pruning rests on the word-level triangle inequality,
        which `distance` satisfies since the heavy units (see the module
        docstring); `tests/test_index.py` also checks it against an
        exhaustive scan."""
        if self._root is None:
            return []
        out: List[Tuple[float, str]] = []
        stack = [self._root]
        while stack:
            node = stack.pop()
            d = self._metric(query, node.word)
            if d <= radius:
                out.append((d, node.word))
            # A child stored in bucket b sits at distance [b·res, (b+1)·res),
            # so widen the window by one bucket on the far side.
            lo = int((d - radius) / self._resolution) - 1
            hi = int((d + radius) / self._resolution) + 1
            for bucket, child in node.children.items():
                if lo <= bucket <= hi:
                    stack.append(child)
        out.sort()
        return out

    def nearest(self, query: str, k: int = 5,
                exclude_query: bool = True) -> List[Tuple[float, str]]:
        """The k nearest words, by expanding the radius until k are found.

        Starts at one elementary move and doubles. Cheaper than a full scan
        when the neighbourhood is dense, which for a real lexicon it is.

        `exclude_query` drops the query itself from the answer, which is
        right when the tree holds words. `Lexicon` passes False: its tree
        holds COMPARED forms, and under `normalise=True` two different words
        share one (saṃgha and saṅgha both compare as saṅgha), so dropping the
        query's form dropped its distance-zero partner with it.
        """
        radius = INDEL_WEIGHT
        for _ in range(8):
            found = [(d, w) for d, w in self.within(query, radius)
                     if not exclude_query or w != query]
            if len(found) >= k:
                return found[:k]
            radius *= 2
        return found[:k]
