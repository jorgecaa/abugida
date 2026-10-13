# abugida's C core

The metric is implemented in C. This document is what a C consumer needs, and
what a Python integrator needs to know about the arrangement — the Python API
is unchanged, and `docs/comparator.md` remains the integration guide for it.

```
csrc/abugida.h          the public C API: types, functions, guarantees
csrc/abugida.c          the implementation: tokeniser, DP, traceback, pipeline
csrc/abugida_myers.c    the bit-parallel Levenshtein kernel (see below)
csrc/abugida_tables.h   GENERATED — vocabulary (126 tokens, 41 graphemes), ids,
                        derived constants
csrc/abugida_tables.c   GENERATED — the substitution-cost matrix, 86 x 86
csrc/Makefile           libabugida.a, and the C test suite
abugida/_cabugida.pyx   the Cython binding: the C core as the Python package
abugida/_pure.py        the pure-Python reference (and the fallback)
tools/generate_c_tables.py   derives the tables from the Python source
tools/benchmark.py      the numbers in "Speed" below
tests/c/test_abugida.c  the core's own test suite, no Python in the process
```

## Why it exists, and what it is not

It is the same metric, not a second one. The substitution cost is still the
truncated angular distance between the 14-dimensional embeddings of SPEC §4,
the indel weights are still derived by the triangle inequality, and the DP is
still the same recurrence over the same heavy units. What changed is where the
arithmetic happens.

It is **not** a re-derivation. Every constant in `csrc/abugida_tables.c` is
computed by `tools/generate_c_tables.py`, which imports the Python package and
calls the reference implementation — `cost` once per pair, `phonology.
assimilate` once per grapheme, `INDEL_WEIGHT` and `_GEMINATE_BASES` as they
are derived at import time. No number in the C core was chosen by hand, which
is the project's discipline (CLAUDE.md) applied to a second language: a
hand-typed C table is a tuning waiting to diverge.

## Using it from C

```c
#include "abugida.h"   /* pulls in the generated vocabulary too */

abugida_token a[64], b[64];
abugida_word wa = ABUGIDA_WORD(a, 64);      /* no allocation */
abugida_word wb = ABUGIDA_WORD(b, 64);
double d;

abugida_word_from_text(&wa, "kamma", 5, 0, NULL);
abugida_word_from_text(&wb, "khamma", 6, 0, NULL);
abugida_word_distance(&wa, &wb, &d);        /* 0.4697... */
```

Build it:

```bash
make -C csrc                  # build/libabugida.a
cc -I csrc myprog.c build/libabugida.a -lm
make -C csrc check            # the core's own test suite
```

The contract, in the order it matters:

- **Input is NFC-normalised, lowercase IAST.** Unicode normalisation is the
  one thing deliberately left out: NFC composition and case folding need the
  Unicode character database, and vendoring it to compute a distance would be
  a much larger dependency than the metric. The Python binding normalises
  before it calls; a C caller does the same, or stores its words that way.
  Two concessions are made inside the tokeniser because they need no Unicode
  data: ASCII uppercase is folded, and the ṁ spelling of the niggahīta is
  accepted.
- **Errors are return codes**, never exceptions and never output on stderr.
  `ABUGIDA_OK` is 0, so `if (abugida_distance(...) != ABUGIDA_OK)` reads
  correctly. A failing tokenisation reports the byte offset of the offending
  character.
- **Nothing is global.** Every function is reentrant; there is no cache to
  warm and no state to reset. The DP uses stack storage for words up to
  `ABUGIDA_STACK_TOKENS` (64) tokens and the heap beyond that.
- **Memory is the caller's**, except where a function says otherwise
  (`abugida_word_alloc`, `abugida_word_align`, the `abugida_string` helpers).

### The token vocabulary

