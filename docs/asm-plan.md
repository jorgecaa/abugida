# Plan: assembly (and mixed C/assembly) in the C core

A plan for putting hand-written assembly into `csrc/`, in the places where it
pays, with the verification that keeps the Python package working.

It is written against measurements, not estimates. Every number below comes
from prototypes measured on this machine
(Intel i5-7600K, 3.8 GHz, AVX2, no AVX-512; GCC 16, GNU `as`). Nothing here
is implemented yet.

## Summary, and the one finding that reorganises the plan

**A blanket "write the C in assembly" is not worth doing, and by the end of
phase 1 it was clear that the narrower version is not either.** The plan has
been redesigned around what the measurements say; the history is kept below
because how it changed is the useful part.

| where | measured | verdict |
|---|---|---|
| `levenshtein`, the flat metric | Myers' bit-parallel kernel: **8× to 53× on the kernel, 4.9× on a lexicon sweep** | **done** (phase 0) |
| the kernel's instruction set | `c` / `sse2` / `avx2` run at 75.4 / 75.1 / 74.6 ns per pair — 1%, the noise floor | done, and **no speed** (phase 1) |
| the weighted DP, hand-restructured | **1.3–1.4× on long words, 0.78× on short** against what `gcc -O2` actually emits | **not worth it** |
| hand assembly over either kernel | bounded by the two rows above at roughly 1.3×, in a language nobody reviews | **closed** |
| the Python/C boundary | 233 ns per `Tokens.from_text("a")`, paid twice per comparison and 200 times per `Lexicon.search` | **the live bottleneck** |

So the remaining work is not in the kernel at all: it is in the crossings and
in work that does not need doing. Phases 2–5 as first written are cancelled in
`THE REDESIGN` below, with the numbers that cancelled them, and replaced by
three phases each of which must clear a stated bar before it starts.

## Constraints that shape every phase

1. **Bit-exactness with the pure-Python reference is non-negotiable.**
   `tests/test_c_parity.py` requires the C core and `abugida/_pure.py` to
   return the same doubles, and `tools/differential.py` extends that to the
   domain (which inputs raise) as well as the range. Any assembly path must
   reproduce the reference bit for bit, which rules out `-ffast-math`, rules
   out reassociating the min-chain, and makes "it looks the same" useless as
   evidence.
2. **The Python binding must not have to change.** The binding calls
   `abugida_word_distance`, `abugida_word_levenshtein` and `abugida_edit`
   through `csrc/abugida.h`. Assembly lives *behind* those symbols or is
   selected inside them, so `abugida/_cabugida.pyx` does not move at all. That
   is the whole point of the C boundary having been drawn where it was.
3. **A machine without the instruction set must still work.** Runtime CPUID
   dispatch with the plain-C variant always present and always correct
   (`-O2`, no `-march`), because the library ships as source and a wheel built
   on one machine runs on another.
4. **The assembly must be optional at build time.** The project's promise is
   that `pip install .` works with a C compiler; it must not start requiring
   an assembler that behaves. A build that cannot assemble the `.S` file falls
   back to C, and the parity tests still pass. `tests/c/test_abugida.c` and
   the differential harness must both be runnable in that configuration.
5. **No second copy of the metric.** CLAUDE.md requires the recurrence to be
   written once. The assembly for `levenshtein` is a different *algorithm* for
   a different *cost model*, not a second copy of the weighted DP, so it does
   not violate that rule. Assembly for the weighted DP would, and that is one
   of the reasons it is Phase 4-at-the-earliest.

## Phase 0 — DONE (2026-08), and what it turned out to be

Implemented and verified. What landed:

- `csrc/abugida_myers.c` — the bit-parallel kernel, exact for words whose
  shorter side is at most 64 tokens and declining above that.
- `abugida_word_levenshtein` runs it first (`#ifdef ABUGIDA_USE_MYERS`) and
  falls back to the DP, so every input has an answer and both kernels give the
  same integer.
