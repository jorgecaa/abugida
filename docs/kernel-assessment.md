# Could `distance` and `levenshtein` be written in assembly?

The question was whether the two hot entry points could be moved to assembly
(hand-written SIMD or an assembly kernel with a C binding) for use from
CPython. The answer is **it is possible, and it is not the optimisation that
matters**. Writing the kernel in assembly would buy a few percent of the API
call; restructuring the C it is written in buys 1.2× to 3.3× on the same API,
with no assembly and no new correctness risk.

(Measured on the DP as it was before 2026-10-13, when the 2:1 / 1:2 / 2:2
geminate transitions it mentions were replaced by a one-time segmentation of
each word into heavy units — `dp_plain` is now the plain recurrence. The
figures are kept as they were measured; they have not been re-run.)

This document is the measurement behind that claim. The prototype that
produced the first version of it has been removed from the tree with the rest
of the model-side analysis tooling, and that is worth being explicit about:
the numbers below that come from it are recorded here and are no longer
reproducible with a command. `make -C csrc bench` remains, and it is the tool
for the question this document is about.

The one number that IS reproducible and that matters most is the measured
comparison against the shipped function: **1.31× on an 11-token pair, 1.41×
on a 35-token one, 0.78× on a 5-token one.** Those came from timing
`abugida_word_distance` as compiled, which is what any future attempt has to
beat.

## What was measured, and where it goes

The kernel is not vectorisable, and the reason is structural rather than a
matter of effort. `gcc -O3` emits **404 scalar `movsd` and 17 packed
instructions** for the inner loop: the cell's value depends on the cell to its
left (`cur[j-1]`), so the wavefront is serial and there is nothing for a
packed instruction to do. Divisions are absent, `arccos` is absent — the
substitution costs are table lookups, and the arithmetic is three adds and two
`minsd` per cell.

What the kernel DOES contain is a per-cell indirect call. `run_dp` takes the
substitution and indel costs as function pointers, which is what makes it the
one place the recurrence is written (see CLAUDE.md) and what stops the
compiler from inlining them: **15 `call` instructions live in that inner
loop**. That, not the arithmetic, is the cost.

| version | ns per cell | vs base |
|---|---|---|
| as `csrc/abugida.c` writes it | 8.6 – 12.0 | — |
| with the cost table behind a local row pointer, the indel weights precomputed, and no function pointers | **1.5** | **5.6×** |
| the same, plus the 2:1 / 1:2 / 2:2 geminate transitions | **1.9 – 2.1** | **4.5×** |

**THAT 5.6× IS AGAINST A STRAW MAN, and it sent the plan the wrong way for a
while.** "As `csrc/abugida.c` writes it" in the first row is the *pointer*
form: `run_dp` takes its costs as function pointers. But `gcc -O2` compiles
`abugida_word_distance` through `constprop` specialisation, so the shipped
function has **zero calls to the cost function in its hot path** — the table
is read directly. Measured against the shipped function instead of against the
pointer version, the same restructuring is:

| pair | shipped | hand-restructured | gain |
|---|---|---|---|
| `kamma` / `khamma` | 252 ns | 324 ns | **0.78×** |
| `dhammaniyāmaṃ` / `dhammaniyama` | 1,182 ns | 904 ns | 1.31× |
| a 35-token compound pair | 10,221 ns | 7,264 ns | 1.41× |

So the conclusion of this document — that the DP should be restructured rather
than assembled — is right by luck and wrong by number: the restructuring is
1.3–1.4×, the compiler had already done most of it, and the honest reading is
that **the kernel is at its floor** (6.7 ns per cell, memory-bound). The
lesson is in `TODO.md`: a benchmark whose baseline is not the shipped code
measures the benchmark, not the code.

All three return the same double, bit for bit, including on a pair with real
geminates (`vikkhambhati` / `vikhambhati` → 0.46973812807927851). That matters
more than the ratio: the project's parity guarantee
(`tests/test_c_parity.py`) requires exact agreement with the Python reference,
and a scalar min-chain in the same order preserves it. Any reordering —
including most of what a SIMD kernel would do — risks it.

## What that becomes at the Python API

A faster kernel is not a faster call. Splitting the 13 × 13 pair
(`dhammaniyāmaṃ` / `dhammaniyama`, 2.37 µs through the binding):

| component | time | share |
|---|---|---|
| building the two `Tokens` — mostly Cython, not the scanner | 1.00 µs | 42% |
| the DP kernel | 1.41 µs | 58% |
| normalisation (`_canonical`, skipped when the word is already canonical) | 0.03 µs | 1% |

**That first row is NOT the tokeniser, and an earlier version of this
document said it was.** Timed directly in C, scanning a 35-token compound —
the longest word in the fixture — takes **390 ns**. What costs a microsecond
is the Cython wrapper: argument handling, the `Tokens` object, the UTF-8
buffer, error plumbing. Two `Tokens.from_text` calls on that pair measure
2.30 µs from Python against ~0.8 µs of actual scanning, and
`Tokens.from_text("a")` alone costs 233 ns for one character.