`abugida.h` includes the generated `abugida_tables.h`, which is where the
token ids live — `ABUGIDA_TOK_K`, `ABUGIDA_TOK_T_DOT_H_T_DOT_H` and the rest,
named in ASCII so any compiler and any terminal can read them. The vocabulary
has three groups, and the boundaries are load-bearing:

| ids | what | reachable how |
|---|---|---|
| `[0, ABUGIDA_NPLAIN)` | the 41 sounds of Pāli | tokenisation |
| `[ABUGIDA_NPLAIN, 123)` | the 82 heavy units: 42 geminates (`kk`, `tth`, `ṭhṭh`…) and 40 homorganic nasal+stop clusters (`nt`, `ṅkh`, `ṃgh`…) | only through the DP's segmentation of a word into units |
| `[123, ABUGIDA_NTOKENS)` | the Sanskrit phonemes `ś ṣ ṛ` | only through lenient tokenisation |

The heavy units are *why* degemination costs 0.470 rather than a full
deletion: `attha` is `a tth a` once segmented, and `tth` against `th` is the
weight gap alone (the LENGTH dimension, consonant length), its halves `t`/`th`
against `th`/`th` costing no more than that.

The Sanskrit phonemes are the reason lenient mode is not just typo tolerance:
`ṣ` against `s` costs 0.460 because Pāli merged all three sibilants into `s`,
so Sanskrit input is *priced* rather than absorbed. A genuine typo (`q`, `*`)
is opaque: cost 1 against everything, 0 against itself.

### Costs, and the extension point

`abugida_cost` and `abugida_indel` are the two costs the core knows.
`abugida_edit` takes function pointers instead, which is how the Python
binding offers the same DP to the experimental `weighted_distance` variant
(SPEC §4) without a second implementation of the recurrence:

```c
double my_sub(abugida_token a, abugida_token b, void *ctx);

abugida_edit(a.tok, a.n, b.tok, b.n, my_sub, NULL,
             abugida_indel_derived, NULL, &out);
```

Two adapters are provided for the costs this library is about —
`abugida_sub_phonological` with `abugida_indel_derived` is the metric,
`abugida_sub_flat` with `abugida_indel_flat` is Levenshtein over the same
tokenisation. `abugida_word_levenshtein` is the second pair with the heavy
units switched off, which is why Levenshtein stays the *fair* baseline:
`kh` counts as one letter in both measures.

### Opaque tokens, and the two bugs they hid

`lenient=True` turns a character outside the inventory into an OPAQUE token:
cost 1 against every token, 0 against itself, so a search frontend never
raises. The token is a signed 16-bit id with the marker `ABUGIDA_NO_TOKEN`
at -1, which leaves slots 1..32766 — 15 bits — where Unicode has 21. Some
collapsing is therefore forced, and the only real question is which
characters share a slot.

The answer is the character's UTF-8 length, in the two high bits:

| category | codepoints | slots | exact? |
|---|---|---|---|
| 0 (1 byte) | U+0000 – U+007F | `cp` | exact |
| 1 (2 bytes) | U+0080 – U+07FF | `0x80 + (cp - 0x80)` | exact |
| 2 (3 bytes) | U+0800 – U+FFFF | `0x800 + ((cp - 0x800) % 8192)` | folds within itself |
| 3 (4 bytes) | U+10000 – U+10FFFF | `0x4000 + ((cp - 0x10000) % 8192)` | folds within itself |

Two characters of different byte-length can never collide, so no Latin letter
is ever confused with a Cyrillic one, nor either with a CJK ideograph — and
categories 0 and 1 are injective, which covers every character a Pāli word or
a web form can contain, combining marks included. Within categories 2 and 3
the folding is one collision per 8192 codepoints.

What the folding costs is exactly one thing: `levenshtein` reports 0 instead
of 1 for two DIFFERENT characters that share a slot. `distance` is unaffected,
because an opaque token costs 1 against everything but itself either way.

Three bugs lived here, and the differential harness found all three:

1. **The first scheme truncated the codepoint's low bits**, so
   `levenshtein("a", "\u00e9", lenient=True)` returned 0: 'a' and a two-byte
   character landed on the same slot after the mask. Distinguishing them is the
   whole point of the scheme above.
2. **A slot above 32766 wrapped to a POSITIVE token**, which is not an opaque
   token at all but a collision with a real id. The astral band sat at 40960,
   so an emoji was priced as a real grapheme. The band edges are now stated
   arithmetically in the comment and asserted in the function.
3. **The Myers kernel indexed its pattern table with a NEGATIVE token id** —
   opaque tokens are negative by construction. That read is usually still
   inside the array, so it was silently wrong rather than a crash, and
   `tests/c/test_myers.c` never saw it because its corpus is all real token
   ids. The kernel now declines any word whose tokens are not indexable, and
   the DP answers it; `test_opaque_tokens_are_refused` pins the case with the
   real encoding.

The lesson is worth stating plainly, because it is the reason
`tools/differential.py` exists: **three of these were invisible to suites that
only ever feed the metric valid Pāli.** The C suite, the parity fixture and the
benchmark all pass with a broken lenient path, because none of them mistypes a
character. A port is not verified by the inputs its author thought of.

### One kernel, compiled once per instruction set

`csrc/abugida_myers.c` is built three times from the same source — `c`, `sse2`
and `avx2` — differing only in the `-m` flags and in the macro that renames
their symbols. `abugida.c` holds a dispatcher: `CPUID` picks the fastest the
CPU supports, `ABUGIDA_IMPL` (or `abugida_impl_select`) forces one, and
`abugida_impl_name` says which is answering. The portable variant is always
compiled and is the fallback on any target without the others.

**They run at the same speed, and that is worth knowing rather than
assuming.** Measured with `make -C csrc bench` on an i5-7600K:

| variant | kernel ns/pair | entry ns/pair | instructions |
|---|---|---|---|
| `c` | 75.4 | 78.6 | 129 |
| `sse2` | 75.1 | 78.3 | 129 |
| `avx2` | 74.6 | 77.5 | 106 |

The AVX2 build is a different binary — BMI2 shifts, 106 instructions against
129 — and about 1% faster, which is the noise floor. The recurrence is a
serial dependency chain, so its latency is the chain and not the instruction
count: there is no vector to exploit. The dispatcher exists so that a
hand-written kernel has somewhere to go and a test that walks it, not because
these three differ.

`make -C csrc check IMPL=1` builds with the C variant alone and passes; that is
the configuration a target without SSE2 or AVX2 gets, and the one that proves
the fallback rather than asserting it.

### Two kernels, for one quantity, checked against each other

`levenshtein` counts edits, so it is computable 64 cells at a time inside
machine words: `csrc/abugida_myers.c` carries a DP row as two bit-vectors and
steps it with four bit operations (Myers 1999). The weighted `distance` cannot
use that — real-valued costs mean adjacent cells do not differ by ±1 — which
is why this is the one function with two kernels and why
`docs/asm-plan.md` spends its effort here.

The choice between them is a property of the INPUT, not of the machine: the
kernel is exact when the shorter word has at most 64 tokens (the bit-vector is
a DP row, so the shorter side is the one that has to fit) and declines above
that with `ABUGIDA_MYERS_NOT_APPLICABLE`, which `abugida_word_levenshtein`
checks before falling through to the DP. Both kernels stay compiled, so
building without `-DABUGIDA_USE_MYERS` is a complete and correct library.

Two kernels for one quantity is exactly the arrangement this project refuses to
accept silently for the weighted distance, so it is checked three ways:
`tests/c/test_myers.c` compares them against each other and against an
independent Wagner–Fischer written in the test, over every pair of a token
corpus plus the 64/65 boundary and a 200-token word only the DP can answer;
`tests/test_c_parity.py` compares the public function against the pure-Python
reference over the whole corpus; and `tools/differential.py` compares the two
implementations as functions.