- `tests/c/test_myers.c` (890 checks) compares the kernel against the DP and
  against an independent Wagner-Fischer written in the test, over every pair
  of a token corpus, both orders, the 64/65 boundary, and a 200-token word
  that only the DP can answer.
- The kernel is added to `csrc/Makefile` and to `setup.py`; the DP stays
  compiled either way, so removing the define is a complete build.

Measured, with the kernel in place:

| what | before | after |
|---|---|---|
| a 500-word lexicon sweep, `lenient=True` — what `eval/head_to_head.py` and `eval/compare_levenshtein.py` actually do | 2.16 ms per query | **0.44 ms (4.9×)** |
| a single 11-token call | 2.02 µs | 1.10 µs (1.8×) |
| a single 5-token call | 1.35 µs | 1.51 µs — inside the noise, and the floor is tokenisation |

Four corrections to this plan, learnt by implementing it. The first two are
about the algorithm; the last two are about the LENIENT PATH, which the
kernel exercised for the first time and which turned out to have been carrying
three bugs that no existing suite could see:

1. **The limit is the SHORTER word, not both words.** The bit-vector is a DP
   row, so it is indexed by the second word; the kernel makes the shorter word
   that one and walks the longer. A 65-token word against a short one is
   therefore well inside the range. The first version of the predicate
   demanded both fit and declined work it could do.
2. **The gain that matters is on sweeps, not on calls.** The plan said
   "1.3×–4.0×"; measured on the operation that actually consumes
   `levenshtein`, it is **4.9×**, because a sweep amortises the tokenisation
   that dominates a single call. Using a baseline in an evaluation script and
   serving one query per user are different workloads.
3. **The opaque-token encoding could not do what it promised.** It clipped
   codepoints to 11 bits, so `levenshtein("a", "\u00e9", lenient=True)` was 0,
   and it could produce a slot that wrapped to a POSITIVE token id, pricing an
   emoji as a real grapheme. It is now length-prefixed, so characters of
   different UTF-8 length can never collide and one- and two-byte characters
   are exact. `docs/c-core.md` has the table.
4. **The kernel indexed its pattern table with a negative id.** Opaque tokens
   are negative by construction, so `peq[t]` was an out-of-bounds read that
   stayed inside the array in practice — silently wrong rather than a crash.
   The kernel now declines any word whose tokens are not indexable and the DP
   answers it.

None of the three was visible to the C suite, the 7,396-pair parity fixture or
the benchmark, because none of them mistypes a character. `tools/differential.py`
found each of them within a minute of the kernel being wired in. Phase 4's
"verify against Python" was not a formality; it was the phase that found the
bugs.

**Gate G0 passed:** `make -C csrc check` reports 0 failures in all three
suites BOTH with the kernel defined and with it removed, and the Python suite
passes either way.

Phase 1 onwards is unchanged and still not started.

## Phase 0 as planned — confirm the Myers ceiling before writing a line of assembly

**Goal:** establish the number the whole plan rests on, in C, with no
assembly. This is already half done (the prototype exists and agrees with the
core) and it is the phase that decides whether the rest is worth starting.

Do:

1. Promote the prototype to a real C file: `csrc/abugida_myers.c`, exporting
   `abugida_levenshtein_myers(const abugida_token *, size_t, const abugida_token *,
   size_t, long *)`. Single 64-bit word, valid for `nb <= 64`; returns a
   "not applicable" status above that so the caller uses the DP.
2. Handle the two things the prototype skips: the `peq[]` table must be built
   per call (measure both with and without — the prototype shows the gain is
   real either way: 51 ns of 268 for the 5-token pair), and words longer than
   64 tokens need either the block variant or the DP. **Measured context:**
   the longest word in the parity fixture is 35 tokens, and 64 covers every
   realistic Pāli compound; the C suite has a 600-token synthetic word that
   must keep taking the DP path.
