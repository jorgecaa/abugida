# Pāli phonological word comparator — integration guide

Documentation for using `abugida.distance` from other applications:
phonological distance between Pāli words in IAST, with metric guarantees,
plus Levenshtein as a baseline. Self-contained: **it requires no dictionary
database, no torch, no external dependency** — pure Python.

## Installation

```bash
pip install -e /path/to/abugida        # editable, for local development
```

or by adding the repository to `PYTHONPATH`. The package is `abugida`.
No runtime dependencies. Declared `requires-python = ">=3.9"`; verified on
CPython 3.11–3.14.

## Start here

```python
from abugida import Comparator

cmp = Comparator(words)                  # validates as it builds
cmp.neighbours("dhamma")                 # nearest words, ranked
cmp.variants()                           # every variant pair, once each
cmp.rejected                             # what was refused, and why
```

That is the whole integration surface. Everything else on this page is the
layer underneath; it stays public because the theory is the point of the
project, but a variant pipeline should not have to assemble it.

**Recall is named, not numeric.** Thresholds are not comparable across modes,
so copying a number from a table is the easy mistake. The table gives each
setting's **agreement with DPD** — the share of the 5,002 pairs in DPD's
`var_phonetic` (August 2026 build) it also generates. See "Agreement with
DPD is not accuracy" below: that field is DPD's own rules' output, not a
ground truth, so the column says how much of what DPD finds you keep.

| `recall=` | agreement with DPD | candidates per lemma |
|---|---|---|
| `"precise"` | 86.2% | 3.6 |
| `"balanced"` *(default)* | 91.4% | 9.1 |
| `"exhaustive"` | 95.1% | 26.6 |

```python
Comparator(words, recall="exhaustive", constructions=my_constructions)
```

**Input is defended.** `Lexicon` below is deliberately permissive — lenient
tokenisation is baked in so a search box cannot crash on a typo. That is
right for a query box and wrong for a lexicon: a Sanskrit headword or a stray
`*` would be indexed and compared in silence. `Comparator` tokenises strictly
on the way in, keeps failures out of the index, and reports them:

```python
cmp = Comparator(["kata", "kṛṣṇa", "qam*"])
cmp.rejected
# {'kṛṣṇa': "not Pāli: 'ṛ' (sanskrit), 'ṣ' (sanskrit)",
#  'qam*':  "not Pāli: 'q' (unknown), '*' (unknown)"}
```

Queries are checked too, and raise rather than returning plausible nonsense
scored from opaque tokens. All 75,367 DPD lemmas pass, so this refuses
nothing legitimate.

### Where to put what

| | takes | validated |
|---|---|---|
| `Comparator(words)` | the words you want to FIND — headwords, lemmas, an index | strictly; failures reported in `.rejected` |
| `neighbours(word)`, `variants(words=…)` | what you are looking WITH | strictly, unless `lenient=True` |

One word per entry. Nothing here takes sentences, phrases or word-splits.

```python
cmp = Comparator(headwords)                    # the lexicon
cmp.neighbours(user_input, lenient=True)       # the query, defensively
```

### Sanskritised Pāli

Pāli carries Sanskritised doublets — `tatra` beside `tattha`, `atra` beside
`attha` — and they are real lemmas, not errors. Every grapheme is Pāli, so
nothing rejects them. Two limits worth knowing:

- **The metric does not price the correspondences cheaply, and the gap is
  measurable.** `tatra ~ tattha` is 0.831 — just outside `"balanced"`, inside
  `"exhaustive"`. `meru ~ sineru` is 2.258 and outside all three. Both are
  pairs in DPD's `var_phonetic`, and both are real doublets: the metric
  prices them far. 10.0% of that field's pairs sit beyond d = 1.0 — but the
  length-relative
  threshold reaches 71% of those, leaving **3.2% genuinely unreachable**, and
  a good share of that 3.2% is not sound change at all (`tumhehi ~ vo`,
  `asmā ~ no`: suppletive pronouns; `obhāsa ~ tejas`: a synonym). Systematic
  sound change is correlated edits where edit distance assumes independent
  ones. Closing it would take a transducer of the sound laws, which is
  historical grammar, not distance between sounds, and is out of scope for
  this library. Use `"exhaustive"` for what is reachable.
- **Actual Sanskrit graphemes need asking for.** `ś ṣ ṛ` (`kṣetta`, `kṛṣṇa`)
  are refused by default — in a Pāli lexicon they are more often an encoding
  mistake than a decision — but `accept="pali+sanskrit"` admits them, and
  only them. They carry real phonology (ṣ↔s 0.460, ś↔s 0.667), which is what
  makes cross-system Sanskrit↔Pāli comparison possible.

