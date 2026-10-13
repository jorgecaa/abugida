# abugida — a phonological metric for Pāli

A measurement instrument for phonological proximity between Pāli words
(IAST). Not a fuzzy-matching score: a **calibrated scale** — every value
has a phonological reading, every constant a derivation rather than a
tuning — with a **receipt** (the edit path that explains each number) and
**true-metric guarantees** (identity, symmetry, triangle inequality,
verified exhaustively) that make it sound to build structures on.

Pure Python, no dependencies, **no lexicon**: any two IAST strings are
comparable, whether or not they appear in any dictionary.

```python
from abugida import Comparator

cmp = Comparator(words)        # the entry point: validates, pipeline built in
cmp.variants()                 # → (a, b, distance, tag), each pair once
cmp.neighbours("dhamma")       # → [(0.415, 'dhammā'), (0.426, 'damma'), …]
```

Underneath it, the metric itself:

```python
from abugida import distance, alignment

distance("kamma", "khamma")   # 0.470 — one elementary move (aspiration)
distance("kamma", "gamma")    # 0.470 — voicing costs exactly the same (derived)
distance("kamma", "samma")    # 1.0   — unrelated
distance("attha", "atha")     # 0.470 — degemination = consonant length
alignment("saṅgha", "saṃgha") # the receipt: [('sub', 'ṅ', 'ṃ', 0.740), …]
```

The scale, in one column: 0.333 vowel length · 0.470 one algebra move
(aspiration, voicing, degemination) · 0.601 a karaṇa bridge (t↔ṭ, k↔c) ·
0.627 an epenthetic insertion · 0.889 a change of place · 1.0 unrelated.
Generic measures return a count; this returns a measurement.

## What it is for

- **Measuring variation** — manuscript doublets, orthographic variants,
  editions: is this reading one ordinary transmission move away, or three?
- **Explaining** — `alignment`/`edit_tag` give the citable reason behind
  every number.
- **Generating** — `Lexicon(words).variants()` proposes variant pairs with
  automatic edit tags. Compared with DPD's 66 hand-written phonetic rules
  (`eval/phonetic_rules.py`): every rule that produces lemma→lemma pairs is
  within its reach, and it also prices the aspiration pairs (g↔gh, j↔jh…)
  low, which the rule list does not contain. Eight multi-grapheme
  rules sit beyond the cost's reach (`ty↔cc` 1.54, `ṭhā↔ṭhaha` 1.86) — but
  they are rare where it counts: across the 5,002 pairs of DPD's
  `var_phonetic`,
  `ty↔cc` occurs once and `dy↔jj` and `ny↔ññ` not at all. Two of the eight,
  `e↔aya` and `o↔ava`, are handled upstream by `contract_word`.
- **Comparing across systems** — Sanskrit↔Pāli reflexes are priced with real
  phonology (ś/ṣ/ṛ in lenient mode), though a Pāli geminate now stands
  further from a Sanskrit cluster than it did (see Guarantees).
- **Searching**, within its envelope — see below: the error channel, not
  the metric, decides that one.

## Against the generic baseline

Measured against ground truth (full detail and reproduction in `eval/`
and `SPEC.md §14`):

| task | phonological | Levenshtein |
|---|---|---|
| scribal corruption → recover the original (n=400, full DPD lexicon) | **95.2%** | 81.4% |
| sandhi spelling → attested assimilated form (n=40) | **87.5%** (100% with pipeline) | 83.8% |
| Sanskrit → Pāli reflex (*tadbhava*) | **58.3%**, mean rank 2.5 | 36.1%, mean rank 9.5 |
| plausible variant vs. arbitrary mutation, **no dictionary** | **88–96%** | ~50% (chance) |
| discrimination battery, 30 linguistic triples, no dictionary | **30 / 30** | 8 / 30 |

All five rows are current (2026-10-13, after the heavy units). The first three
need the DPD database and were re-run on a newer build (75,733 lemmas); the
Levenshtein column moved too (83.9% → 81.4%, 77.1% → 83.8%), so the change
from the previously published 95.5% / 82.5% is the newer lexicon as much as
the metric, and cannot be read as the units' effect.

The open-vocabulary row is the identity claim: with no lexicon to lean on,
a flat measure cannot tell a plausible variant from an arbitrary mutation —
every edit weighs 1. This metric carries the phonology inside. The typo row
is the honest converse: a metric is a bet on how the error was made, and
keyboard noise has no articulation to measure — on such traffic a flat
matcher plus a prefix route is the right tool, and the docs say exactly
when (a measured crossover rule).