3. Wire it into `abugida_word_levenshtein` behind a compile-time flag that
   defaults to on, so the existing suites exercise it immediately.

**Gate G0:** `tests/c/test_abugida.c`, `tests/c/test_edge_cases.c`,
`tests/test_c_parity.py` and `tools/differential.py` all pass, and
`tools/benchmark.py` shows the expected kernel gain. If they do not, stop:
the plan has no foundation.

Already established, so Phase 0 starts from evidence rather than a hope:
The kernel was compared against the core's DP over 20,000 random token
pairs with no disagreement
measures the gain. Both build with two commands and neither is wired into
anything.

**Why this is first:** it is where most of the win is, it needs no assembly,
and it is revertible. If Phase 0 lands and nothing else does, the project is
still substantially faster and carries no new maintenance surface.

## Phase 1 — DONE (2026-08), and the answer is that the flag does not matter

Implemented and verified. What landed:

- `csrc/abugida_myers.c` is compiled **once per instruction set** from one
  source, via `ABUGIDA_MYERS_SUFFIX`; `csrc/Makefile` builds them with
  `-march=x86-64-v2` and `-march=x86-64-v3`, probed rather than assumed.
- `abugida.c` holds the dispatcher: a table of variants, `CPUID` for the
  default, and `ABUGIDA_IMPL` (or `abugida_impl_select`) to force one.
- `abugida_impl_count`/`_at` exist so a TEST can walk every variant instead of
  whichever the machine happens to pick.
- `tests/c/test_myers.c` runs its whole battery once per variant (**2,724
  checks**); `tests/test_c_parity.py` compares every variant with every other
  and each with the pure-Python reference.
- `abugida._cabugida.impl_names()`, `impl_name()` and `impl_select()` expose
  the same thing to Python, so a bug report can say which kernel answered.
- `make -C csrc bench` measures them; `make -C csrc check IMPL=1` builds the
  single-variant library and passes (**914 checks**).

**THE MEASUREMENT, which is the part worth reading.** The variants run at the
same speed:

| variant | kernel ns/pair | entry ns/pair | instructions in the kernel |
|---|---|---|---|
| `c` | 75.4 | 78.6 | 129 |
| `sse2` | 75.1 | 78.3 | 129 |
| `avx2` | 74.6 | 77.5 | 106 |