### If you need something this does not allow

`Comparator` is deliberately narrow; it is not a wall.

```python
cmp.lexicon          # the Lexicon underneath: permissive, unvalidated
```

Every layer below is exported from the package — `Lexicon`, `distance`,
`alignment`, `phonological_form`, the thresholds, `channel`, `index`. Use
them when you have a reason: a different threshold, a metric-only comparison,
your own prefilter, a BK-tree. What you give up is the configuration that
produces the numbers above, so measure what you build. The rest of this page
documents each piece and what it guarantees.

To choose a threshold against a precision budget on your own corpus rather
than taking a preset, see `abugida.channel`.

**If you have evidence the metric cannot see** — word families, part of
speech, anything from your own database — `fit_strata` fits one channel per
stratum instead of one overall:

```python
obs = [(d, is_variant, (shares_family, same_pos)) for …]
s = fit_strata(obs)
s.precision_at(0.4, (True, True))    # informed by your signal
s.report()                           # per-stratum λ, R², n
```

Worth doing when the signal separates *within* a distance band rather than
tracking it — measured in dpd-db, sharing a word family splits the d ≤ 0.35
band into 87.9% against 3.4%, which is information the distance does not
contain.

Strata that will not fit are handled by size, and the distinction matters:
too few observations means abstain (the pooled channel answers), but a
stratum with many observations and almost no positives is not silence — it
is a loud negative, and gets a flat channel at its own rate. Measured in
dpd-db, one stratum held 16,758 candidates with 3 positives; pooling it
would claim 25.2% where the truth is 0.018%. Check `.basis` on a channel to
see which you got.

## Basic use

```python
from abugida import distance, levenshtein, neighbors, cost

distance("kamma", "khamma")     # 0.470  — one cheap edit (aspiration)
distance("kamma", "samma")      # 1.0    — one expensive edit (unrelated)
levenshtein("kamma", "khamma")  # 1      — the baseline: every change is 1

# searching your own lexicon:
neighbors("dhamma", ["dhammā", "damma", "kamma", "magga"], k=2)
# → [(0.333, 1, 'dhammā'), (0.344, 1, 'damma')]
#    (phonological_distance, levenshtein, word), sorted by the former
```

### Expected input

Pāli words in **IAST**. Normalisation is automatic: uppercase, Unicode
NFC/NFD, the `ṁ` variant of the niggahīta, editorial hyphens and apostrophes
(`Saṁyutta-Nikāya` works as-is). The aspirated digraphs (`kh`, `gh`, `ch`,
`jh`, `ṭh`, `ḍh`, `th`, `dh`, `ph`, `bh`) count as **one letter**.

Characters outside the Pāli alphabet (`ṛ ṣ ś`, punctuation, etc.) raise
`ValueError` by default — rejecting Sanskrit and garbage is a guarantee.
For typo-tolerant frontends there is an explicit lenient mode plus a
reporting function:

```python
from abugida import distance, diagnose, is_possible

distance("qamma", "kamma", lenient=True)   # 1.0 — the typo costs 1, the rest
                                           # of the word still discriminates
distance("qamma", "magga", lenient=True)   # > 2 — so kamma outranks magga
diagnose("qamma")                          # [(0, 'q', 'unknown')] — never raises
diagnose("kṛṣṇa")                          # [(1,'ṛ','sanskrit'), (2,'ṣ','sanskrit')]
is_possible("dhamma")                      # could this be a Pāli word? (bool)
```

A typo has no phonology, so its cost is 1 against everything (and 0 against
itself) — an extension that preserves the metric (tested). The Sanskrit
diacritics ś, ṣ, ṛ are the exception: in lenient mode they carry real
phonology (ṣ↔s costs 0.460, ś↔s 0.667 — Pāli merged all sibilants into s),
so Sanskrit input prices correctly instead of as noise; strict mode still
rejects them. Lenient mode
restores *comparability* on noisy input, not phonological discrimination:
it cannot tell which letter the typo replaced.
On Pāli-only input, strict and lenient are byte-identical (the lenient path
never triggers).

## What the number means

