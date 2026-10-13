"""Pure Python against the C core, on the operations the package exports.

`docs/c-core.md` quotes these numbers. The benchmark is here rather than
inline in the doc so the figures can be re-derived after any change: a claim
in prose has to point at something runnable (CLAUDE.md).

    python tools/benchmark.py           # the table in the doc
    python tools/benchmark.py --json    # the same numbers, machine-readable

What is measured, and how, matters as much as the numbers:

- **Both implementations, same work, same process.** The pure-Python side is
  `abugida._pure` called directly, never through `abugida.distance` — the
  delegating module switches to C when the extension is present, so a
  benchmark that imported normally would measure C twice and report a ratio
  of 1.0.
- **Tokenisation is measured on the words, not on raw strings only.** The
  metric's cost for a pair includes tokenising both words, so the honest
  comparison is the whole operation: `_pure.distance(w1, w2)` against
  `_c.distance(w1, w2)`, both from text. Tokenisation alone is reported
  separately because it is where a large share of the gain lives for short
  words.
- **`cost` is measured warmed.** The pure implementation caches it with
  `lru_cache`, so a cold loop measures the cache as much as the arithmetic;
  the loop primes every pair first and then measures. The C side has no cache
  and does not need one.
- **A lexicon sweep is measured through `Lexicon.search`**, which is the
  operation an integration actually runs, with the rapidfuzz prefilter
  disabled on both sides so the comparison is the metric and not the
  prefilter.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import timeit
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abugida import _pure  # noqa: E402
from abugida.alphabet import ALPHABET  # noqa: E402
from abugida.distance import USING_C  # noqa: E402
from abugida.iast import normalize  # noqa: E402

if USING_C:  # pragma: no cover - the branch depends on the build
    from abugida import _cabugida as _c
else:  # pragma: no cover
    _c = None

SEED = 20260801

#: Words of a few lengths, so the table shows how the ratio moves with the
#: word: a short pair is dominated by tokenisation and call overhead, a long
#: one by the O(n·m) inner loop.
SHORT = ("kamma", "khamma")
MEDIUM = ("dhammaniyāmaṃ", "dhammaniyamaṃ")
LONG = ("abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ",
        "abhidhammapiṭakapakaranassaṭṭhakathaṃ")


def words(n: int) -> list:
    """A fixed-seed sample of legal Pāli words of 3 to 12 tokens."""
    rng = random.Random(SEED)
    letters = [p.grapheme for p in ALPHABET]
    return ["".join(rng.choice(letters) for _ in range(rng.randint(3, 12)))
            for _ in range(n)]


def timed(fn, number: int) -> float:
    """Seconds per call, best of three runs — a laptop's first run is noise."""
    return min(timeit.repeat(fn, number=number, repeat=3)) / number


def bench_pair(name: str, a: str, b: str, number: int, results: dict) -> None:
    pure = timed(lambda: _pure.distance(a, b), number)
    c = timed(lambda: _c.distance(a, b), number)
    results[name] = {"python_us": pure * 1e6, "c_us": c * 1e6,
                     "speedup": pure / c}


def bench_tokenize(results: dict) -> None:
    sample = [SHORT[0], MEDIUM[0], LONG[0]]
    number = 20000
    pure = timed(lambda: [_pure.tokenize(normalize(w)) for w in sample], number)
    c = timed(lambda: [_c.tokenize(normalize(w)) for w in sample], number)
    results["tokenize (3 words)"] = {
        "python_us": pure * 1e6 / 3, "c_us": c * 1e6 / 3,
        "speedup": pure / c,
    }


def bench_cost(results: dict) -> None:
    """Warmed, on the pairs the table is calibrated over."""
    tokens = [p.grapheme for p in ALPHABET]
    pairs = [(a, b) for a in tokens for b in tokens]
    for a, b in pairs:  # prime the pure implementation's LRU cache
        _pure.cost(a, b)
    number = 2000
    pure = timed(lambda: [_pure.cost(a, b) for a, b in pairs], number)
    c = timed(lambda: [_c.cost(a, b) for a, b in pairs], number)
    results["cost (%d warmed pairs)" % len(pairs)] = {
        "python_us": pure * 1e6 / len(pairs), "c_us": c * 1e6 / len(pairs),
        "speedup": pure / c,
    }


def bench_levenshtein(results: dict) -> None:
    pure = timed(lambda: _pure.levenshtein(*MEDIUM), 20000)
    c = timed(lambda: _c.levenshtein(*MEDIUM), 20000)
    results["levenshtein (medium)"] = {
        "python_us": pure * 1e6, "c_us": c * 1e6, "speedup": pure / c,
    }


def bench_alignment(results: dict) -> None:
    """The receipt is a different shape of work: a full matrix and a
    traceback, not rolling rows — the operation the Python implementation had
    to write a second time and the C one gets for free."""
    pure = timed(lambda: _pure.alignment(*SHORT), 5000)
    c = timed(lambda: _c.alignment(*SHORT), 5000)
    results["alignment (short)"] = {
        "python_us": pure * 1e6, "c_us": c * 1e6, "speedup": pure / c,
    }


def bench_scan(results: dict, size: int = 2000) -> None:
    """The bulk operation: one query against a lexicon, distance only, no
    prefilter (the C core has none and neither has `_pure`)."""
    lexicon = words(size)
    query = lexicon[0]
    pure = timed(lambda: sorted(_pure.distance(query, w) for w in lexicon), 1)
    c = timed(lambda: sorted(_c.distance(query, w) for w in lexicon), 1)
    results["scan %d words (1 query)" % size] = {
        "python_us": pure * 1e6, "c_us": c * 1e6, "speedup": pure / c,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true",
                    help="print the numbers as JSON and nothing else")
    ap.add_argument("--scan", type=int, default=2000,
                    help="lexicon size for the bulk scan (default 2000)")
    args = ap.parse_args()

    if not USING_C:
        print("the C extension is not built: nothing to compare against")
        return 1

    results: dict = {}
    bench_tokenize(results)
    bench_cost(results)
    bench_pair("distance (short, 5x6 tokens)", SHORT[0], SHORT[1], 20000,
               results)
    bench_pair("distance (medium, 13x13)", MEDIUM[0], MEDIUM[1], 5000,
               results)
    bench_pair("distance (long, 39x37)", LONG[0], LONG[1], 2000, results)
    bench_levenshtein(results)
    bench_alignment(results)
    bench_scan(results, args.scan)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    print(f"{'operation':34} {'python':>12} {'C':>12} {'speedup':>9}")
    print("-" * 70)
    for name, row in results.items():
        print(f"{name:34} {row['python_us']:>10.2f} µs "
              f"{row['c_us']:>10.2f} µs {row['speedup']:>8.1f}×")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