The AVX2 build is measurably a different binary — BMI2 shifts replace the
flag-dependent `shl`, 106 instructions against 129 — and it is **1% faster**,
which is inside the noise of a machine with a scheduler on it. The reason is
the one `docs/kernel-assessment.md` already gave for the weighted DP and which
turns out to apply here too: **the recurrence is a serial dependency chain**
(`pv`/`mv` feed the next token's `pv`/`mv`), so its latency is the chain, not
the instruction count. There is no vector to exploit and no throughput to
recover.

So Phase 1 buys **no speed**, and the plan should say so rather than being
retro-fitted. What it buys is the thing Phase 2 needs: a verified seam where a
hand-written kernel can be dropped in behind three existing names, with the
tests that walk it already written — and a tool that can tell whether the
assembly is actually faster, which the measurements above show is the only
question that matters.

Two things Phase 1 corrected in this plan:

1. **"One file compiled three times with different flags" does not work with
   setuptools.** It de-duplicates `sources` and applies `extra_compile_args` to
   the whole extension, so the naive version produced ONE object and a
   duplicate-symbol link error. `setup.py` now generates one file per variant
   in the build tree, differing only in the suffix macro.
2. **A variant list is only worth having if a test walks it.** The first
   version of the parity test compared variants against each other, which
   cannot catch one wrong source compiled three times — sabotaging the kernel
   showed it passing. It now compares each variant against the pure-Python
   reference first.

## Phase 1 as planned — the C variants, so there is something to compare against

**Goal:** a seam for dispatch, and a reference implementation for the
assembly, before any assembly exists.

Do:

1. Split the *dispatch* from the *implementation*:
   `abugida_levenshtein_dispatch` (in `abugida.c`) selects among variants by
   function pointer resolved once at first call.
2. Instantiate three variants of the Phase 0 kernel: `_c` (portable, `-O2`,
   the baseline), `_sse2` (x86-64 mandatory, so it always exists), `_avx2`.
   For now all three are compiled from the *same C* with different flags; the
   point is that the plumbing is exercised before assembly is trusted to it.
3. Add an environment override — `ABUGIDA_IMPL=c|sse2|avx2` — because the
   parity run needs to force each variant, and because "which path answered"
   must be answerable in a bug report. This is a debug facility in the spirit
   of `USING_C` in `abugida.distance`.

**Gate G1 passed:** all three variants pass the C battery and the parity
suite, `IMPL=1` builds and passes with one variant, and the values are
identical across them. The gate asked for identical values; it also produced
the answer that they are identical in SPEED, which is what makes Phase 2 a
question rather than a plan.

## THE REDESIGN (2026-08)

Phases 2–5 as originally written are cancelled, not postponed. Measuring the
product instead of the kernel took away their premises:

- **Phase 2 wanted to beat the compiler on the Levenshtein kernel.** Phase 1
  measured instruction count as irrelevant: 129 instructions against 106 was
  1%, because the recurrence is a latency chain.
- **Phase 5 wanted 4.5–5.6× from removing the DP's function pointers.** That
  number came from a prototype that compared against a
  HAND-WRITTEN pointer version. The real `abugida_word_distance` does not call
  a pointer: `gcc -O2` specialises `run_dp` (`constprop`), inlines both cost
  functions and reads the cost table directly — **zero calls to the cost
  function inside the hot path**. Measured against what the compiler actually
  produces, removing the pointers by hand is **1.3–1.4× on long words and
  slower on short ones**:

  | pair | current | hand-restructured | gain |
  |---|---|---|---|
  | `kamma` / `khamma` | 252 ns | 324 ns | **0.78×** |
  | `dhammaniyāmaṃ` / `dhammaniyama` | 1,182 ns | 904 ns | 1.31× |
  | a 35-token compound pair | 10,221 ns | 7,264 ns | 1.41× |

  Same doubles throughout. 1.3× on the long case is not worth a second
  instantiation of the recurrence, and 0.78× on the short one is a regression.

What replaced them is what the same measurements point at. The three facts
that decide it:

1. **The kernel is essentially done.** `distance` costs 6.7 ns per DP cell;
   eliminating the function pointers entirely — reaching the floor of what a
   scalar loop can be — moves that by at most 1.4×. There is no large factor
   left in the kernel.
2. **The crossings are now the visible cost.** `Tokens.from_text("a")` costs
   233 ns from Python against ~11 ns of actual scanning, and `Lexicon.search`
   pays it 200 times per query.
3. **The work that does not need doing is the cheapest work to remove.**
   `Lexicon._compare` is a derived, immutable list of strings that
   `distance()` re-normalises and re-tokenises on every single call.

So the remaining plan is about crossings and about not doing work, in that
order, and each phase must clear a measured bar before the next starts.

## Phase 2 — DONE (2026-08): the Lexicon stopped re-tokenising itself

Implemented. `Lexicon` builds the tokens of its compared forms once
(`_compared_tokens`, keyed by the COMPARED form, so `normalise=True` is
covered) and hands `distance()` a `Tokens` instead of a string, in `search`,
`median_length`, `variants` and the pair-scoring loop. No C, no Cython, no API
change — `distance` already accepted a `Tokens`.

**The number, measured at the entry point and not at the part.**

| | ms per query | share of a search |
|---|---|---|
| candidate prefilter (`_pool`, rapidfuzz) | 0.268 | 32% |
| scoring, strings (before) | 0.619 | 73% |
| scoring, cached tokens (after) | **0.291** | **34%** |
| **`Lexicon.search`, whole call** | **0.849 → 0.626** | **1.35×** |

`python tools/benchmark_lexicon.py` reproduces it on a seeded synthetic
lexicon, with no DPD database.

**Two corrections to this phase's own plan, both about measurement.**

1. **The plan promised 2.97× and the entry point gives 1.35×.** The 2.97× came
   from timing the scoring loop in isolation, with the query already tokenised
   and the candidates already in hand — i.e. from excluding `_pool`, which is
   32% of a search, and the cache lookup itself, which the loop then still
   paid. The sub-part really is 2.1×; quoting that as the phase's result would
   have been the third time in this work that a ratio measured on a slice sent
   the plan the wrong way. The script now prints both numbers side by side, on
   purpose.
2. **The first implementation was wrong in a way that looked fine.** The cache
   build loop used `form` as its loop variable, shadowing the parameter, so
   every lookup answered with the LAST compared form in the lexicon. The
   symptom was `search("kamma")` returning `(0.0, "yoga")`: plausible-looking
   output, every number wrong. It survived a read of the function and a
   from-scratch reimplementation of it, and was found by printing the cache
   from inside. `tests/test_lexicon_tokens.py` pins it, and re-introducing the
   shadowing fails four of its five tests — checked, not assumed.

**Gate G2 passed:** `Lexicon.search` is identical over 37 queries in both
`normalise` modes and with `max_distance`, the 394-test suite passes, and the
scoring loop's share of a search fell from 73% to 34%.

## Phase 3 — MEASURED AND NOT INTEGRATED (2026-08)

The gate did its job: it was measured before it was built, and the answer
changed what was built.

**The gate (G3) said go.** On the real lexicon (`../dpd-db/dpd.db`, 75,733
lemmas) and the 200-candidate pools the evaluation scripts use, the share of
candidates above the threshold is **94.4% at θ=1.5** and **99.6% at
θ=ONE_MOVE**. The pool is not chosen to fall inside θ, so almost everything in
it is discarded — which is exactly what makes pruning worth trying.

**The kernel gain is real.** `abugida_word_distance_bounded` stops the DP at a
cell that has passed the bound, and it is exact. Measured against the plain DP
in C, per pair:

| pair | tokens | plain | bounded | gain |
|---|---|---|---|---|
| `nāma` / `rūpa` | 4 | 283 ns | 172 ns | 1.64× |
| `kamma` / `khamma` | 5 | 251 ns | 193 ns | 1.30× |
| `vikkhambhati` / `vikhambhati` | 10 | 803 ns | 551 ns | 1.46× |
| `dhammaniyāmaṃ` / `dhammaniyama` | 12 | 1,204 ns | 796 ns | 1.51× |
| a 35-token compound pair | 35 | 10,295 ns | 7,017 ns | 1.47× |

**And it is worth nothing at the Python API.** `Lexicon.search` with a
threshold, using the bounded DP, against filtering afterwards:

| θ | 100 queries, identical results | gain |
|---|---|---|
| 1.5 | 964 ms → 1,053 ms | **0.92×** |
| 0.627 | 962 ms → 937 ms | **1.03×** |

The per-candidate Python work — the `Tokens` lookup, the call, unpacking the
verdict — costs more than the kernel saves. `_pool` is ~40% of a search and
the scoring is now spread over many small pieces; a 1.4× kernel no longer
moves the total. Phase 2 is why: it removed the tokenisation that used to
dominate the same loop.

**So the Python integration is REVERTED**, with the measurement left in a note
where the code would have gone, and the C function stays: it is correct,
tested (`tests/c/test_bounded.c`, 12,306 checks), and a C consumer sweeping a
pool has no per-candidate Python cost to pay. What does not exist is a
justification for calling it from `Lexicon.search`.

**Three wrong versions of the cut, all measured.** This is the part worth
keeping, because each looked right:

1. **"Stop when the row's minimum exceeds the bound."** That the minimum of
   row i exceeds the bound DOES prove the final distance does — a path through
   row i pays at least that — but it does not license stopping: a later cell of
   the SAME row can still be under the bound and reach the end cheaply. It lost
   `vohari`/`voharati`, true distance 1.627 against a bound of 1.5. **2.6% of
   verdicts wrong** on a real pool.
2. **The same plus `remaining * min_indel`**, on the theory that the steps left
   have a floor. They do not: a substitution between two equal tokens costs
   **0**. **4% wrong.**
3. **Forgetting `cur[0]`** when taking the row's minimum, which is the cheapest
   cell of the first row and the reason `vohari`/`vihari` cut a row early.

What is right is the cut **per cell**: a cell that has passed the bound can
never be part of a path that comes back under it, because every edit is
non-negative. `tests/c/test_bounded.c` pins all three failures — re-introducing
version 1 fails it on `tt`/`ṭṭ`, whose distance is 0.437 against a bound of
0.45.

**Gate G3 passed and the phase still did not ship**, and the lesson is the one
this plan keeps relearning: the gate measured whether there was WORK to remove.
It did not measure whether removing it would make the CALL faster. The next
gate for a phase like this one should be written on the entry point, not on the
mechanism.

## Phase 4 — CAN the DP be beaten? One attempt, with a stated bar

**Not "write it in assembly" — "find 2× somewhere", with permission to fail.**
The kernel is at 6.7 ns/cell, memory-bound and already specialised by the
compiler. The measured headroom from the most obvious restructuring is 1.3×.
So this phase is a bounded experiment, not a work item:

- **The bar: 2× on `distance` for words of 10 tokens or more, or the phase is
  abandoned.** 1.4× is already known to be reachable and already known not to
  be worth the maintenance; anything less than 2× is not worth a second
  instantiation of the recurrence.
- **Compare against what the compiler emits, never against a hand-written
  straw man.** That is the mistake the prototype made and this
  document repeated: its "base" was a pointer version no build ever produces.
  Any future measurement must be against `abugida_word_distance` as compiled.
- Directions that are algorithmically different rather than micro-optimised,
  and therefore the only ones with a chance: a banded DP driven by a length
  bound (`|len(a) - len(b)| × min_indel` is a lower bound on the answer), and
  a cheap lower bound used as a prefilter across a lexicon.
- **`make -C csrc bench` is the tool.** It exists so that whoever attempts
  this can fail fast and with a number.

## Phase 5 — CLOSED: the assembly of the kernel

Closed after two phases and one set of measurements, and reopened only with a
number:

- The Levenshtein kernel is latency-bound, so instruction count does not
  matter (phase 1: 1% between a 129-instruction and a 106-instruction build).
- The kernel's share of a call is now small: 2.25 µs of a 2.50 µs
  `levenshtein` is the Python/C boundary, not the kernel, and the weighted DP
  is at 1.3–1.4× from its own floor.
- Hand assembly would be a third implementation of the metric, in a language
  nobody on the project reviews, for a factor that the two measurements above
  bound at roughly 1.3×.

The seam that was built for it stays — `abugida_impl_select`, the variant
list, `make -C csrc bench` — because it is what makes "is assembly worth it
here?" an answerable question rather than an argument. `csrc/abugida_myers.c`
still compiles once per instruction set; adding a fourth variant that is an
assembly file is a matter of defining the same three symbols.

## The order, and the stopping rule

Phase 2 (measured, 2.97×, no C) → Phase 3 IF G3 clears → Phase 4 IF the 2×
bar looks reachable → otherwise stop.

**The stopping rule is the important part of this redesign.** Every phase
above has a number attached BEFORE it starts, and a phase that cannot clear it
is cancelled rather than finished. Phases 0 and 1 were worth doing and were
done; phases 2–5 as first written were not, and the only reason that is known
is that measuring them came before building them.