**What this table does not say, stated here rather than buried.** Every row
above is a RANKING task — pick the right word out of a lexicon — and that is
where the metric's resolution decides. On *agreement with DPD* at matched
candidate volume (see below for what that measures), with the pipeline
available to both measures, the margin is far smaller: +5.6 points at 1
candidate per lemma and +7.4 at 2, about even at 4 (+1.0), and dressed
Levenshtein a point ahead at 8. Levenshtein with normalisation and a
length-relative threshold even beats the *bare* phonological metric by nine
points. Most of it comes from the pipeline, which is metric-agnostic.

What the metric keeps is the low-volume regime. Bare Levenshtein cannot work
there at all — its costs are integers, with no threshold between "one edit"
and "none", so it cannot go below ~4 candidates per lemma — and dressed with
a relative threshold it can, but trails the metric by 5–7 points at 1–2
candidates per lemma. The full comparison is
in `docs/comparator.md` and reproduces with `eval/head_to_head.py`. In short:
**the metric buys resolution, the pipeline buys coverage.**

### Agreement with DPD is not accuracy

Several figures in this repository are measured against `var_phonetic`, the
field of the [Digital Pāḷi Dictionary](https://github.com/digitalpalidictionary/dpd-db)
that lists variant pairs (5,002 pairs in the August 2026 build). That field is
not a ground truth: DPD computes it with its own phonetic rules. A figure
against it therefore says how much of what DPD's rules find the metric also
finds — **agreement with DPD** — and is reported under that name. It
describes overlap with one rule system and is no evidence that the metric is
right:
for that, see the table above, the grammar-based checks (`eval/oberlies.py`,
`eval/geiger.py`), the open-vocabulary task and the hand-written battery
(`eval/hard_battery.py` does not count: its triples are harvested from
`var_phonetic` pairs, so it inherits the same population, though its
difficulty is defined without the metric). The comparison holds only
while `var_phonetic` is computed independently of this library.

**Most agreement figures in this repository predate the heavy units**
(2026-10-13, SPEC §14), which changed every distance involving a geminate or
a nasal+stop cluster, and were measured on the August build (5,002 pairs).
The paired measure of the change is on one newer build (5,143 pairs): at
θ = `ONE_MOVE`, 63.2% before the units and **62.6%** after, at the same
candidate volume (0.84 per lemma) — the units cost agreement 0.6 points.
The other figures are kept as measured, with their build.

The mechanism behind the first three rows is measured too: Levenshtein
reaches the top of the ranking with 1.6–2.8 tied candidates and has to
guess; the phonological distance almost never ties.

## Install

```bash
pip install git+https://github.com/jorgecaa/abugida
```

That is all: no runtime dependencies, nothing to configure. pip fetches
Cython for the build and compiles the C core into the package, so the
installed `abugida` needs neither a shared library nor Cython at run time.
The only thing it needs from the machine is a C compiler — on Linux the
system `cc`, on macOS the Xcode command-line tools (`xcode-select
--install`), on Windows the Microsoft C++ Build Tools. Without one the
install still succeeds, with a warning, and the package answers from the
pure-Python reference with the same values, only slower; this says which you
got:

```bash
python -c "from abugida.distance import USING_C; print(USING_C)"   # True = C
```

Requires Python 3.9 or later. `.github/workflows/install.yml` installs it and
runs the suite on Linux, macOS (Apple silicon and Intel) and Windows, at
Python 3.9 and 3.13.

To work on it, clone and install in editable mode from the repository root
(where `pyproject.toml` is), with `pytest` for the 420 tests:

```bash
git clone https://github.com/jorgecaa/abugida && cd abugida
pip install -e . pytest && python -m pytest -q
```

## The C core

The metric is implemented in C, linkable from C and reached from Python
through Cython. Same metric, same numbers — 19× to 32× faster, and a
39-token compound pair goes from 384 µs to 12 µs:

```c
#include "abugida.h"
abugida_word a = ABUGIDA_WORD(buf, 64);
abugida_word_from_text(&a, "kamma", 5, 0, NULL);
abugida_word_distance(&a, &b, &d);
```

```bash
make -C csrc check    # the core's two suites: no Python in the process
```

Every constant in the C tables is **generated from the Python definitions**
(`tools/generate_c_tables.py`), so no number was re-derived or hand-tuned in a
second language, and `tests/test_c_parity.py` requires the two
implementations to agree exactly — over all 7,396 token pairs, the whole
alphabet and a fixed-seed corpus. Four checks hold the arrangement together;
[docs/c-core.md](docs/c-core.md) is the guide, including what is deliberately
*not* in C (Unicode normalisation) and the measured speed table.
[docs/kernel-assessment.md](docs/kernel-assessment.md) answers the next
question — whether the kernel should be written in assembly — with
measurements: no, and it names the restructuring that is worth more.

## Documentation

**Handing this to someone — or something — for the first time?**
[docs/using-abugida.md](docs/using-abugida.md) is a one-page briefing written
to be pasted into a prompt or read on its own. Every claim in it is executed
by `tests/test_briefing.py`, so it cannot drift.

**[docs/comparator.md](docs/comparator.md)** is the full integration
guide: installation, value scale, metric guarantees, bulk-search recipe,
and when to use which measure.

`SPEC.md` is the theoretical foundation: the
phonological algebra, the embedding, and the derivation of every constant.

## What is underneath

The substitution cost is the truncated angular distance between 14-dimensional
embeddings that faithfully represent a phonological algebra of Pāli:

- **Voicing, aspiration and nasality** form a commutative semiring `B × F₃`.
  Its two axioms — that aspiration and nasality cancel each other at each
  voicing level — force the whole structure (the modifier axis must be `Z₃`,
  the voicing axis cannot be `Z₂`).
- **Places of articulation** form a lattice, following the traditional
  *ṭhāna* classification. Compound places are native to that tradition:
  `e` is *kaṇṭhatāluja*, `o` is *kaṇṭhoṭṭhaja*, and the niggahīta `ṃ` sits
  at the top with all five.
- **The weight balancing the two axes is derived, not hand-tuned**: it is
  the unique value making elementary moves cost the same (aspirating `k→kh`
  exactly as much as voicing `k→g`), computed by bisection over the actual
  embeddings.

One consequence worth noting: the traditional recitation order of the 25
*vagga* consonants (`k kh g gh ṅ, c ch j jh ñ, …`) turns out to be exactly
the lexicographic order of the product Place × Algebra. The tradition has
been reciting the semiring in order.

Supporting modules, all usable on their own: IAST normalisation and
tokenisation (`tokenize` — digraphs like `kh` are single letters), sandhi
(`assimilate_word`, `sandhi_join`), executable phonotactics (`is_possible` knows
`dharma` is not Pāli even though every grapheme is), and Pāli alphabetical
ordering (`sort_words`).

Candidate generation comes at two strengths. `pseudoword` inverts the
phonotactics: legal syllable sequences. `pseudoform` (in `morphology`) adds
the second criterion — a candidate should also be **formable**, root + base
+ ending as the grammarians build one, and it returns the analysis with the
word:

```python
pseudoform(rng)   # taraṇesu < tar + taraṇa + -esu (action noun, loc pl m/n)
```

The criterion is the rules, not the dictionary. Its fidelity is measured,
not asserted: of everything it can build, **47.9% turns out to be attested
Pāli** (74.0% of the verb forms) with no dictionary consulted in the
construction. And `is_formable` applies the criterion to strings it did not
build — measured against the phonotactic generator, **roughly nine in ten
phonotactically legal strings are not formable words** (91.1% pruned; 63.6%
under the weakest reading of the criterion, which any vowel-final word
satisfies). Formability is strictly stronger than possibility.

## Evaluation

Two complementary evaluations, both reproducible:

- `eval/compare_levenshtein.py` — **closed vocabulary**: retrieval against
  the full DPD lexicon. Measures the practical task (searching a real
  dictionary). Requires the DPD database.
- `eval/open_vocabulary.py` — **open vocabulary**: forced choice with no lexicon at
  all, over phonotactically legal pseudo-words (99.5–99.8% certified absent
  from DPD). Measures the metric itself. Runs in under a second.
- `tests/test_battery.py` — **side-by-side battery**: 30 discrimination
  triples (base, nearer, farther) where linguistics fixes the answer, across
  vowel length, aspiration, voicing, place, nasals, clusters, Sanskrit
  reflexes and morphology. Needs no dictionary; run it directly to print the
  comparison table. It also measures the mechanism: over 190 word pairs the
  phonological distance yields 167 distinct values, Levenshtein 7 (175 before
  the heavy units, which price a geminate change like the single one).

The second exists because the first, on its own, would be misleading: judging
a metric by dictionary retrieval inherits the dictionary's closed world, and
never measures comparisons between forms no dictionary records — which is
precisely where a metric has to stand on its own.

## Guarantees and limitations

`distance` is a **true metric**: identity, symmetry and the triangle
inequality hold for every pair of words, the empty one included. It rests on
three conditions over single tokens, each verified exhaustively — the
substitution cost is a metric over all 126 tokens (letters, heavy units,
Sanskrit phonemes: 2,000,376 triples), and the indels satisfy the triangle
against it over every pair — and on one structural fact: each word is
segmented ONCE, before measuring, with geminates and homorganic nasal+stop
clusters as single heavy units (SPEC §14). Edit distance over one sequence
per word is then a metric by the classical argument.

It was not always so. Until 2026-10-13 alignment transitions let each
comparison decide whether a doubled pair was one long consonant or two
letters, and composition broke:

```
d("makka", "saṅgha") = 2.262374                      (then)
  > d("makka", "magga") + d("magga", "saṅgha") = 2.064786
d("makka", "saṅgha") = 1.631187 <= 0.469738 + 1.343898   (now)
```

`eval/triangle_geminates.py` traces every violation to that one cause and
measures the repairs that keep per-comparison segmentation (none works).

**What the units cost.** A heavy unit cannot align letter by letter with a
cluster of two articulations, so Sanskrit-to-Pāli correspondences of that
shape moved away: `tatra ~ tattha` went from 0.831 to 1.470, and Sanskrit
forms within two moves of their Pāli reflex fell from 40.0% to 31.6%
(Oberlies) and from 47.8% to 35.0% (Geiger); ranking Sanskrit forms against
the whole lexicon, the Geiger tadbhava task fell from 32.8% to 24.5%, measured
paired against each historical `distance` (by a script that replayed the
repository's earlier history, retired with it). Pāli doublets did not move
(Oberlies 92.5% -> 91.8% within two moves, Geiger unchanged). A one-letter
change that breaks a unit (a half-geminate, `tṭ`) also costs a broken unit;
on strings Pāli writes, the open-vocabulary task is unchanged.

**BK-trees, vp-trees and metric clustering are sound at any radius.** The
BK-tree in `index.py` is exact by proof, and `tests/test_index.py` still
checks it against an exhaustive scan. Everything threshold-based
(`Lexicon.search`, `Lexicon.variants`, every agreement figure here) assumes
no metric property at all.

Known limitations, in the open:

- Keyboard typos are outside the envelope: random ASCII noise is
  phonologically arbitrary (and often not even tokenisable), so char-level
  fuzzy matchers beat this metric there — an independent benchmark measured
  80% vs 87% on typos, and 100% vs 89% in this metric's favour on
  phonological confusions. The deployment rule is universal and measured:
  hybrid (rapidfuzz prefilter → phonological re-rank) iff your traffic's
  typo share is below p* = 56.8% (95% CI 45–69%); measure your share with
  `eval/profile_error_mix.py`. See docs/comparator.md.

- Place adjacency covers exactly the attested confusions: `t`↔`ṭ` (shared
  tongue tip) and `k`↔`c` (shared tongue body) are cheaper than `k`↔`p` via
  the two karaṇa bridges — the traditional active articulator as a shared
  half-place. The eight place pairs with no organ in common get no
  adjacency, deliberately; they are 15.9% of the place substitutions in
  DPD's `var_phonetic` against the bridges' 84.1%.
- The niggahīta `ṃ` sits further from series nasals than orthographic
  variation alone would suggest, because the metric treats it as the
  overdetermined phonological object it is. For collating spellings, resolve
  first: `distance(assimilate_word(w1), assimilate_word(w2))` — measured, this
  raises the sandhi task from 87.5% to 100%. The same shape applies to vowel
    contraction: `contract_word` (`aya`~`e`, `ava`~`o`). Both are
  normalisations rather than edit operations, and deliberately so —
  contraction as an alignment transition breaks the triangle inequality
  (SPEC §9.1). **Measured together, phonology first and metric second lifts
  agreement with DPD from 62.0% to 77.5%** — +6 to +13 points even after
  matching candidate volume — and `Lexicon(words, normalise=True)` turns the
  whole pipeline on in one flag (`docs/comparator.md`).
- It compares words, not sentences.

## Provenance

The project began as an exploration of a feature algebra for Pāli phonology
and was refocused on the comparator on 2026-08-01. The exploratory theory
(paraconsistent LP truth tables, a consequence relation over the place
lattice, the akṣara symbol, a 20-word pangrammatic language `L`) remains
documented in `SPEC.md` (the repository was restarted from a single commit
on 2026-10-13, so its code is no longer in this history); its operative ideas
survive inside the live code — the lattice meet *is* the assimilation rule in
`assimilate` and in the phonotactics.

## License

The code and the documentation are in the public domain, dedicated under
[CC0 1.0 Universal](LICENSE). The dedication does not reach the third-party
data some evaluation scripts read:
extractions from Oberlies' and Geiger's grammars and from DPD are not in this
repository or in any distribution, and each user keeps a local copy in
`eval/data/` — see [NOTICE](NOTICE) and `eval/_data.py`.

## Data used in evaluation

Some evaluation scripts read the
[Digital Pāḷi Dictionary](https://github.com/digitalpalidictionary/dpd-db)
(DPD) database. The library itself does not depend on it; DPD is used as a lexicon
of real Pāli, as the reference for agreement figures (never as a ground
truth: see "Agreement with DPD is not accuracy"), and in the open-vocabulary
evaluation only as a negative control.