Measured (through the binding, and in the C suites): 8× to 53× on
the kernel for the benchmark pairs, 4.9× on a 500-word lexicon sweep — the
workload that actually consumes `levenshtein`, as the baseline in the
evaluation scripts — and inside the noise on a single short call, where the
Cython call itself is the floor. Careful with the word "tokenisation" here:
the C scanner is 390 ns for the longest word in the fixture, while a single
`Tokens.from_text("a")` costs 233 ns from Python. The floor is the boundary,
not the scan.

### The recurrence is written once

`abugida_edit` (rolling rows) is the only place the DP is written.
`abugida_word_align` computes the same recurrence over a full matrix for the
traceback, and reports the answer by reading the last row — the same cell
`abugida_edit` returns, not a recomputation. The Python package needed a test
(`test_alignment_conserves_the_distance`) to hold its two implementations
together; here they cannot drift, and the C suite checks the totals agree
anyway.

## Using it from Python

Nothing changes:

```python
from abugida import distance, alignment, Lexicon
distance("kamma", "khamma")     # 0.470, computed in C
```

`USING_C` in the module `abugida.distance` reports which implementation
answered (`from abugida.distance import USING_C`; the attribute
`abugida.distance` is the function, which shadows the submodule of the same
name, so `import abugida.distance as d` binds the function). When the
extension is absent — a source checkout with no compiler — the pure-Python
reference in `abugida._pure` answers instead, with the same values, so the
package degrades to what it was before rather than failing.

`abugida._cabugida` is the binding, and is private: it exposes token ids and
the raw DP, which an integrator has no reason to use. Two of its extension
points are worth knowing about because they exist for a reason:

- `edit(tokens1, tokens2, substitution, indel)` runs the C DP with Python
  callables for the costs. `distance._edit` adapts the string signature
  `eval/` scripts use; `weighted_distance` is the caller that needs it.
- `alignment` returns the same operations the Python API always has, with the
  costs summing exactly to `distance`.

## Tests, and how the two implementations are held together

Seven checks, each catching something the others cannot:

| check | what it proves |
|---|---|
| `tests/test_c_parity.py` | the C core and the Python reference return the **same doubles** (bit for bit on Linux, within 1e-12 where the C library rounds `acos` differently): the cost table over all 15,876 ordered token pairs, the tokeniser over every grapheme and grapheme pair, `distance`/`levenshtein`/`alignment` over a fixed-seed corpus, and the two pipeline functions |
| `tests/c/test_abugida.c` | the metric is **right**: the published scale as values, the metric axioms over the whole vocabulary, degemination, the epenthetic weights, the sandhi pipeline, and 4,131 pairs the generator wrote from the Python implementation (2,049,213 assertions, **no Python in the process**) |
| `tests/c/test_edge_cases.c` | the library is **sound**: empty words, NULL arguments, words past the stack threshold, broken UTF-8, alignment invariants, and a **leak check** that runs each operation thousands of times against the allocator's own accounting (8,797 assertions) |
| `tests/c/test_bounded.c` | the bounded DP agrees with the plain one — every pair at every bound, a pool-shaped sweep, and three wrong versions of the early cut pinned |
| `tools/differential.py` | the two are the same FUNCTION, not merely equal on examples: same **domain** (every input either succeeds in both or raises the same exception type in both) and same **range** (same types, same shapes, same doubles) over 3,878 inputs and ~102,000 comparisons |
| `tools/generate_c_tables.py --check` | the committed tables are **not stale** relative to the Python definitions |
| the existing 389-test suite | the package's behaviour is unchanged: it now runs against the C core |

### Installing the C core, verified end to end

A source tree that builds is not a package that installs, and the difference
is where this arrangement breaks. Both halves are checked, from an sdist in a
clean virtual environment:

```bash
python -m build --sdist
pip install dist/abugida-0.1.0.tar.gz      # in a fresh venv
python -c "from abugida.distance import USING_C; print(USING_C)"   # True
```

