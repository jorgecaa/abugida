# Using abugida — a briefing you can paste

Self-contained instructions for someone (or something) integrating this
library for the first time. Everything here is verified by
`tests/test_briefing.py`, so it cannot drift from the code.

For the full reference see [comparator.md](comparator.md); for the theory,
`SPEC.md`. If you are going to *modify* the library rather than use it, read
`CLAUDE.md` (the repo's discipline) and `FINDINGS.md` (thirteen things
already measured and closed — it is what stops you repeating work).

---

## abugida — phonological distance for Pāli words (IAST)

Measures phonological proximity between Pāli words and generates variant
pairs. Pure Python, no dependencies (`rapidfuzz` is optional and makes it
much faster).

**Use `Comparator` and nothing else.** The rest of the package is the
theoretical layer underneath; assembling it by hand is the known source of
mistakes.

```python
from abugida import Comparator

cmp = Comparator(lemmas)                   # validates as it builds
cmp.neighbours("dhamma", k=5)              # → [(0.333, 'dhammā'), (0.344, 'damma'), …]
cmp.variants()                             # → (a, b, distance, tag), each pair once
cmp.variants(words=["dhamma"])             # only pairs involving that word
cmp.rejected                               # {word: reason} for anything not indexed
"dhamma" in cmp                            # membership
```

**Recall is named, not numeric.** The table gives each setting's
**agreement with DPD**: the share of the 5,002 pairs in DPD's `var_phonetic`
(the August 2026 build) that it also generates. That field is not a ground
truth — DPD's own rules compute it — so the column says how much of what DPD
finds today you keep, not how often the metric is right:

| `recall=` | agreement with DPD | candidates per lemma |
|---|---|---|
| `"precise"` | 86.2% | 3.6 |
| `"balanced"` *(default)* | 91.4% | 9.1 |
| `"exhaustive"` | 95.1% | 26.6 |

```python
Comparator(lemmas, recall="exhaustive", constructions={...})
```

`constructions` is optional: `{word: "a + √root + b"}` (DPD's `construction`
field). It pairs words of identical formation however far apart they are:
+8 points of agreement with DPD for +0.08 candidates per lemma.

Building is cheap — 1.6 s for DPD's 75k lemmas — and **the index does not
depend on the recall setting**, so comparing settings needs one object:

```python
cmp = Comparator(lemmas)                     # build once
for setting in ("precise", "balanced"):
    rows = cmp.variants(recall=setting)      # re-thresholds only
```

### Input rules

- The constructor takes what you want to **find**; `neighbours` and
  `variants(words=…)` take what you look **with**. One word per entry — no
  sentences, no phrases, no splits.
- Everything is validated as strict IAST. What fails is not indexed and is
  explained in `.rejected`.
- Invalid queries raise `ValueError`. Behind a search box use
  `cmp.neighbours(text, lenient=True)`, which never raises.
- Sanskrit graphemes (`ś ṣ ṛ`) are refused by default;
  `accept="pali+sanskrit"` admits those three and only those three.

### Reading a distance

0 identical after normalisation · 0.333 vowel length · 0.470 one move in the
algebra (aspiration, voicing, degemination) · 0.601 a shared-organ place
change (t↔ṭ, k↔c) · 0.889 a change of place · 1.0 unrelated.

The word distance is a true metric — identity, symmetry, triangle inequality —
over all words, so BK-trees, vp-trees and metric clustering are sound at any
radius. Each word is read once as a sequence of letters and heavy units: a
geminate (`tt`) or a homorganic nasal+stop cluster (`nt`, `ṃk`) is one unit,
priced by the half that differs (`kk↔gg` = `k↔g`, `tt↔nt` = `t↔n`). The price:
a unit cannot align letter by letter with a cluster of two articulations, so
`tatra ~ tattha` is 1.47, more than its one Levenshtein edit.

### Known limits

- **A structural blind spot, and it is not a corner case.** Systematic sound
  change — Sanskritised doublets (`tatra ~ tattha`, 1.47), syllable prothesis
  (`meru ~ sineru`, 2.26) — is correlated edits, and an edit distance assumes
  independent ones. Measured on DPD: 10.0% of the `var_phonetic` pairs sit
  beyond d = 1.0, but the length-relative threshold rescues 71% of
  those, so **3.2% is genuinely out of reach**. And part of that 3.2% is not
  sound change at all — `tumhehi ~ vo`, `asmā ~ no` are suppletive pronouns,
  `obhāsa ~ tejas` a synonym: material the field contains that no
  phonological metric should capture. Use `"exhaustive"` for the reachable
  part; the rest is historical grammar (sound laws), not distance between
  sounds, and out of scope.
- Keyboard noise is not its territory: for ASCII typos a flat matcher does
  better. The metric is a bet on how the error was made, and a slipped finger
  has no articulation.
- Every reference is partial, so measured precision is always a lower bound.

### If you need something this does not allow

`cmp.lexicon` is the layer underneath: permissive, unvalidated, fully public.
You lose the configuration that produces the numbers above, so measure what
you build.
