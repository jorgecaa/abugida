# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`abugida` is a phonological distance metric for Pāli words in IAST: a
calibrated edit distance whose substitution costs come from an algebraic
model of Pāli phonology. No runtime dependencies, no lexicon.

The metric is implemented **in C** (`csrc/`), reached from Python through a
Cython binding; `abugida/_pure.py` is the pure-Python reference the C core is
generated from and verified against. `docs/c-core.md` is the guide to that
arrangement. The Python API is unchanged by it.

Nine documents carry the project's intent, and they are authoritative:

- `SPEC.md` — the theory: the algebra (§1), the embedding (§4), the
  distance (§9), the evaluation (§11). It describes what the library is,
  not how it got there; the record of decisions is in `TODO.md` and
  `FINDINGS.md`.
- `docs/comparator.md` — the integration guide and the public API contract,
  including the published cost table.
- `docs/c-core.md` — the C core: how to link it from C, how the generated
  tables are derived, the speed measurements, the seven checks that hold the C
  and Python implementations together, why the metric's triangle
  inequality holds (one segmentation per word into heavy units),
  what "the two are mirrors" is verified to mean, and the one function that
  keeps two kernels (bit-parallel `levenshtein` plus its DP fallback).
- `docs/using-abugida.md` — a one-page briefing for a new integrator or an
  agent, pinned line by line by `tests/test_briefing.py`. If you change the
  API or a published figure, that test fails and tells you the briefing needs
  updating too.
- `docs/kernel-assessment.md` — whether `distance` and `levenshtein` should be
  written in assembly (measured answer: no), with the numbers reproducible
  from a prototype whose recommended restructuring turned out to
  be 1.3-1.4x against the shipped code, not the 5.6x it measured, because the
  prototype's baseline was hand-written; the document says so at the top.