- **The C core builds with no Python in the process**: `make -C csrc check`
  runs all four suites inside the unpacked sdist (2,049,213 + 8,797 + 2,724
  + 12,303 checks, 0 failures).
- **A C consumer links it**: `make -C csrc` produces `build/c/libabugida.a`,
  and a 30-line program against `csrc/abugida.h` returns
  `0.96047433597865872` for `dhammaniyāmaṃ`/`dhammaniyama` — the same double
  the Python binding returns, which is the whole point of the arrangement.
- **The generated tables are fresh in the sdist**:
  `python tools/generate_c_tables.py --check` says so there too.

**Two things in `setup.py` are load-bearing for that, and both were found by
installing rather than by building in place:**

1. **`sources` and `depends` must be RELATIVE to `setup.py`.** setuptools
   refuses absolute ones outright — "setup script specifies an absolute
   path" — and the failure only appears when the package is installed, not
   when `build_ext --inplace` runs from the project root.
2. **`include_dirs` has no such rule, and should be absolute.** A relative
   `-Icsrc` resolves against the COMPILER's working directory, which under
   pip is a temporary build tree, so the header is not found. The two rules
   point in opposite directions and the error messages do not say so.

The kernel variants are compiled the same way through `setup.py` as through
`csrc/Makefile`, from one source, with the instruction-set flags probed
rather than assumed: an installed package reports `['c', 'sse2', 'avx2']` on
this machine and would report `['c']` on a target without the others.

### What "the two are mirrors" is verified to mean

Agreement on examples is not agreement on functions. The claim the C core
makes is stronger — it is the SAME function — and that decomposes into two
things a value comparison cannot see:

- **the domain**: for every input, either both raise or neither does, and when
  they raise it is the same exception type. A port that is stricter than its
  reference breaks callers that relied on lenient behaviour; one that is
  looser returns a number where the reference raised.
- **the range**: same types, same shapes, same doubles. Bit for bit on the
  platform the tables are generated on (Linux, glibc): the C table holds the
  doubles the generator computed there. Elsewhere the C core still returns
  those same doubles, but the pure-Python reference recomputes each cost with
  the platform's `acos` and `sqrt`, which macOS and Windows round differently
  in the last bit (up to 3 ulp, measured on the CI runners), so
  `tests/test_c_parity.py` and `generate_c_tables.py --check` compare doubles
  to within 1e-12 — the traceback's tie tolerance.

`tools/differential.py` runs both over 3,878 inputs and ~102,000 comparisons
and reports zero disagreements. Three real bugs lived in the gap between
"agrees on the examples" and "is the same function", and none of them was
visible to the existing tests, because **every one of those tests used
lowercase input**:

1. **`distance`, `levenshtein` and `alignment` did not normalise.**
   `distance("Bh", "bh")` returned 1.34 where the reference returns 0.0, and
   `alignment` split `Bh` into `b` + `h`. The C core's contract is to receive
   NFC-normalised lowercase IAST, and the delegating wrappers were passing
   raw strings; the fix normalises at the one point where tokens enter the
   binding, which every function inherits.
2. **The C scanner skipped ASCII whitespace only.** A non-breaking space out
   of a pasted web page tokenised as mojibake in one implementation and was
   dropped in the other. The set is now derived from Python —
   `[c for c in map(chr, range(0x110000)) if c.isspace()]` — and hard-coded
   as a table with that expression in the comment.
3. **An opaque token stored the character's first BYTE**, so a single
   mistyped two-byte letter cost 2.0 instead of 1.0 and came back as two
   Latin-1 characters. It now carries the CODEPOINT, and the scan advances by
   the whole character. Above U+0800 the 11 bits that fit alongside the
   marker truncate — documented, and identical on both sides.

Two of the three were differences in the DOMAIN rather than the values, which
is why `tests/test_c_parity.py` now has `test_the_two_implementations_accept_
the_same_inputs` and `..._return_the_same_values` over a curated set of 39
inputs: the cheap version of the differential run, in CI.

