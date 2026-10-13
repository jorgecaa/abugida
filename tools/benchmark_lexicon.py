"""What the Lexicon's token cache is worth, measured at the entry point.

Not at the scoring loop, which is where the change is and where the number
flatters it: the first version of this measurement reported 2.97x for the
loop and the real, end-to-end gain is **1.36x**, because `_pool` is 41% of a
search and the distance computation itself is most of the rest. Slicing a
sub-part of a call and quoting that ratio is how this project has twice sent
itself the wrong way; this script reports both numbers so the difference is
visible.

    python tools/benchmark_lexicon.py

The lexicon is synthetic and seeded, so the figure is reproducible without the
DPD database. It is a shape, not a corpus: a real lexicon has different word
lengths and a different pool hit rate.
"""

import random
import timeit

from abugida.alphabet import ALPHABET
from abugida.lexicon import Lexicon

#: Words in the synthetic lexicon, and `search`'s default pool.
SIZE = 2000
POOL = 200
QUERIES = 30
REPEATS = 40
SEED = 20260801


def _lexicon(size=SIZE):
    rng = random.Random(SEED)
    letters = [p.grapheme for p in ALPHABET]
    return [
        "".join(rng.choice(letters) for _ in range(rng.randint(4, 12)))
        for _ in range(size)
    ]


def _per_call(fn, repeats=REPEATS):
    """Milliseconds per call of `fn`, which is one operation.

    Separate from the search timings below, which time a LIST of queries and
    must divide by it: the first version of this divided a single operation by
    the number of queries and reported `_pool` as 1% of a search when it is
    41%."""
    return timeit.timeit(fn, number=repeats) / repeats * 1000


def _per_query(fn, queries, repeats=REPEATS):
    """Milliseconds per query, for a callable that runs the whole list."""
    return timeit.timeit(fn, number=repeats) / repeats / len(queries) * 1000


def main():
    lex = Lexicon(_lexicon())
    queries = lex._words[:QUERIES]
    lex.search(queries[0])  # build the cache, which is paid once per lexicon

    cached = _per_query(lambda: [lex.search(q, k=5, pool=POOL) for q in queries],
                        queries)

    # Without the cache: `_compared_tokens` hands back the string, which is
    # exactly what `distance` was given before the cache existed.
    original = Lexicon._compared_tokens
    Lexicon._compared_tokens = lambda self, form: form
    lex._tokens_of = None
    try:
        uncached = _per_query(
            lambda: [lex.search(q, k=5, pool=POOL) for q in queries], queries)
    finally:
        Lexicon._compared_tokens = original

    # And the sub-part, for the contrast that matters.
    lex._tokens_of = None
    lex.search(queries[0])
    pool_ms = _per_call(lambda: lex._pool(queries[0], POOL), repeats=200)
    candidates = lex._pool(queries[0], POOL)
    from abugida.distance import distance

    qt = lex._compared_tokens(lex._as_compared(queries[0]))
    score_cached = _per_call(
        lambda: sorted(
            (distance(qt, lex._compared_tokens(lex._compare_of[w]), lenient=True), w)
            for w in candidates if w != queries[0]),
        repeats=200)
    score_plain = _per_call(
        lambda: sorted(
            (distance(lex._as_compared(queries[0]), lex._compare_of[w],
                      lenient=True), w)
            for w in candidates if w != queries[0]),
        repeats=200)

    print(f"Lexicon.search, {SIZE} words, pool {POOL}, {QUERIES} queries")
    print()
    print(f"  candidate prefilter (_pool)   {pool_ms:7.3f} ms   "
          f"{pool_ms / uncached * 100:3.0f}% of a search")
    print(f"  scoring, strings              {score_plain:7.3f} ms   "
          f"{score_plain / uncached * 100:3.0f}%")
    print(f"  scoring, cached tokens        {score_cached:7.3f} ms   "
          f"{score_cached / uncached * 100:3.0f}%")
    print()
    print(f"  the sub-part                  {score_plain / score_cached:7.2f}x")
    print(f"  THE WHOLE CALL                {uncached / cached:7.2f}x   "
          f"({uncached:.3f} ms -> {cached:.3f} ms per query)")
    print()
    print("  The two differ because a search is not its scoring loop. Quote the")
    print("  second number: it is the one a caller experiences.")


if __name__ == "__main__":
    main()