- `docs/asm-plan.md` — the plan, and the record of it being redesigned by its
  own measurements. Phases 0 (the Myers kernel) and 1 (per-instruction-set
  variants) are DONE: 4.9× on a lexicon sweep, and no speed at all from the
  instruction-set variants. Phases 2–5 as first written are CANCELLED — the
  DP is already specialised by the compiler, so hand assembly is bounded at
  ~1.3× — and replaced by three phases about the Python/C boundary and about
  not doing work twice. Phase 2 (the Lexicon's token cache) is DONE: 1.35× on
  `Lexicon.search`, 2.1× on the scoring loop inside it, and no answer changed.
  Phase 3 (a bounded DP) cleared its gate, is 1.4× on the KERNEL and 0.92–1.03×
  at the API, so the Python integration is reverted and the C function kept —
  the gate measured the mechanism instead of the call.
- `README.md` — the positioning and the headline measurements.
- `FINDINGS.md` — the summary table of what has been established, what is
  worth trying and what is closed, with the number attached to each. Read it
  before proposing any change to the metric.
- `TODO.md` — the open threads *and* the measured dead ends. Read it before
  proposing work on variants, filters or new distance operations: it records
  what was already tried and rejected (root_key as a filter, contraction as
  an alignment transition, morphological formability as a filter) with the
  numbers, so nobody re-measures them. It also fixes the reference
  population: agreement is measured against `dpd_headwords.var_phonetic`,
  not `variant`, and any figure quoted from before 2026-08-01 predates that
  correction. **`var_phonetic` is not a ground truth** — DPD's own rules
  compute it — so every figure against it is called *agreement with DPD*,
  names its build (5,002 pairs, August 2026), and never argues the metric's
  quality in a headline (decided 2026-10-13; README, "Agreement with DPD is
  not accuracy"). Do not write "recall", "accuracy", "curated" or "ground
  truth" for it. The independent checks are the grammars
  (`eval/oberlies.py`, `eval/geiger.py`), the open-vocabulary task and
  `tests/test_battery.py`; `eval/hard_battery.py` is NOT one — its triples
  are harvested from `var_phonetic` pairs.

Any change to a cost, a threshold, or a derived constant must be reflected
in the cost tables in both `docs/comparator.md` and `README.md`.

## Commands

```bash
pip install -e .            # editable install; pip install -e '.[speed]' adds rapidfuzz
python -m pytest            # 420 tests, ~6s
python -m pytest tests/test_distance.py::test_triangle_inequality_of_cost   # single test
python tests/test_battery.py   # prints the side-by-side discrimination table

make -C csrc check          # build the C core and run all FOUR suites (no Python):
                            #   test_abugida.c   the metric is right (2,049,213 checks)
                            #   test_edge_cases.c the library is sound (8,797 checks:
                            #     empty words, NULLs, heap path, broken UTF-8, leaks)
                            #   test_myers.c     the two Levenshtein kernels agree, once
                            #     per instruction-set variant of the kernel (2,724)
                            #   test_bounded.c   the bounded DP against the plain one (12,303)
make -C csrc bench          # each kernel variant's ns/pair; they are all the same
make -C csrc check IMPL=1   # the single-variant build: one kernel, no dispatch
python tools/benchmark.py   # pure Python against the C core; docs/c-core.md quotes it
python tools/benchmark_lexicon.py  # Lexicon.search, its parts, and why the two
                            #   ratios differ (the call is 1.35x, the scoring
                            #   loop inside it is 2.1x; quote the first)
python tools/differential.py # the two implementations as functions: same DOMAIN
                            #   (which inputs raise) and same RANGE (same values),
                            #   over 3,878 inputs / ~102,000 comparisons in ~18 min
python tools/generate_c_tables.py          # regenerate csrc/abugida_tables.[ch]
python tools/generate_c_tables.py --check  # fail if they are stale

# Installing, which is a DIFFERENT check from building in place — both of the
# setup.py bugs that broke it were invisible to `build_ext --inplace`.
python -m build --sdist && pip install dist/abugida-*.tar.gz   # in a venv
```

**The metric is C.** `pip install -e .` builds the extension; without a
compiler the package falls back to `abugida/_pure.py` and returns the same
values. After changing anything the tables are derived from — `cost`, the
inventory, `_UNITS`, `EPENTHETIC`, `INDEL_WEIGHT` — you MUST re-run
the generator, and `tests/test_c_parity.py` will fail if you do not.
`pip install -e .` alone does not regenerate them.

Evaluation scripts under `eval/` are run directly (`python eval/x.py`), not
via pytest. The library and its tests never need DPD; only these scripts do,
through `eval/_dpd.py`, and by default they do not use it: a script that needs
DPD says so and exits 0. Pass `--dpd` to use it, or `--dpd PATH` to name the
file (default `/dev/shm/dpd.db`, else `../dpd-db/dpd.db`); `hard_battery.py`
runs from its case file without it, and needs the flag only for `--harvest`.
They are not part of the test suite and most need external
resources.

**Third-party case files are never committed** (decided 2026-10-13, see
`NOTICE`): the Oberlies and Geiger extractions and the DPD-derived
`hard_battery.json` live in `eval/data/` (gitignored) or in
`$ABUGIDA_EVAL_DATA`, and every script reaches them through `eval/_data.py`,
which exits 0 naming the missing file. Do not add a case file, a page image,
an OCR or a quotation longer than a word pair to the repository; a new
extraction goes to the local data directory and its script gets a
`--harvest`. The repository was restarted from one commit that day to drop
the files from history, so no commit hash older than it resolves.

| script | needs |
|---|---|
| `open_vocabulary.py` | DPD db only as a negative control; runs in ~1s. Flags: `--morphological` (formable base words), `--attestation`, `--oov-only` |
| `compare_levenshtein.py` | DPD db (`/dev/shm/dpd.db`) |
| `geiger.py` | DPD db + rapidfuzz. Case file only (`geiger_cases.json`, local data); the grammar is in copyright and is not shipped, so `--harvest PATH` needs your own OCR of it |
| `decision_curve.py` | DPD db + rapidfuzz |
| `phonetic_rules.py` | DPD db + a checkout of `../dpd-db` (read-only) |
| `profile_error_mix.py` | reads logs on stdin; DPD db for the default lexicon |
| `variant_curve.py` | DPD db + rapidfuzz (without it the pipeline column measures something else). The volume/agreement curve behind the θ table in `TODO.md`; the source of every agreement-with-DPD number quoted in the project |
| `karana_bridges.py` | DPD db. Which place confusions transmission attests, and what each karaṇa bridge is worth. Flag: `--ablate coronal\|dorsal\|both` |
| `ablate_geminates.py` | DPD db. Prices the geminates-as-units before anyone removes them (−14.4 points at ONE_MOVE on the 5,143-pair build; the transitions the units replaced were worth −15.1) |
| `noisy_channel.py` | DPD db + rapidfuzz. Derives the LINEAR cost from the noisy-channel reading: confusability decays exponentially over the operating range, so −log P is linear |
| `head_to_head.py` | DPD db + rapidfuzz. Levenshtein vs the metric with the pipeline available to BOTH, at matched volume. The honest margin is +5.6 to +7.4 points at 1–2 candidates per lemma and about nil from 4 up (dressed Levenshtein a point ahead at 8), not the ~20 a bare baseline suggests |
| `protocol.py` | DPD db + rapidfuzz. **The evaluation protocol.** Use it for any "is this better?" question: paired bootstrap + McNemar, not overlapping intervals; agreement against volume, never against θ |
| `oberlies.py` | case files only (`oberlies_cases.json`, `geiger_cases.json`, `hard_battery.json`, all local data); no DPD. The metric against Oberlies' grammar, an independent reference, and both against DPD's variant pairs; findings in `TODO.md` |
| `oberlies_attested.py` | DPD db (as information only). Which Sanskrit-side forms of the Oberlies pairs Pāli also attests (western `samāja` beside eastern `samajja`); writes the local `oberlies_attested.json`, which `oberlies.py` then measures as a second set of Pāli doublets |
| `phonotactics_calibration.py` | DPD db. How much of the real lexicon `is_possible` accepts and why the rest is rejected; reproduces the calibration quoted in SPEC §8 |
| `triangle_geminates.py` | case files only; no DPD. Why the word-level triangle failed before the heavy units (one cause: per-pair geminate segmentation) and what each repair costs, the adopted one (halves) included; ~6 s |
| `hard_battery.py` | case file only (`--harvest` needs DPD). 3,000 triples where Levenshtein ties by construction; the metric scores 50.9% [49.1, 52.7] raw and 68.1% through the pipeline, so unlike `tests/test_battery.py` it has headroom |

Three measurement rules, each learnt by getting it wrong (see
`eval/protocol.py`):

- **Sweep the constant, never its rounded label.** A large share of true
  pairs sit at *exactly* one epenthetic indel, so sweeping `0.627` instead
  of `INDEL_WEIGHT` drops all of them — 59.9% where the operating point
  really yields 63.6%.
- **Compare paired, not by overlapping intervals.** Two 95% intervals can
  overlap while the paired difference is decisive; `protocol.compare` does
  the bootstrap and McNemar.
- **Never compare agreement at equal θ across metrics** — equal thresholds cost
  different candidate volumes. Use `protocol.iso_volume`.

`tests/test_battery.py` is saturated (30/30 since the heavy units; 29/30 before, and that held even under
calibrations that make `a↔ā` cost 0.073). It detects regressions only; for
improvements use `eval/hard_battery.py`.

Eval scripts insert the repo root on `sys.path` themselves and open the DPD
database read-only. Fixed seeds (`20260801`) — keep results reproducible.

## Architecture

A strict layer stack; each layer only imports downward.

```
comparator.py  Comparator: THE entry point — validated input, pipeline built in
   ↓
lexicon.py     the permissive layer below it (lenient, no validation)
   ↓
```

```
algebra.py     A = B × F₃: voicing (boolean) × modifier (Z₃, aspiration/nasality)
   ↓
phonology.py   the inventory: grapheme + places (ṭhāna) + value in A + residual features
   ↓
embed.py       14-dim vectors; ⊗ becomes vector arithmetic (a verified homomorphism)
   ↓
distance.py    cost() = truncated angular distance between embeddings; distance() = DP over tokens
   ↓
lexicon.py     Lexicon: search + variant generation over a word list (the integration surface)
```

The metric's bottom three layers have a C implementation beside them, which
is what runs by default:

```
csrc/abugida.h      the C API — the contract a C consumer programs against
csrc/abugida.c      tokeniser, cost lookup, DP, traceback, sandhi pipeline
csrc/abugida_myers.c  the bit-parallel Levenshtein kernel, compiled once per
   instruction set (c / sse2 / avx2) from this one source via
   ABUGIDA_MYERS_SUFFIX. Measured: they run at the SAME speed, because the
   recurrence is a serial dependency chain. The dispatcher in abugida.c picks
   one by CPUID and ABUGIDA_IMPL forces one. The DP stays compiled as the
   fallback for words the kernel declines (longer than 64 tokens, or carrying
   an opaque token)
csrc/abugida_tables.[ch]   GENERATED from the Python definitions, committed
   │ compiled into
   ↓
abugida/_cabugida.pyx      the Cython binding (abugida._cabugida)
   │ delegates to it
   ↓
abugida/distance.py, iast.py, sandhi.py    re-export, and fall back to
abugida/_pure.py    the pure-Python reference: the oracle, and the fallback
tools/generate_c_tables.py   reads _pure, writes the tables
```

`_pure.py` is the reference the tables are generated from and the oracle the
C core is checked against; `distance.USING_C` says which is answering. Never
make the generator read `abugida.distance` — it delegates to C, so the tables
would be generated from themselves and would agree with the Python
definitions only by accident. Same for the oracle in `tests/test_c_parity.py`.

`iast.py` (normalisation, longest-match tokenisation — `kh` is one token)
sits beside the stack and is used by everything above `phonology`.
`index.py` (BK-tree over `distance`) sits beside `lexicon.py` and is used
only as the pure-Python prefilter fallback — measured, it does not beat
rapidfuzz and its docstring says why, so do not promote it.

`channel.py` is a peer of the stack that imports nothing from it: pure
arithmetic over `(distance, is_variant)` observations, reading a threshold
as an expected precision under the noisy-channel model of SPEC §9.2
(`fit_channel`; `fit_strata` for per-stratum fits, which abstain to the
pooled channel when a stratum is too small and use the stratum's own flat
rate when it is large but nearly all negative). It ships **no** constants:
λ and c are properties of a corpus, not of Pāli phonology, so the
integrator supplies the observations. `eval/noisy_channel.py` is where the
exponential form was verified.

`sandhi.py`, `phonotactics.py` and `alphabet.py` are peers built on the same
inventory; the place lattice's *meet* is the assimilation rule (`assimilate`)
and its *join* is vowel sandhi (`sandhi_join`). `morphology.py` sits on top
of `phonotactics.py` (never the reverse — that import direction is what
keeps the layering acyclic).

### Two criteria for candidates, not one

`phonotactics.is_possible` asks whether a string is a legal sequence of
syllables; `morphology.is_formable` asks whether it could also be *formed*
(root → base → ending). The second is strictly stronger and strictly
optional: `pseudoword` keeps its role and the evaluations citing it keep
their numbers. Present bases in `ROOTS` are declared data, not derived —
guṇa and the class infixes admit no honest small rule set, and the module
says so rather than approximating. Everything downstream (kita bases,
junction, retroflexion) *is* derived, and `is_possible` filters every
output, so formability is only ever added on top of possibility.

Attestation in DPD is **not** a criterion anywhere in generation: it is used
only to measure the junction rules (47.9% of the generable space is real
Pāli) and, behind an explicit `--oov-only` flag, to satisfy the
open-vocabulary evaluation's own premise.

### Constants are derived, never tuned

This is the project's central discipline. Two constants are computed at
import time from the embeddings themselves, so they re-derive if the layout
changes:

- `embed.NEUTRAL_MODIFIER_WEIGHT` (ρ* ≈ 0.458) — by bisection, the unique
  weight making `cost("k","kh") == cost("k","g")` (the balance principle).
- `distance.INDEL_WEIGHT` (≈ 0.627) — the extremal epenthetic indel weight
  the triangle inequality permits, from a Lipschitz bound and an in-class
  pair bound. `ONE_MOVE` is the MAXIMUM over the elementary moves, defined
  beside it in `_pure` and re-exported by `distance` and `lexicon` (it must
  not be collapsed back into an alias — see the comment there).

If you need a new number, derive it from an existing structure and document
the derivation in the docstring; do not hand-pick a value that makes a test
pass.

### Contraction belongs in `sandhi`, not in `distance`

`sandhi.contract_word` (`aya`→`e`, `ava`→`o`) is deliberately a
normalisation applied *before* measuring, not an edit operation. Moving it
into `distance` as a 3:1 alignment transition looks like a natural
extension of the DP and **breaks the triangle inequality**, for the same
reason the old geminate 2:1 transitions did (see below) — it was implemented, measured and reverted; the
counterexample and the reasoning are in SPEC §6.3. Monotone alignments are
not closed under path composition once a transition consumes three tokens
on one side. If you are tempted to unify the two mechanisms, read that
section first.

### The metric guarantee holds — because each word is segmented once

`distance` is a true metric (identity, symmetry, triangle inequality) over
all words, the empty one included. Each word is segmented ONCE into tokens
and heavy units — geminates (`tt`, `tth`) and homorganic nasal+stop clusters
(`nt`, `ṅkh`, and `ṃ` + any stop, since ṃ carries all five places) — by
`_pure._segment` / `segment_units` in C, and the DP is then plain
substitution and indel. A unit is priced by its halves: `cost` = the max of
the first-half cost, the second-half cost and the weight gap (`_weight`, the
old degemination cost per consonant), so `tt~dd = t~d`, `tt~nt = t~n`,
`nt~nd = t~d`, and costs between single letters are unchanged. A unit's
indel is derived (`_UNIT_INDEL`: the cheapest route through a single token).

The guarantee rests on three token-level conditions, verified exhaustively
in tests over all 126 tokens: `cost`'s triangle, `indel(g) <= cost(g,h) +
indel(h)`, and `cost(g,h) <= indel(g) + indel(h)`. Change a cost, the
inventory, `_UNITS` or an indel and those tests are what tell you whether
it is still a metric.

Until 2026-10-13 it was NOT a metric: 2:1 / 1:2 / 2:2 alignment transitions
let each comparison read a geminate as one long consonant or two letters,
and `d("makka","saṅgha")` was 2.262 against 2.065 through `magga`.
`eval/triangle_geminates.py` traces all violations to that one cause and
measures the repairs that keep per-comparison segmentation (raising unit
costs, closing the transitions under composition): none works. Do not
reintroduce a transition that lets a comparison choose a segmentation.

**What the units cost, measured:** Sanskrit-to-Pāli correspondences of the
cluster-against-geminate shape moved away (`tatra ~ tattha` 0.831 ->
1.470; Sanskrit forms within two moves of their reflex 40.0% -> 31.6%
Oberlies, 47.8% -> 35.0% Geiger; the Geiger tadbhava ranking 32.8% ->
24.5%, paired, McNemar p < 0.01); a one-letter change that breaks a unit
(`tṭ`, which Pāli does not write) costs a broken unit (open vocabulary
90.9/96.0/99.2 -> 88.0/92.4/96.2, unchanged on possible-Pāli variants); and
`distance <= levenshtein` no longer holds in general (tatra~tattha 1.470
against one Levenshtein edit). Pāli doublets did not move; the battery went
29/30 -> 30/30. Every agreement-with-DPD figure predates the change.

### The kernel has variants, and a test walks them

`levenshtein` runs on `abugida_myers.c`, built once per instruction set from
one source and selected at run time by `abugida_impl_select` (or the
`ABUGIDA_IMPL` environment variable). The variants are **not** faster than
each other — measured, 75.4 / 75.1 / 74.6 ns per pair — because the
recurrence is a serial dependency chain whose latency is the chain and not
the instruction count. The arrangement exists so that a hand-written kernel
has a verified seam to go behind, and so that `abugida_impl_count`/`_at` let
a test run EVERY variant rather than whichever the machine selects. A
variant that is only exercised on its author's CPU is a variant nobody has
checked: `tests/c/test_myers.c` runs its whole battery once per variant, and
`tests/test_c_parity.py` compares each with the pure-Python reference.

`make -C csrc check IMPL=1` builds one variant, no dispatch, and passes.

### The recurrence is written ONCE

`abugida_edit` (`csrc/abugida.c`, rolling rows) is the only place the DP is
written; `abugida_word_align` runs the same recurrence over a full matrix for
the traceback and returns the same last-row cell. The Python reference still
has both, and `test_alignment_conserves_the_distance` still holds its two
together — but a change to the metric that is not accompanied by
`python tools/generate_c_tables.py` will not reach the C core, and if it
changes a cost the parity test will say so.

Two things in the C traceback are deliberate and must not be "tidied": the
branch ORDER matches the Python one, and the cost comparison uses a `1e-12`
tolerance rather than equality. Several paths through the matrix usually cost
exactly the same, so which script comes out is a decision, not a derivation;
`edit_tag` publishes whichever one it is, and the parity test compares
scripts operation by operation.

### Strict vs lenient

`tokenize` raises on non-Pāli characters by default — rejecting Sanskrit
diacritics and garbage is a documented guarantee, not a bug. `lenient=True`
turns them into opaque tokens (cost 1 against everything, 0 against
themselves) so a search frontend never raises; `diagnose` is the reporting
half. `phonology.FOREIGN` (ś, ṣ, ṛ) is deliberately *outside* `INVENTORY`:
those graphemes carry real phonology in lenient comparison but must keep
failing strict tokenisation and `is_possible`.

## Conventions

- No runtime dependencies. `rapidfuzz` is optional (`[speed]`) and every use
  is behind an import guard with a pure-Python fallback.
- Docstrings carry the derivation and the reason, with `SPEC.md §n`
  references. They are the project's real documentation — match that density
  when editing.
- Empirical claims in prose (percentages, thresholds) trace back to a script
  in `eval/` or a test. Do not add a claim you cannot point at.
- Commit messages are one substantive sentence describing the finding or the
  change, not a conventional-commits prefix.
- **English only, in the files and in their names.** Prose, comments,
  docstrings, identifiers, commit messages and filenames are written in
  English, whatever language the conversation that produced them was in.
  Pāli and Sanskrit forms are the subject matter, not a second language of
  authorship: `paṭikkūla`, `ṭhāna` and the IAST data are English-file
  content like any other technical term. The rule is retroactive: nothing
  already in the repository is grandfathered, and anything found in another
  language is a defect to fix, not a precedent to follow.
  `tests/test_english_only.py` enforces it: the character sweep is
  exhaustive, the Spanish word list is a tripwire meant to grow.