The mirror is not free, and it is worth naming the price: normalising on entry
cost 20–25% of the short-pair time until `_canonical` learned to detect the
already-normal input and skip the work. The alternative — a faster function
that answers differently from its reference on uppercase input — is not a
trade this port gets to make.

### The triangle inequality, and how it came to hold

`distance` is a true metric over all words, the empty one included. It was
not when the C core was written, and the C work is where the failure was
found:

```
d("makka", "saṅgha") = 2.262374                        (before 2026-10-13)
  > d("makka", "magga") + d("magga", "saṅgha") = 2.064786
```

The cause was the geminate alignment transitions (2:1, 1:2, 2:2): each
comparison could read a doubled pair as one long consonant or as two letters,
and a middle word read both ways made the detour cheaper (42 violations in
10,648 triples over 22 words, none with the transitions off; the empty word
failed too, `d("kamma","")` against the path through `"a"`). The pure-Python
reference returned the same numbers, so it was the metric's, not the port's.
`eval/triangle_geminates.py` traces every violation to that cause and
measures the repairs that keep per-comparison segmentation — raising the unit
costs (it is removing the transitions), closing them under composition (50 of
86 remain) — and none works.

What replaced them is one segmentation per word. `segment_units` reads each
word once, left to right, into letters and heavy units (geminates and
homorganic nasal+stop clusters, the niggahīta included before a stop), using
the same pair table the transitions used; `dp_plain` then runs the plain
recurrence over the units, and `abugida_word_align` traces the same matrix.
A unit is priced by its halves — the max of the first-half cost, the
second-half cost and the weight gap — and its indel is derived. The
inequality then follows from three token-level conditions, each verified
exhaustively by the Python suite over all 126 tokens: the cost is a metric
(2,000,376 triples), `indel(g) ≤ cost(g,h) + indel(h)` and
`cost(g,h) ≤ indel(g) + indel(h)` (15,876 pairs). `tests/c/test_edge_cases.c`
checks it on words chosen to break the old DP and pins the old
counterexample's three legs, now `1.631187 ≤ 0.469738 + 1.343898`.

**BK-trees, vp-trees and hierarchical clustering are sound at any radius**,
and the `index.py` BK-tree is exact by proof (before, it was exact by a
measured margin: the inequality never failed by more than its bucket
widening, 0.409 at worst). Consumers that only threshold — `Lexicon.search`,
`Lexicon.variants`, everything measured in `docs/comparator.md` — never
assumed the inequality at all.

The parity test compares *exactly*, not approximately. That is possible
because the generator emits C99 hex-float literals, which round trip, and
because the DP accumulates in the same order as its Python counterpart. Two
things had to be matched deliberately and are worth recording, because both
look like details and neither is:

- **The traceback's branch order and its 1e-12 tolerance.** Several paths
  through the matrix usually cost exactly the same, so which one is reported
  is a decision, not a derivation. Python compares to within `1e-12`; the C
  code does too, so a pair with two optimal scripts yields the same script in
  both — and `edit_tag` publishes whichever comes out.