`distance(w1, w2)` is a **weighted edit distance** over tokenised letters:
substitution = a phonological cost ∈ [0, 1]; insertion/deletion = 1 for
consonants and **0.627 for the epenthetic class** (vowels, y, v, ṃ — the
graphemes whose insertion/loss is ordinary attested transmission variation:
svarabhakti sve/suve, prothesis uṭṭhita/vuṭṭhita, aphaeresis idāni/dāni,
final-ṃ loss sakiṃ/saki, per Geiger). The 0.627 is derived, not tuned: the
cheapest value the metric's triangle inequality allows. Read the total as
"how many edits, discounting how alike the sounds are". Usually
`distance ≤ levenshtein`, but not always: the distance counts heavy units
(a geminate, a nasal+stop cluster) where Levenshtein counts letters, so a
unit against two different letters can cost more than Levenshtein's one
edit (tatra ~ tattha: 1.470 against 1).

The substitution-cost scale (`cost(g1, g2)`), calibrated by the balance
principle — aspirating costs the same as voicing, derived rather than chosen:

| pair | cost | what it is |
|---|---|---|
| k↔k | 0.000 | identical |
| a↔ā | 0.333 | vowel length |
| k↔kh, k↔g | 0.470 | one move in the algebra (aspiration / voicing) |
| k↔gh, k↔ṅ | 0.631 | two moves |
| t↔ṭ, th↔ṭh | 0.601 | places sharing the tongue tip (the coronal bridge) |
| k↔c, kh↔ch | 0.601 | places sharing the tongue body (the dorsal bridge) |
| n↔ṇ, ṅ↔ñ, g↔j | 0.437 | a bridged place change between nasals/voiced stops |
| l↔ḷ | 0.322 | a bridged place change between laterals |
| ṅ↔ṃ | 0.740 | series nasal ↔ niggahīta |
| k↔p, t↔p, c↔ṭ, k↔t | 0.889 | change of place, no shared organ |
| k↔y | 0.831 | guttural ↔ tāluja semivowel (both dorsal) |
| b↔s, k↔r | 1.000 | unrelated |
| insert/delete a, i, u… y, v, ṃ | 0.627 | epenthetic class (derived) |
| insert/delete any consonant | 1.000 | full price |
| tt↔t, tth↔th (degemination) | 0.470 | consonant length: one move (0.377 for voiced, ~0.30 for sonorants) |
| kk↔gg, nt↔nd | 0.470 | a change inside a heavy unit costs what it costs alone (k↔g, t↔d) |
| tt↔nt, ṅgh↔ṃgh | 0.631 / 0.740 | geminate against cluster, or two clusters: the half that differs (t↔n, ṅ↔ṃ) |
| insert/delete a heavy unit (tt, nt) | 1.327 | derived: the cheapest route through a single token (tt → v → ∅) |
| ṣ↔s, ś↔s (lenient) | 0.460 / 0.667 | Sanskrit sibilants, real phonology |

Rules of thumb for applications: `< 0.5` per substituted letter ≈ a plausible
variant of the same etymon; a whole word at `distance < 1.0` is usually a
scribal variant or a close inflected form.

The scalar is a deliberate compression; when you need the detail behind it,
`alignment(w1, w2)` returns the optimal edit script — which letters were
kept, substituted, inserted or deleted, each with its cost. The script's
costs sum exactly to `distance(w1, w2)`, so nothing is lost between the two
views: `distance` answers "how far", `alignment` answers "along which path".

```python
from abugida import alignment
[op for op in alignment("saṅgha", "saṃgha") if op[0] != "keep"]
# → [('sub', 'ṅ', 'ṃ', 0.7403...)]
```

### A budget that scales with the word

Pāli compounds are long, and a fixed θ is progressively stricter on them:
three cheap vowel alternations cost the same in a 22-token compound as in a
4-token word but mean far less. Measured on DPD, agreement with its
`var_phonetic` falls from 84.2% on words of ≤5 tokens to 72.2% on those of
13 or more.

```python
lex.variants(relative=True)     # cut on distance / max(token length)
```

The noisy-channel reading motivates it: if each position can be corrupted
independently, a whole word's negative log-likelihood grows with its length.
**Measured at matched candidate volume: +2 to +9 points across the range**,
best in the low-volume region (+8.7 at 0.76 candidates per lemma). `theta`
defaults to `ONE_MOVE / median_length()`, derived from your lexicon.

One caveat, and it is why this is a `variants` option rather than a distance:
`distance/n` is **not a metric** — it violates the triangle inequality (6
cases in 314,432 triples). Use it to cut candidates, never to index them.
`distance` itself keeps the guarantee.

## Choosing θ: what a threshold buys

