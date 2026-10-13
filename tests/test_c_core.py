"""Build the C core and run its own test suite, from pytest.

`tests/c/test_abugida.c` is the core's standalone check: no Python in the
process, only `csrc/abugida.c`, the generated tables and libm. It is worth
running for the reason the C version exists at all — a C consumer links those
files — and it is the only test in the project that would catch a bug in the
library's C API rather than in the binding.

The compile is a `make` away, so this test is skipped when there is no
compiler: `tests/test_c_parity.py` covers the binding, and a machine without
a toolchain cannot check this, which is a fact to report rather than to fail
on.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSRC = ROOT / "csrc"
PAIRS = ROOT / "tests" / "c" / "pairs.txt"

pytestmark = pytest.mark.skipif(
    shutil.which("make") is None or shutil.which("cc") is None,
    reason="no C toolchain (make and cc) to build the core with",
)


def test_the_c_core_passes_its_own_tests():
    """`make -C csrc check`: build the static library and run all THREE C
    suites.

    `test_abugida.c` checks that the metric is right — the published scale, the
    metric axioms over the whole vocabulary, the heavy units, the
    epenthetic weights, the sandhi pipeline, and every pair in the fixture the
    generator wrote from the Python implementation.

    `test_edge_cases.c` checks that the library is sound — empty words, NULL
    arguments, words past the stack threshold, broken UTF-8, a leak check that
    runs each operation thousands of times against the allocator's own
    accounting, and the triangle inequality over words chosen to break the
    old geminate transitions (it holds since the heavy units; the old
    counterexample's legs are pinned there).

    `test_myers.c` checks the one place the library keeps TWO kernels for one
    quantity: the bit-parallel Levenshtein (`docs/asm-plan.md`, phase 0) and
    the dynamic program it falls back to. Every pair of a token corpus, both
    orders, the 64-token boundary, and a word long enough that only the DP can
    answer.

    `test_bounded.c` checks the bounded DP against the plain one — every pair
    at every bound, a pool-shaped sweep, and the argument contract. It pins
    three wrong versions of the early cut, each of which looked reasonable and
    each of which got real pairs wrong."""
    assert PAIRS.exists(), (
        "tests/c/pairs.txt is missing: run python tools/generate_c_tables.py"
    )
    result = subprocess.run(
        ["make", "-C", str(CSRC), "check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, (
        f"the C core's own test suite failed:\n{result.stdout}\n{result.stderr}"
    )
    assert "0 failures" in result.stdout, result.stdout
    # All four suites ran and every one reported no failures.
    assert result.stdout.count("0 failures") == 4, result.stdout