- **The 1:1 substitution at every column.** The C recurrence originally
  guarded it (`j >= 2`, translated from Python's `j >= 2` in 0-based terms)
  and that dropped the diagonal at the first column, which let a one-token
  word pass for a two-token one. The parity fixture caught it; no single
  property test did.

## Speed

`tools/benchmark.py`, CPython 3.14, GCC 16, one core of a laptop. Both sides
in one process, the Python side calling the reference directly.

| operation | Python | C core | speedup |
|---|---|---|---|
| tokenise 3 words (5, 13, 39 tokens) | 3.1 µs | 2.5 µs | 1.3× |
| `cost`, 1,681 warmed pairs | 0.10 µs | 0.19 µs | 0.5× |
| `distance`, 5 × 6 tokens | 16 µs | 0.90 µs | **18×** |
| `distance`, 13 × 13 tokens | 59 µs | 2.7 µs | **22×** |
| `distance`, 39 × 37 tokens | 392 µs | 13.6 µs | **29×** |
| `levenshtein`, 13 × 13 | 42 µs | 2.2 µs | 19× |
| `alignment`, 5 × 6 | 33 µs | 1.7 µs | 20× |
| one query against 2,000 words | 81 ms | 5.0 ms | 16× |

Three things to read off it rather than just the ratios.

**The gain grows with the word, because the inner loop is what moved.** A
short pair is dominated by argument checking and marshalling, which no
implementation can avoid; a 39-token compound is almost all DP, and there the
ratio reaches 29×. The run-to-run spread on the short row is real — 14× to 18×
across runs on this machine — so read the long row as the ratio and the short
one as a floor.

**The binding normalises, and pays for it only when there is something to
do.** A word that is already NFC and lowercase — which is what a lexicon
holds, and what a caller passes on every call after the first — is returned
by `_canonical` unchanged after an `isascii()`/`islower()` check, so the
common path costs a method call. Normalising unconditionally on entry cost
20–25% of the short-pair figure (0.82 µs to 1.20 µs) before that check
existed; it is what buys the guarantee that `distance("Bh", "bh")` is 0.0 in
both implementations instead of 1.34 in one of them.

**`cost` is SLOWER in C, and that is the honest number.** The pure
implementation caches it with `lru_cache`, so the 0.10 µs is a dictionary
lookup, and the C side pays two byte conversions to reach a table. It is
still the right trade: `cost` is called once per DP cell in the *pure*
implementation, but in C the table is read directly and `cost` is only ever
called by a user. Per-pair documentation figures in `docs/comparator.md`
(~76 µs) were measured on Pāli-sized words with the pure implementation and
remain the honest comparison for that implementation.

**Tokenisation is barely faster, and the reason is not the scanner.** The
Python side's 2.7 µs per word is mostly `unicodedata.normalize`, which stays
in Python by design. What the C scan buys is that it does not get slower on
long words.

## What this buys an integrator

The consequence is not the constant factor but that the metric stops being the
part you design around.

**A re-rank is now cheaper than the prefilter that feeds it.** The recipe in
`docs/comparator.md` is "rapidfuzz prefilter, phonological re-rank", measured
at ~15 ms per query over the full DPD lexicon because the re-rank was the
expensive half. At 18–32× the metric, the re-rank of a 200-candidate pool is
well under a millisecond, and the balance tips: the prefilter is now what a
query costs.

**A full sweep is bounded by the prefilter, not by the metric.** Measured on a
500-lemma sample of 6–12-token words with `Lexicon(words, normalise=True)`,
`variants()` runs at **0.37 ms per lemma** — of which the metric is 0.004 ms
(500 pairs in 2 ms, against 52 ms in pure Python). Do not read that as "a 75k
sweep takes half a minute": on a synthetic lexicon the rapidfuzz prefilter
returns far fewer true neighbours than a real one does, and `variants` scores
whatever the prefilter offers. What it does say is that the metric has stopped
being the limiting term, which is the claim `docs/comparator.md`'s
"~12-minute batch" was making about the pure implementation.

Both figures are reproducible on your own hardware with the commands above and
`tools/benchmark.py`; the second is a single script's worth of code, so if you
depend on the sweep time, measure your own lexicon rather than quoting this
one.

The recall figures do not change. They are properties of the metric, not of
its implementation, and `tests/test_c_parity.py` is what makes that statement
checkable rather than hopeful — including the two published evaluations that
run without a database at all: `tests/test_battery.py` (30/30, 167 distinct
values over 190 pairs) and `eval/hard_battery.py` (50.9% [49.1, 52.7] over
3,000 triples), both of which reproduce their documented numbers exactly
against the C core.