`ONE_MOVE` is derived structurally — the costliest elementary move — which
says what it *is* without saying what it *buys*. `abugida.channel` answers
that in the currency you care about, by fitting the noisy-channel model the
metric already assumes (SPEC §9): `P(true variant | d) = exp(−(c + λd))`.

```python
from abugida import Lexicon, fit_channel

lex = Lexicon(words, normalise=True)
obs = [(d, c in known_variants[q])            # your ground truth
       for q in sample
       for d, c in lex.search(q, k=200, pool=200, max_distance=99)]

ch = fit_channel(obs)
ch.r_squared          # check this FIRST — below ~0.9 the model does not fit
ch.precision_at(0.627)   # what ONE_MOVE admits, on your corpus
ch.theta_for(0.25)       # the threshold for 25% expected precision
```

No constants are shipped: λ and c belong to a corpus, not to Pāli phonology,
and baking in DPD's would put a fitted number inside a package that derives
everything else. Measured on DPD (75k lemmas, `var_phonetic`, λ=4.68, c=−0.84,
R²=0.982):

| θ | expected precision | |
|---|---|---|
| 0.333 | 44% | vowel length |
| 0.470 | 26% | one move in the algebra |
| 0.601 | 14% | a karaṇa bridge |
| **0.627** | **12%** | `ONE_MOVE`, the default |
| 1.000 | 2% | |

Two anchors agree without having been made to: one algebra move sits within
half a percent of the 25%-precision threshold, and `ONE_MOVE` near the 10%
one. Use it the other way round when you have a precision budget — `variants`
with `theta=ch.theta_for(0.25)` yields roughly one true pair in four.

## Formal guarantees

- **`distance` is a true metric.** d(x,x)=0, symmetry and the triangle
  inequality hold for every pair of words, the empty one included: each word
  is segmented once into letters and heavy units (geminates, homorganic
  nasal+stop clusters), the cost is a metric over all 126 tokens (verified
  exhaustively, 2,000,376 triples) and the indels satisfy the triangle
  against it (every pair), so edit distance over one sequence per word is a
  metric by the classical argument. **BK-trees, vp-trees and hierarchical
  clustering are sound at any radius**; the `index.py` BK-tree is exact by
  proof. Until 2026-10-13 alignment transitions let each comparison choose
  how to read a geminate, and the inequality failed (`d("makka","saṅgha")`
  2.262 > 2.065 through `magga`); `docs/c-core.md` and
  `eval/triangle_geminates.py` have the account.
- Deterministic and stateless; `cost` carries an internal LRU cache.
- Complexity: O(|w1|·|w2|) per pair (dynamic programming), with |w| in
  tokenised letters, not Unicode characters.

## Performance and bulk search

For searching large lexicons (tested against 38,819 DPD lemmas):

```python
from abugida import distance, tokenize

lexicon = [...]                                  # your IAST words
tokens = {w: tokenize(w) for w in lexicon}       # 1) pre-tokenise once

def search(query, k=5):
    lq = len(tokenize(query))
    candidates = (w for w in lexicon
                  if abs(len(tokens[w]) - lq) <= 2)   # 2) length pruning
    return sorted((distance(query, w), w) for w in candidates)[:k]
```

Length pruning is safe for near neighbours: each unit of length difference
costs ≥ the epenthetic weight (0.627). Order of magnitude with the C core
(the default): ~0.8 µs per pair of short words and ~12 µs for a 39-token
compound, so a 200-candidate hybrid re-rank is under a millisecond and a full
38k-lemma scan under a second. The pure-Python reference is 19–32× slower —
~16 µs and ~384 µs for those two — and its figures are the ones to use when
comparing against anything measured before the C core existed
(`docs/c-core.md` has both columns and `tools/benchmark.py` reproduces them).
Either way, for hot serving: hybrid prefilter, pre-tokenise, prune.

## Levenshtein on equal terms

The table below this one compares the phonological metric against a bare
Levenshtein, and that comparison is generous to us: the pipeline's two
biggest components — `normalise=True` and `relative=True` — are not
properties of the metric, and a flat measure can use both. Held to the
standard this project applies elsewhere, here is the same comparison with
every upgrade available to both, at matched candidate volume and from an
identical pool (`eval/head_to_head.py`). The figures are agreement with
DPD's `var_phonetic`, as everywhere on this page:

| system | 0.5 | 1.0 | 2.0 | 4.0 | 8.0 cand/lemma |
|---|---|---|---|---|---|
| levenshtein | — | — | — | 74.9 | 79.4 |
| lev + normalisation | — | — | — | 81.9 | 85.9 |
| lev + norm + relative | 36.0 | 55.8 | 73.3 | 86.2 | **91.6** |
| phonological | — | 45.4 | 67.4 | 77.6 | 83.6 |
| phon + normalisation | — | 53.1 | 78.1 | 84.4 | 89.4 |
| **phon + norm + relative** | **36.4** | **61.4** | **80.7** | **87.2** | 90.6 |

(Measured 2026-10-13, after the heavy units, on the 5,143-pair build. The
table before them, on the August build: best against best +1.4 / +5.0 /
+7.1 / +3.0 / +0.8. The Levenshtein rows moved as well, so the shift is the
lexicon as much as the units.)

**The pipeline matters more than the metric.** Levenshtein with normalisation
and a relative threshold (86.2) beats the *bare* phonological metric (77.6)
by nine points. If you take only one thing from this page, take the pipeline —
it is largely metric-agnostic.

**On equal terms the metric's margin is narrow, and it lives at low volume**:
+5.6 points at 1 candidate per lemma and +7.4 at 2, but +0.4 at 0.5, +1.0 at
4 and −1.0 at 8, where dressed Levenshtein is ahead. Not the ~20 points a
bare-baseline comparison implies.

**Where it matters is at low volume.** A dash means the system cannot reach
that volume at all: bare Levenshtein's costs are integers, so it has no
threshold between "one edit" and "none". A relative threshold gives it
fractional cuts and so low volumes too, and that is where the metric's lead
lives (+5.6 at 1, +7.4 at 2 candidates per lemma) — the range where an
integration with a precision budget works. That is the same property behind its 167 distinct
values against Levenshtein's 7, and it is why its margin on top-1 *ranking*
(the table below) is far larger than its margin on agreement.

In one line: **the metric buys resolution, not coverage.** Coverage is bought
by the pipeline; resolution is what lets you spend it cheaply.

## Which one should I use?

Ground-truth evaluation against the full DPD lexicon
(`eval/compare_levenshtein.py`, details in `SPEC.md §11`):

| task (expected top-1) | phonological | levenshtein |
|---|---|---|
| scribal corruption → original (n=400) | **95.2%** | 81.4% |
| sandhi spelling → assimilated form (n=40) | **87.5%** | 83.8% |
| Sanskrit → Pāli reflex (tadbhava, n=12) | **58.3%** | 36.1% |

**Use `distance`** for: collating manuscript variants, linking assimilated
and unassimilated forms, detecting loanwords and reflexes, and
**variant-candidate generation between headwords** — compared with
DPD's 66 hand-written PHONETIC_RULES (`eval/phonetic_rules.py`), all of
the rules' real variant pairs lie within θ = max rule cost (AUC 0.829), and
the metric also prices low a family the rule list does not contain (the
aspiration pairs).
For a user-facing search box, match the measure to the error mix first
(see below): on typo/fragment-dominated traffic, char-level matching plus
a prefix route wins. The measured reason: Levenshtein reaches the top of the ranking
with 1.6–2.8 tied candidates and guesses; the phonological distance almost
never ties.

And in **open vocabulary** — comparing forms that appear in no dictionary
(misspellings, unrecorded variants), which is where a metric must stand on
its own — the gap is total: telling a plausible scribal variant from an
arbitrary mutation with the same number of edits, the phonological distance
scores 88–96% and Levenshtein sits at chance (50%), because with no lexicon
to disambiguate every edit weighs the same (`eval/open_vocabulary.py`). The
comparator consults no lexicon: any two IAST strings are comparable.

A third, dictionary-free check — 30 discrimination triples where linguistics
fixes the answer, covering vowel length, aspiration, voicing, place, nasals,
clusters, Sanskrit reflexes and morphology (`tests/test_battery.py`, run it
directly to print the table):

| measure | triples won | distinct values over 190 pairs |
|---|---|---|
| phonological | **29 / 30** | 175 |
| levenshtein | 8 / 30 | 7 |

Levenshtein wins exactly the cases where the edit *count* differs; wherever
both alternatives are one edit away — the normal situation for manuscript
variants — it ties.

**Use `levenshtein`** for: quick bounds, exact-but-for-a-typo deduplication,
or when you need comparability with other systems. It is computed over the
same tokenisation (kh = 1 letter), so it is the fair baseline — fairer than
Levenshtein over raw Unicode characters, which splits digraphs.

### Match the measure to the error model

There is no absolute winner: an independent benchmark (full 74,438-lemma DPD
lexicon, no length restriction, n=150 per scenario, 2026-08) measured the
crossover precisely:

| error model | best measure | phonological | char-level rapidfuzz |
|---|---|---|---|
| keyboard typos (random ASCII edits) | **rapidfuzz** | 80.0% | 87.3% |
| scribal/phonological confusions | **phonological** | **100%** (no ties) | 88.7% |

Why the phonological distance loses on keyboard typos — three mechanisms,
all by design:

1. A random ASCII character (`q`, `x`, `w`…) is not a Pāli grapheme: strict
   tokenisation rejects it (`lenient=True` absorbs it at uniform cost 1 —
   restoring comparability, not discrimination).
2. A typo that straddles a digraph boundary changes the token count
   (dhamma → hdamma is 5 vs 6 tokens), which token-level measures amplify.
3. There is no transposition operation: swapped letters cost ~2 edits, where
   ratio-style measures treat them benignly.

Keyboard noise is phonologically arbitrary; a phonological metric has
nothing to grip there. The deployment decision is a measured, universal
rule, free of population bias (`eval/decision_curve.py`): accuracy over any
error mix is LINEAR in the typo share p (each query is one error type or
the other, so the mix only reweights two fixed accuracies), which gives a
single crossover —

    deploy the hybrid  ⇔  your typo share p < p* = 56.8%  (95% CI 45–69%)

p is the only population-dependent number. Measure it on your own traffic
with `eval/profile_error_mix.py` (reads uvicorn-style logs or bare query
lists; lexicon pluggable via --lexicon). Two properties of the tool matter:

- **Classification is metric-free.** A miss counts as phonological only if
  a lexicon word is reachable through 1–2 substitutions from the documented
  confusion table; typo-like only via plain character edits. The distance
  whose adoption is being decided is never consulted — an earlier version
  used it and inflated the phonological share (p = 15% → 59% on the same
  sample once the circularity was removed, flipping the verdict). A
  classifier must not vote for itself.
- **It reports decision coverage**: the share of misses the p-rule actually
  governs. Prefixes from incremental typing, morphological coverage gaps
  and fragments are excluded from p because no fuzzy measure should "fix"
  them — and if they dominate your traffic, the tool says so: optimise
  those routes first.

The one available sample (local scholar traffic, n = 27 true errors, below
the n ≥ 30 threshold the tool itself enforces) measured p = 59% with 53%
decision coverage — illustrative only; measure your own.

Two follow-up measurements from the same independent benchmark, useful when
integrating behind an existing search pipeline:

- **An upstream ASCII-normalisation route does not skim the phonological
  cases.** Such routes (index by `unidecode(headword)`, look up the raw
  query) only fire when the query is typed entirely without diacritics: a
  single residual diacritic breaks the key, and confusions in the
  ASCII→diacritic direction (a→ā — the modal error, 91 of 300 in the
  sample) cannot be intercepted by construction. Measured interception: 4%.
  On the surviving 96%, the hybrid kept +10.8 points over char-level
  matching (99.3% vs 88.5%).
- The most frequent real confusions are vowel-length in the ASCII→diacritic
  direction (a→ā, i→ī, u→ū: 141 of 300) — which is this metric's cheapest,
  most reliable discrimination (cost 0.333 against ≥0.47 for anything
  else).

### The hybrid: rapidfuzz prefilter, phonological re-rank

Measured at 12 ms/query on the full DPD lexicon (~70× faster than pure
Python `distance`, same 100% on phonological errors, and the prefilter loses
nothing because rapidfuzz's acc@10 is 100% there — the truth is always in
the re-ranked pool):

```python
from rapidfuzz import process
from abugida import distance

def search(query, lexicon, k=5, pool_size=200):
    pool = [w for w, _, _ in process.extract(query, lexicon, limit=pool_size)]
    return sorted((distance(query, w, lenient=True), w) for w in pool)[:k]
```

`lenient=True` covers mechanism 1 better than falling back to the raw
rapidfuzz order: an untokenisable query still ranks phonologically on its
intact remainder (qamma finds kamma at 1.0, while magga sits beyond 2).

## Integration adapter: `Lexicon`

The surface an application needs, with no algebra in sight and no input
that raises — generic over any word list:

```python
from abugida import Lexicon, ONE_MOVE

lex = Lexicon(words)                     # pre-normalises and tokenises once
lex.search("qīha")                       # [(1.0, 'sīha'), …] — typo-safe
lex.search("!!??", max_distance=1.5)     # [] — noise thresholds to nothing
for a, b, d, tag in lex.variants():      # variant-candidate generation
    print(a, b, d, tag)                  # sve suve 0.627 "+u"
```