The correction matters because it changes what to do next: "optimise the
tokeniser" would have been work in the wrong place. The scanner is 4% of a
`distance` call. The wrapper is a floor under every call, and the only way
past it is to not cross it — which is what an API taking pre-tokenised words
would do, not a faster scanner.

So the ceiling on any kernel work — assembly included — is the kernel's ~58%,
and a 5.6× kernel turns that into:

| pair | now | with the 5.6× kernel | gain |
|---|---|---|---|
| `kamma` / `khamma` (5 × 6) | 0.89 µs | 0.65 µs | 1.4× |
| `dhammaniyāmaṃ` / `dhammaniyama` (13 × 13) | 2.37 µs | 1.23 µs | 1.9× |
| a 39 × 37 compound pair | 13.80 µs | 4.31 µs | 3.2× |

The gain grows with the word, because tokenisation is a fixed cost and the DP
is quadratic. Over a realistic lexicon sweep — where most work is in the
longer half — that is roughly **2–2.5× end to end**.

## Why assembly specifically does not pay

1. **The remaining kernel time is not arithmetic.** 2.1 ns/cell at ~3.5 GHz is
   about seven cycles, for three adds, two branches and four loads. Hand
   assembly could plausibly reach five cycles — 20% off the kernel, which is
   **0.28 µs of the kernel's 1.41 µs on a 13 × 13 call, or 12% of the API
   call** — and that is the optimistic end. The ceiling is already visible from
   the prototype, and the larger prize is a restructuring C can do by itself.
2. **There is no vector to exploit.** The recurrence is a serial scan along a
   row. A wavefront formulation would need the anti-diagonal dependency
   rewritten cell by cell, and the geminate transitions break the diagonal
   structure outright (a 2:2 transition reaches back two rows and two columns).
3. **It would break the parity test's basis.** `tests/test_c_parity.py`
   requires bit-exact agreement with the pure-Python reference. Reassociation
   is the one thing SIMD does by default, and `-ffast-math` (which would be
   needed to let a compiler vectorise the min-chain freely) breaks the
   NaN/rounding behaviour the guarantee rests on.
4. **The project ships a single C99 file that also compiles as C++.** Assembly
   means one file per architecture, a build step that cannot be a `.c` file,
   and a reviewer who has to read it. CLAUDE.md's discipline is that numbers
   are derived and claims are reproducible; an arch-specific kernel is a
   maintenance surface that buys 1.5% of a call.
5. **CPython is not the constraint at this size.** For a short pair the
   Python-side marshalling is a third of the call and cannot be removed
   without changing the API. `tools/benchmark.py` already shows the metric at
   18× the reference; the next multiple is not in the arithmetic.

## What would actually be worth doing, in order

0. **Nothing in the kernel.** The measurements below were taken before the one
   above and are kept because the reasoning still holds, but the first item —
   restructuring — is now measured at 1.3–1.4× against the real code and is not
   worth taking. Start from the boundary instead: the Cython call is 233 ns per
   word and is paid twice per comparison, which is where the product's time is.

1. **Restructure the kernel as the prototype does** — pass the cost table in
   as a row pointer, precompute the indel weights into a small array, and
   specialise the recurrence so the costs are direct calls the compiler can
   inline. Pure C99, no new file, ~4–5× on the kernel and 1.2–3.3× on the API.
   The risk is real but bounded: the prototype already returns bit-identical
   results, and `tests/test_c_parity.py` plus the 4,131-pair fixture would say
   so immediately if a refactor changed a value.
2. **Stop re-crossing the boundary** (the 42% row above). Note what this is
   NOT: it is not the scanner, which is 390 ns for 35 tokens. It is the
   Cython call itself, ~0.23 µs per `Tokens` and paid twice per comparison. A
   sweep tokenising the same 500 words for every query pays it 500 times, so
   an API that accepts pre-tokenised words — the binding already has
   `Tokens` — removes it where it is actually spent. A token cache keyed by
   the string would do the same and is easier to get wrong.
3. **Only then** consider the kernel's last cycles, and consider first whether
   the algorithm can be beaten rather than the arithmetic: for Levenshtein the
   classical answer is Myers' bit-parallel algorithm (about 1 bit per cell,
   ~15× on the flat metric), which is a different algorithm and not available
   to the weighted one — but it is worth knowing that flat Levenshtein has a
   much faster formulation the current integer DP does not use.

## The honest summary

Assembly is *possible* here — nothing about the kernel forbids it, and the
function boundary is already clean enough to replace. It is not *worth it*:
the kernel is a serial scalar recurrence with a visible ceiling of about seven
cycles per cell, the bottleneck is a per-cell indirect call that C can remove
by itself, and the part of the call an assembly kernel could never touch is
40% tokenisation. A 5.6× kernel is worth having; a 6.5× one is not worth a
second implementation of the metric in a language nobody on the project
reviews.