`variants(theta=ONE_MOVE)` yields headword pairs within one
attested-variation move of each other, labelled by `edit_tag` with the
edits connecting them ("t↔ṭ", "+a", "−h") — the automatic equivalent of
DPD's hand-written `rule:x<->y` tags. ONE_MOVE (0.627) is derived, not
picked: the costliest single attested move the metric knows, agreeing with
the measured median of DPD's 66 hand rules. Validated at scale: ~10 ms per
lemma against 71k (a full sweep is a ~12-minute batch). The generator
over-generates by design and expects a curation step, like the hand rules
it replaces. Install with the prefilter: `pip install abugida[speed]`.

**A second criterion, for pairs no threshold reaches.** If you have
morphological constructions for your words (DPD's `construction` field, or
anything of the shape `a + b + c` with `>` for derivations), pass them:

```python
lex.variants(constructions={"agamā": "a + √gam + ā", "agā": "a + √gam + ā"})
# → ("agamā", "agā", 1.627, "=construction")
```

Words whose constituents agree as a multiset are paired whatever their
distance. It reaches pairs the metric cannot: `abhikkhaṇaṃ ~ abhiṇhaṃ`
(2.37), `agamā ~ agā` (1.63). This is a lexical fact rather than a
phonological one, so abugida only groups the data you supply — it still owns
no lexicon.

### The recommended pipeline, measured

Phonology first, metric second, lexical facts last. All figures are
agreement with DPD — the share of the 5,002 pairs in its `var_phonetic` —
at θ = `ONE_MOVE`:

| pipeline | agreement with DPD | cand/lemma |
|---|---|---|
| `distance` alone | 63.6% | 0.84 |
| + `assimilate_word` (niggahīta) | 68.8% | 0.84 |
| + `contract_word` (`aya`→`e`, `ava`→`o`, `ayi`→`e`) | 78.2% | 0.84 |
| + `constructions=` | **82.0%** | 0.92 |

```python
lex = Lexicon(words, normalise=True)          # phonology first
lex.variants(constructions=my_constructions)  # lexical facts last
```

`normalise=True` is the whole pipeline in one flag: it compares words through
`phonological_form` (sandhi resolved, then vowel contraction) while keys and
results stay your own words — `contract_word` alone maps 533 distinct DPD
lemmas onto identical strings, so the normalisation is for MEASUREMENT only.

Normalising does draw non-variants closer as well, so it is not free:
candidates per lemma rise about 25% at a fixed θ. The comparison that matters
is at equal volume, and it survives it — **+6 to +13 points across the range,
+12.7 at the operating point**. For scale, reaching 83.9% with the metric
alone takes θ≈1.3 and 6.6 candidates per lemma. If you take one thing from
this document, take this table.

## Full API

| function | signature | description |
|---|---|---|
| `distance` | `(w1, w2, lenient=False) -> float` | phonological metric between words |
| `levenshtein` | `(w1: str, w2: str) -> int` | baseline, same tokenisation |
| `cost` | `(g1: str, g2: str) -> float` | substitution cost between letters, [0,1], a metric |
| `neighbors` | `(word, candidates, k=5) -> [(dist, lev, word)]` | k nearest, both measures |
| `algebraic_cost` | `(x: A, y: A) -> int` | ⊗-generator moves between algebra values, {0,1,2} |
| `alignment` | `(w1, w2, lenient=False) -> [(op, from, to, cost)]` | the optimal edit script; its costs sum exactly to `distance` |
| `diagnose` | `(word) -> [(index, char, kind)]` | non-Pāli characters in the input, kind ∈ {sanskrit, unknown}; never raises |

Supporting helpers, all usable on their own: `tokenize`, `normalize`,
`transcribe`, `is_possible`, `pseudoword`, `assimilate_word`, `sandhi_join`,
`sort_words`, `sort_key`, `ALPHABET`.

### Generating candidates

Two criteria, in increasing strength (SPEC §8 and §13.1):

| function | question it answers |
|---|---|
| `is_possible(w)` / `pseudoword(rng)` | is this a legal sequence of Pāli syllables? |
| `is_formable(w)` / `pseudoform(rng)` | could it also be FORMED — base + ending? |

`pseudoform` builds root → base → ending as the grammarians do and returns
the analysis with the word, so no candidate is unexplained:

```python
from abugida import pseudoform, is_formable
f = pseudoform(rng)
f.word, f.root, f.base, f.ending, f.category
# ('taraṇesu', 'tar', 'taraṇa', 'esu', 'action noun, loc pl m/n')

is_formable("pacati")    # True
is_formable("kaṭubha")   # False — legal syllables, not a formable word
```

Formability is strictly stronger: measured over 20,000 phonotactic
pseudo-words, requiring a real ending over a syllabic base prunes 63.6%,
and requiring an ending of two or more graphemes prunes 91.1%. Attestation
is not part of the criterion — the generator consults no dictionary — but
as a check on the junction rules, 47.9% of everything it can build turns
out to be attested Pāli.

## Agreement with DPD is not accuracy

Every percentage on this page measured against `var_phonetic` — the field of
the Digital Pāḷi Dictionary listing variant pairs, 5,002 of them in the August
2026 build — is **agreement with DPD**, and is named so. That field is not
curated from the texts: DPD computes it with its own phonetic rules. A pair
those rules never produce is missing from it and counts against any measure
that finds it; their mistakes count for any measure that copies them. So the
figure answers one question well — how much of what DPD's rules find this
library also finds — and does not answer whether the metric is right. That is asked of
grammars (`eval/oberlies.py`, `eval/geiger.py`), of the open-vocabulary task
and of the hand-written battery — not of `eval/hard_battery.py`, whose
triples are harvested from `var_phonetic` pairs. The comparison holds only while `var_phonetic`
is computed independently of this library. The `recall=` parameter keeps its
name, which is API.

## Known limitations (SPEC §9.7)

- Place adjacency is limited to the two karaṇa bridges: t↔ṭ (shared tongue
  tip) and k↔c (shared tongue body) are cheaper than k↔p, but the eight
  place pairs with no organ in common are not — deliberately. Those two are
  the confusions transmission attests: 84.5% of the place substitutions in
  DPD's `var_phonetic` (72.7% tip, 11.4% body), against 15.9% spread over
  the other eight pairs — 90.1% on the metric-independent positional count.
- The niggahīta ṃ sits further from series nasals than orthographic variation
  alone would suggest (0.740): the distance treats it as the overdetermined
  phonological object it is. To collate spellings, compare the resolved forms
  first: `distance(assimilate_word(w1), assimilate_word(w2))` — **measured**,
  this pipeline raises top-1 on the sandhi-variant task from 87.5% to 100%
  (it fixes every failure). Phonology first, metric second.
- Vowel contraction (`aya`~`e`, `ava`~`o`: abhibhavati ~ abhibhoti) is not
  priced by the metric — those pairs sit above 1.5, since three tokens
  collapse into one. Resolve first, as with the niggahīta:
  `distance(contract_word(w1), contract_word(w2))`. **Measured** on DPD's
  5,002 `var_phonetic` pairs, this lifts agreement with DPD from 63.6% to
  72.0% at θ=0.627 and from 80.0% to 88.2% at θ=1.0, for +2.8% candidate
  volume. It stays a normalisation on purpose: as an alignment transition
  inside `distance` it breaks the triangle inequality (SPEC §6.3).

- A weighted metric buys discrimination at a known price: when the TRUE
  error is an expensive edit (an arbitrary consonant dropped or added,
  1.0), impostor candidates one cheap edit away (vowel length 0.333,
  epenthetic 0.627) can outrank the truth — where a flat measure would let
  the one-edit truth win. Independently measured on an insertion/deletion
  error class: the epenthetic work closed half the gap (82.0% → 89.3%),
  char-level still ahead at 96.0%. Inherent to weighting; mitigated, not
  eliminated.
- Gemination is priced as consonant length: every word is segmented once,
  a geminate and a homorganic nasal+stop cluster each being ONE heavy unit,
  so attha↔atha costs 0.470 — one elementary move, like k↔kh — instead of
  a full deletion, and citta↔cinta 0.631 (the half that differs, t↔n). The
  price of one segmentation: a unit cannot align letter by letter with a
  cluster of two articulations, so Sanskrit-shaped pairs like tatra↔tattha
  cost 1.470 (it was 0.831), and a one-letter change that leaves half a
  geminate (tṭ) costs a broken unit.
- It compares words, not sentences: segment beforehand.

## Foundation

The substitution cost is the truncated angular distance between 14-dimensional
embeddings whose geometry faithfully represents the project's phonological
algebra of Pāli: sounds close in the metric are those separated by few moves
of aspiration/voicing/nasalisation, with the weight between axes **derived**
— not hand-tuned — from the principle that elementary moves should cost the
same. Full theory in `SPEC.md` (§1 the algebra, §4 the embedding, §9 the
distance, §11 the evaluation).
