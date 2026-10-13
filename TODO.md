# TODO

Open threads, with what has already been measured so nobody re-measures it.
Numbers here trace to `eval/variant_curve.py` unless stated otherwise.

## Reference population: use `var_phonetic`, not `variant`

`dpd_headwords.var_phonetic` (5,002 pairs, both sides real lemmas, median
distance 0.530) is the right population for variant work. `variant` (1,024
pairs) mixes phonetic variation with part-whole relations
(`sumanā ~ vuḍḍhapabbajitasumanā`), compound permutation
(`sampannavijjācaraṇa ~ vijjācaraṇasampanna`), whole phrases and outright
synonyms (`karitvā ~ vihacca`, `phāletvā ~ uppāṭiya`). Measuring a
phonological metric against it understates the metric by ~35 points and
sets targets no edit distance should hit.

Any figure quoted from before 2026-08-01 was measured against the wrong
population and should be re-derived. ("Recall" in this file, from here on,
means agreement with DPD in the sense of the next section.)

## Ground truth is circular: `var_phonetic` is an algorithm's output (2026-10-13)

`var_phonetic` is not curated by hand from the texts: DPD computes it with its
own rule set (`PHONETIC_RULES`, an algorithm weaker than this metric). Recall
against it therefore measures agreement with that algorithm, not with the
language: a pair the rules never generate is missing from the truth and
counts against any metric that finds it, and the rules' errors count for any
metric that imitates them. Every recall figure in this repository, and every
decision closed on one, rests on that population. Nothing has been re-measured
yet; the decisions are not shown wrong, only unsupported by that number.

**Decision (2026-10-13): the figures are kept, renamed, and taken out of the
headlines.** What they measure is real but narrow: how much of what
one rule system finds the metric also finds, and which pairs differ. So every
figure against `var_phonetic` is called **agreement with DPD**
(never "recall" or "accuracy", never "curated", never "ground truth"), it
names the build it was measured on (5,002 pairs, August 2026), and no
headline argues the metric's quality from it: that is what the grammar
(Oberlies, Geiger), the hand-written battery and the open-vocabulary task
are for. Not the hard battery: its triples are harvested from `var_phonetic`
pairs, so it shares the population, though its difficulty is defined
without the metric.
The `recall=` parameter keeps its name; it is API. The comparison holds only
while `var_phonetic` is computed independently of this library.

DPD stays usable as INFORMATION (the lexicon, `construction`, `root_key`), not
as the judge. The DPD dependency of the evaluation is explicit since the same
date: every script in `eval/` needs `--dpd [PATH]` before it opens the
database (`eval/_dpd.py`). Re-run on a newer DPD (5,143 `var_phonetic` pairs,
75,733 lemmas), `variant_curve.py` gives 63.2% at θ = ONE_MOVE against the
published 63.6% on 5,002 pairs; the change of population alone moves it.
On that same build after the heavy units (2026-10-13): **62.6%**, same
volume (0.84 cand/lemma) — the units cost 0.6 points of agreement.

Part of `var_phonetic` is not phonetic at all, read pair by pair in the
`hard_battery.json` sample: the optional aorist augment (`bravi ~ abravi`,
like `hosi ~ ahosi`), suffix pairs (`-eyya ~ -īya`, `-tta ~ -tā`, `-ika ~
-iya`), prefix sandhi (`abbhaññāsi ~ abhiññāsi`), blends Oberlies explains as
such (`abbhidā ~ abhidā`), and at least one pair of different words
(`loṇapallavagga ~ loṇaphalavagga`).

### An independent ground truth: Oberlies (`oberlies_cases.json`, local data)

Oberlies' *Pali* grammar is the current reference; Geiger's is older. The case
file holds 740 Sanskrit→Pāli pairs and 134 Pāli doublets read from it (Geiger:
157 and 24) — word pairs only, with the page of the scan each came from; how
they were read and what was excluded is in its `note`. **Letters
cross-checked, not yet validated** (2026-10-13): every Pāli form was looked
for on its own page in the scan's OCR text layer, the OCR's misreadings
modelled (`eval/validation/ocr_crosscheck.py`, which needs your copy of the
PDF); the forms it could not find were read in the image, and three slips
came out and were corrected — `punapunaṃ` for punappunaṃ (p. 45), and two
Pāli doublets filed as Sanskrit -> Pāli, `pāricariyā ~ paricaryā` (p. 54) and
`anupādā ~ anupādāya` (p. 55). That check shares the scan with the reading,
sees no diacritics and does not count what is missing, so the independent
review of `eval/validation/` still stands: a random sample with planted errors as the
control that the check can fail, and a completeness count on the same
pages. Every figure below is `eval/oberlies.py`, which needs no DPD.

What the grammar confirms: the alternations it documents inside Pāli are
mostly priced under one move — aspiration (k~kh, §14.1), voicing (§14.2),
ḍ~ḷ, r~l, l~ḷ, n~ṇ, and t~ṭ and kh~ch through the karaṇa bridges; svarabhakti
i and loss of a cost the epenthetic weight; every single~geminate doublet
(§14.13, §14.16, §16 rem., §18.7, §20) costs 0.60–0.75 of a move.

What it does not, documented and left unchanged:

- [ ] **Alternations priced above one move.** s~ch 1.59× (§13, `chava` ←
      śava), t~c 1.42× (§16.1, ty > cc), s~h 1.17× (§18.4), p~v 1.12×
      (§14.2 n. 6; inside Pāli `āpeti ~ āveti`), and d~j 1.01× (`dighacchā ~
      jighacchā`, `dūta ~ jūta`) — d~j is 0.631 against ONE_MOVE 0.627, so a
      one-move threshold loses those pairs by 0.004. Inside Pāli the evidence
      is thin; the rest is Sanskrit→Pāli. DPD's sample has almost none of
      them, so calibrating against DPD could never have lowered them.
      **Swept the whole book for Pāli doublets (2026-10-13)**: every '~' in
      the text and the index read in the page image, 37 doublets added (134
      in all). Inside Pāli the counts are now s~ch 0, t~c 0, s~h 1, p~v 3
      (`āpeti ~ āveti`, `hupeyya ~ huveyya`), d~j 3. So s~ch and t~c are
      correspondences between Sanskrit and Pāli, not variation within Pāli,
      and a metric of Pāli against Pāli is right to price them as a change
      of place: lowering them would buy nothing on its own population. p~v
      and d~j stay open, with three doublets each — too few to move a cost
      on, enough to say they occur.
- [x] **The phonotactics rejected initial nh-/mh-** (fixed 2026-10-13).
      `is_possible` refused `nhāyati`, `nhāru`, `nhusā`, `mhita`; Oberlies
      §15.1 treats nh and mh as unitary aspirated nasals that occur
      word-initially. `_valid_onset` now admits n/m + h, and only those: the
      other sonorant+h clusters stay word-internal (pinned by
      `tests/test_phonotactics.py`). No generated output moves (`pseudoword`
      opens with one consonant; no root in `ROOTS` starts with nh/mh). The
      SPEC §13 calibration had no script; `phonotactics_calibration.py
      --dpd` reproduces it: 98.99% of 74,800 lemmas, the 0.06-point rise
      over 98.93% being the 47 nh/mh lemmas.
- [x] **The phonotactics rejected word-internal st** (fixed 2026-10-13).
      `bhastā`, `ghasta`, `viddhasta`, `anuddhasta` were pinned as
      impossible, "a marginal Sanskritism"; Oberlies §16 rem. (a), p. 102,
      lists (vaṅka)ghasta- and bhasta- 'bag' (Th 1151) among the sibilant
      clusters Pāli leaves unassimilated, beside asnāti and bhasma-, which
      were already accepted. Every other example in that remark (ky gy my
      ly vy) already passed. Family f now takes s+t, word-internally only
      (`stana`, `stūpa` stay impossible). Consequence, accepted: `hasta` is
      now possible, and `pseudoword` draws from a wider cluster set, so
      `open_vocabulary.py` moves by tenths (SPEC §14 table updated; the
      `--morphological` variant and the morphological generator's 3,920
      words are identical). `phonotactics_calibration.py --dpd`: 26 more
      lemmas accepted (99.03%), all Pāli; the 64 left are read in SPEC §13.
- **Quantity exchange (law of mora, §3.3) is priced as two edits** —
  `appeti ~ āpeti` 1.28×, `soppati ~ supati` 1.44×, `patta ~ pātī` 1.29×.
  This is correct and stays: the two forms differ in two phonetic segments;
  their equivalence is one of syllable weight, which is metre, not phonetic
  distance.
- **Consonant length costs one feature**, like voicing or aspiration (p~pp
  0.470 = p~b = p~ph; a~ā 0.333). Length is distinctive in Pāli (`mata ~
  matta`), so a one-move threshold also brings minimal length pairs
  together; how many fall inside it over a lexicon is not measured.
- Sanskrit→Pāli cost goes mostly to the OIA cluster laws (`r`, `ṣ`, `s`, `n`,
  `t` deleted at full cost; `ṣ → kh`), which a metric built for Pāli against
  Pāli does not model. A limit for lenient use on Sanskrit, not a defect.

## Order of investigation

Priority, not a wish list. The ordering is derived from what the 2026-08-02
experiments actually showed, and each phase states what would make it fail.

**Phase 0 — fix the instrument. DONE 2026-08-02** (`eval/protocol.py`,
`eval/hard_battery.py`). Findings below; the rest of the phase description is
kept because it says why.

- The hard battery scores **50.6% [48.8, 52.4]** over 3,000 triples where
  Levenshtein ties by construction (Levenshtein itself: 0%, all ties). Ample
  headroom, unlike the hand-written battery's 29/30. (Heavy units,
  2026-10-13: 50.9% [49.1, 52.7]; the battery 30/30.)
- Split by edit count it exposes something the old instrument could not:
  lev=1 62.2%, lev=2 52.0%, **lev=3 19.9% — below chance**. That is the
  multi-grapheme alternations of Phase 4 (`ty↔cc`, `e↔aya`, `ṭhā↔ṭhaha`,
  live at 1.5–1.8) showing up as a measurable deficit rather than an
  anecdote.
- Re-judging the concave warp with the paired test **changed the verdict on
  one of its two columns**: ΔAUC 95% CI [+0.0074, +0.0156] is DECISIVE, not
  "inside the noise" as recorded from overlapping marginal intervals. Top-1
  remains indistinguishable (5 vs 5 discordant, McNemar p=1.000). The
  reversal still stands — it rested on iso-volume recall, not on AUC — but
  the entry below has been corrected, and this is exactly the class of error
  Phase 0 existed to stop.

*Original rationale:* The battery is saturated: it holds 29/29 across a sweep that takes
`a↔ā` down to 0.073, so it can only detect regressions. Meanwhile AUC on hard
negatives and the iso-volume recall curve both carry roughly ±2 points of
noise (one standard error on ~480 queries), which is larger than most of the
gains chased so far. Concretely: (a) build a HARD battery — triples where the
live metric already ties or fails, harvested from `var_phonetic` rather than
hand-written; (b) write the evaluation protocol down as a script, so
"measured better" always means the same thing; (c) report an interval, never
a point. Cheap, and it is the reason four of the five experiments below could
not be settled cleanly.

**Phase 1 — DONE 2026-08-02**, and half of it turned out to be wrong.

- **Part-whole detection: REJECTED.** The "10% of `variant`" figure was an
  overestimate by ~2.5×: of 114 substring pairs, 94 differ by a single
  character and 69 of those are ALREADY inside ONE_MOVE — final-ṃ loss and
  the like, which the epenthetic indels already handle. Genuine part-whole
  is 46–59 pairs. And no detector pays for them: raw substring matching
  costs **6.0 candidates per lemma** (against the metric's 0.84) for 46
  pairs, where spending the same volume on a higher θ buys ~1,000. Sharing a
  constituent is far worse, 979 cand/lemma. The strict form ("the short one
  IS a constituent of the long one") is affordable at 1.0 cand/lemma but
  recovers only 31. Deeper reason: "is a constituent of" is not "is a
  variant of", and in a language of compounds the relation is everywhere.
- **Construction as a second criterion: ADOPTED**
  (`Lexicon.variants(constructions=...)`, `construction_key`). The cheapest
  recall in the system by an order of magnitude: **63.6% → 71.8%, +8.2
  points, for +0.082 cand/lemma**, where buying six points by raising θ to
  0.800 costs +0.28. It reaches what the metric cannot — `abhikkhaṇaṃ ~
  abhiṇhaṃ` (2.37), `agamā ~ agā` (1.63), `abbheti ~ avheti` (1.28).
  Measured only on the pairs the metric does NOT already capture, as the
  open item demanded.
- **The name was wrong.** This was filed as "compound permutation" (same
  constituents, different order). Permutation is a special case and a rare
  one; what pays is IDENTICAL construction — the same word formed the same
  way and spelled differently. Sorting the constituents covers both.
- It is a LEXICAL fact, not a phonological one, so it lives in the
  integration layer and the caller supplies the data. abugida still owns no
  lexicon.

**Phase 2 — DONE 2026-08-02. The tradition had nothing left to add to the
EMBEDDING; what it had was already implemented and simply not being used.**

The phase was framed as "which traditional distinctions are still absent from
the embedding". Measured answer: none that pay.

- **The prediction I registered first FAILED, and that is the useful part.**
  The tradition identifies the semivowels with their vowels (`y` is
  non-syllabic `i`, `v` is `u`; it is the basis of the sandhi `i` + V → `y`),
  so I predicted `y↔i` and `v↔u` would be expensive and need an axis. They
  are 0.535 and 0.608 — already BELOW ONE_MOVE, already captured through
  shared place. No change warranted.
- **Diagnosing the losses instead** (1,823 true pairs missed at ONE_MOVE)
  showed most are lost by ACCUMULATING cheap edits, not by one dear
  substitution — except one doctrinal group: **288 ṃ↔series-nasal
  substitutions** (`ṃ↔ṅ` 182, `ñ↔ṃ` 54, `m↔ṃ` 52), all at 0.740, the known
  cost of the glut reading.
- For that group the tradition had already dictated the answer and the
  project had already implemented it — `assimilate_word`, saṃ+gha → saṅgha —
  it just was not in the variant pipeline. Applying it recovers **263 pairs,
  +5.26 points, at zero volume cost**: it is a normalisation, it generates no
  candidates. (Predicted ~288, recovered 263. The prediction came first.)

Recall over the 5,002 `var_phonetic` pairs, all at ONE_MOVE:

| pipeline | recall | cand/lemma |
|---|---|---|
| metric alone | 63.6% | 0.84 |
| + `assimilate_word` | 68.8% | 0.84 |
| + `contract_word` too | 78.2% | 0.84 |
| + `constructions` (Phase 1) | **82.0%** | 0.92 |

For comparison the metric alone needs θ≈1.3 — **6.6 cand/lemma** — to reach
83.9%. The full pipeline gets within two points of that at a seventh of the
volume.

The lesson generalises past this phase: before adding anything, check what is
already built and not wired up. Two of the three components of that 82% were
implemented and documented long ago.

**Phase 3 — DONE 2026-08-02. There is ONE metric. The apparent conflict was
an artefact of the benchmark, not a property of the tasks.**

The phase existed because the dorsal bridge gained on variant recall and lost
1.9 points on scribal retrieval, which looked like two tasks wanting
different calibrations. Both halves of that turned out to be wrong.

- **The 1.9 points were half noise.** That figure came from n=80 — 1.5 cases.
  Re-run at n=1000 with the paired test the loss is 0.9 points (96.8% vs
  97.7%), significant at p=0.0039 but half the size reported.
- **And the remaining loss was the benchmark's own bias.** The corruption
  generator's `CONFUSION_PAIRS` is a THEORY of which confusions occur, and
  the metric is scored against it. It contained the tongue-TIP pairs
  (`t↔ṭ` and friends) but not the tongue-BODY pairs (`k↔c`), so synthetic
  corruptions were never dorsal and a metric modelling the dorsal bridge
  could only be penalised, never rewarded. The asymmetry has no support in
  the data: guttural~palatal is 11.4% of attested place substitutions.
- **Corrected, the trade-off stops being significant**: 97.1% vs 97.6%,
  McNemar p=0.2266. The sign is still mildly negative and might survive at a
  larger n, but nothing here justifies maintaining two calibrations.

`CONFUSION_PAIRS` now includes the body pairs, and the sample went from 80 to
400 — 80 could not resolve a difference of a point or two, which is how this
went unnoticed.

**The conclusion is stronger than "one metric is enough".** A benchmark that
enumerates the errors it will test is a hypothesis, and scoring against it
rewards agreement with the hypothesis rather than with the language. Any
future task of this shape should have its error model justified against the
corpus, exactly as the karaṇa bridges were.

Also worth keeping in proportion: this whole trade-off is ~1 point, while
Phases 1–2 moved recall 18 points. Calibration profiles were never where the
value was.

**Phase 4 — DONE 2026-08-02. All three items closed; the most interesting
result is that one of them was my own measurement error.**

- **Multi-grapheme alternations: closed, nothing to build.** They are
  expensive (`ty↔cc` 1.54, `ṭhā↔ṭhaha` 1.86) and vanishingly rare: across the
  5,002 `var_phonetic` pairs `ty↔cc` occurs ONCE, and `dy↔jj`, `ny↔ññ` and `ṇṭ↔nd`
  never. `ṃy↔ññ` (41 pairs) is already in `assimilate_word`; `e↔aya` and
  `o↔ava` in `contract_word`. Prediction registered first — that extending
  assimilation to `C+y` would pay — and it failed on the frequencies.
- **The lev=3 "below chance" deficit was an artefact of my instrument.**
  I attributed 19.9% at three edits to these alternations without checking.
  Wrong: those triples are `aya↔e` (`gaṇetvā ~ gaṇayitvā`, 1.65), and through
  the recommended pipeline the same 682 triples score **79.5%**. Overall the
  hard battery goes 50.6% → 66.7%. `hard_battery.py` now prints both columns;
  scoring the metric in isolation misdiagnosed the project's own
  recommendation as a hole in the metric.
- **`contract_word`'s spurious share: ~0.** Of 533 collapsed lemma pairs
  (the note said 527), 444 (83%) are annotated variants and the other 89 are
  plainly genuine — `abhivaṇṇayati ~ abhivaṇṇeti`, `avacarati ~ ocarati`.
  Nothing to fix.
- **README wording reconciled.** "Subsumes" and "complements" were both
  defensible and the README now says which is which: it covers every rule
  that produces lemma→lemma pairs, eight multi-grapheme rules sit beyond the
  cost's reach, and those eight barely occur.

**Phase 5 — DONE 2026-08-02. The principle exists, and it derives the LINEAR
cost — the opposite of what the phase was looking for.**

The phase was framed as "find a principle that would derive the concave
warp". The principle turned out to be the noisy-channel reading of edit
distance — cost = −log P(operation), which is why costs sum at all — and
under it the transformation is not a choice: exponential decay of
confusability gives a linear cost, power-law decay a logarithmic one.
Measured (`eval/noisy_channel.py`), the decay over the operating range is
exponential: R² 0.974 identity against 0.932 log at d ≤ 1.5, identity winning
at every cut through 2.5. Log overtakes only past d ≈ 3, where P ≈ 0.0001 and
no usable threshold reaches.

So the warp is not merely unprofitable — it is wrong for the observed decay,
and its R² advantage came from fitting a tail with no signal. The gain is
that "no warp" stops being the untouched default and becomes derived, like
ρ* and INDEL_WEIGHT. Bound on the claim: this fixes the right transformation
OF THIS GEOMETRY, not the geometry itself (§4).

## Open work

- [ ] **Mostly explained**: the discrepancy between a sweep AT the operating
      point and a θ=1.0 sweep filtered down to it. The rapidfuzz prefilter
      was the hypothesis and it is **not** the cause — pipe@50 tracks the
      metric ceiling to within 1.5 points up to θ=1.5. The likely cause is
      **rounding**: `ONE_MOVE` is 0.62707…, a large share of true pairs sit
      at exactly one epenthetic indel, and comparing against a literal
      `0.627` drops every one of them — 59.9% against the true 63.6%. Both
      `variant_curve.py` and `karana_bridges.py` now sweep the constant
      itself. Still to confirm that this accounts for the *pipeline*-column
      gap specifically, which is what the original item was about.

### Done: the triangle inequality across the geminate transitions (2026-10-13)

**CLOSED: the halves model was adopted.** Every word is segmented once into
letters and heavy units (geminates, homorganic nasal+stop clusters with ṃ),
in `_pure._segment` and C `segment_units`; the 2:1 / 1:2 / 2:2 transitions
are gone; `distance` is a metric by theorem and checked in tests (the three
token-level conditions exhaustively over 126 tokens, word triples in
`tests/c/test_edge_cases.c`). Measured with the adoption: battery 30/30,
hard battery 50.9% raw / 68.1% pipeline, Pāli doublets unchanged,
Sanskrit-to-Pāli correspondences further (Oberlies within two moves 40.0% →
31.6%, Geiger 47.8% → 35.0%, tatra~tattha 0.831 → 1.470), open vocabulary
88.0 / 92.4 / 96.2%. Re-run with DPD the same day: agreement at ONE_MOVE
63.2% → 62.6% on one build (same volume); the units worth 14.4 points by
ablation; the Geiger tadbhava ranking 32.8% → 24.5%, paired over the same
pools (by `geiger_history.py`, retired with the earlier history; the step alone [−13.0%, −4.2%], McNemar 15 vs
1, p < 0.01) — the measurable price of the
guarantee, all of it on Sanskrit→Pāli. Retrieval rows re-run on the newer
lexicon (95.2%, 87.5%, 58.3%), not attributable to the units. The record of how it was found and decided follows.

Recorded 2026-08 while testing the C core. The word-level
triangle fails across the 2:1/1:2 alignment transitions: 42 violating triples
in 10,648 over 22 words, 0 with the transitions disabled; the empty string
fails it separately. The full account is in `docs/c-core.md` and the
amendment to SPEC §14.

What is already established, so nobody re-measures it:

- **The substitution cost is a metric**, exhaustively — the failure is in the
  transitions, not the geometry.
- **It is not a C artefact.** The pure-Python reference returns the same
  numbers; `tests/test_c_parity.py` holds the two together.
- **The geminate transitions are worth +15.1 recall points**
  (`eval/ablate_geminates.py`), so removing them to restore the theorem is
  not a trade worth proposing again.
- **The BK-tree is exact anyway**, measured over 5,000+ queries including
  corpora built from the counterexample: the pruning can only drop a word the
  first comparison already placed outside the radius. Pinned by
  `tests/test_index.py`. It is exact by measurement, not by theorem, which is
  the thing to keep in mind when changing the metric.
- **Nothing published moves.** Every recall figure is a threshold sweep, and
  the relative-threshold path already refuses to index on a non-metric.

**Answered 2026-10-13 (`eval/triangle_geminates.py`, no DPD):**

- **The cause, one for all 86 violations** in 26,400 triples built from the
  grammar case files: the DP decides PER PAIR whether a geminate is one long
  consonant (2:1, 2:2) or two letters (1:1), and a unit change is cheaper
  than changing both halves (kk~gg 0.377 against k~g 0.470 each). In 81 the
  middle word's geminate is a unit in one leg and split in the other
  (makka -> magga -> saṅgha); in the other 5 the same happens to an end
  word's geminate, one of them through the missing whole-geminate deletion.
- **Raising the unit costs** to what the triangle demands is the removal of
  the transitions under another name: all 992 geminate pairs would have to
  rise, up to 2.0, the price of two separate substitutions.
- **Closing the transitions under composition** (a geminate against any two
  tokens, deletion of a whole geminate) leaves 50 of the 86: a geminate can
  be split ACROSS other material (kathita -> katta: th, a deleted i, t), and
  no transition of bounded size covers that.
- **One segmentation per word** — every geminate always one long token,
  plain edit distance, the long token's indel derived as the cheapest route
  through a single token — is a metric by the classical theorem: 0
  violations. Unchanged: the Oberlies and Geiger doublets within one move
  (56.7%, 45.8%). Lost: two battery triples, both geminate against
  nasal+stop cluster (citta ~ cinta 0.63 -> 1.47, puñña ~ puñja), 29/29 ->
  27/29; and open-vocabulary points (below). A first version of this entry
  said the open-vocabulary task was unchanged: the substitute distance had
  not reached the script (`abugida.distance` names the function, not the
  module), and a distance returning 0 scored the same 90.9%. Corrected.
- **Halves** — geminates AND homorganic nasal+stop clusters as one token
  each, a token being (first half, second half, weight), the cost the max of
  the three coordinate costs, the weight priced at the live degemination
  cost: 0 violations by theorem, the battery whole (29/29), citta ~ cinta
  kept at 0.63, a change inside a cluster at full price (nt~nd = t~d),
  Oberlies doublets within one move 56.7% -> 58.2%. A single vector per
  cluster (the sum of its segments) was tried first and cannot work: the
  nasal weight that separates tt from nt is the weight that dilutes every
  change inside the cluster (nt~nd fell to 0.06–0.20, and khandha ~
  khantha lost to khandha ~ khandhā).
- **The price of both one-segmentation systems** is a one-letter change
  that breaks a unit (a half-geminate, tṭ) — it costs a broken unit. On the
  open-vocabulary forced choice (1,500 trials per level, the script's own
  generators): live 92.7 / 98.3 / 99.8%, halves 85.8 / 91.1 / 96.3%; on the
  trials where both variants are possible Pāli, live 92.8 / 99.5 / 100%,
  halves 92.2 / 97.9 / 100% (n = 548 / 211 / 68). The loss is on strings
  Pāli does not write. Not measured: agreement with DPD and the Geiger
  tadbhava ranking (both need DPD), and the speed of a real implementation
  (C core, tables, traceback, `edit_tag`). Adopted the same day (above).

The questions this entry first asked, kept as they were:

1. **Which operation makes it fail?** (answered above) The counterexample needs a geminate on
   one side and an indel on the other. Characterising the violating triples
   (rather than counting them) would say whether a narrower repair exists —
   e.g. pricing a 2:1 transition so that it equals the best composition of
   substitutions and indels that could replace it. That is a *calibration*
   question, and the project's discipline says a calibration has to come from
   structure, not from making the test pass.
2. **Does it matter for anything measured?** The index is the only structure
   in the package that consumes the guarantee, and it is exact in practice.
   Any other consumer would have to be named before this is worth more work.
3. **Should the empty string be an error?** It is a domain question, not a
   metric one: no lexicon has one, and the reference implementation silently
   scores it as a word of zero tokens.

### Done: the kernel dispatcher (asm-plan phase 1)

Implemented 2026-08: the kernel compiles once per instruction set from one
source, a dispatcher picks by CPUID, `ABUGIDA_IMPL` forces one, and the tests
walk every variant. Measured: **they run at the same speed** (75.4 / 75.1 /
74.6 ns per pair) despite the AVX2 build being a different binary, because the
recurrence is a serial dependency chain. Phase 2 was going to be justified by
"assembly can beat the compiler"; these numbers say the compiler is already at
the latency floor, so Phase 2 needs a measurement of its own before it is
worth starting.

### Done: the bit-parallel Levenshtein kernel (asm-plan phase 0)

Implemented 2026-08 in `csrc/abugida_myers.c`, verified, and 4.9× on a
500-word lexicon sweep. `docs/asm-plan.md` has the numbers and the two things
the implementation corrected in the plan. The DP remains as the fallback for
words longer than 64 tokens, and both kernels are checked against each other
by `tests/c/test_myers.c`. Phases 1 to 5 of the plan are still open.

### NEXT: the redesigned plan (docs/asm-plan.md)

The plan was redesigned after the kernel measurements took away its premises.
What is left, in order, each with a bar it must clear before it starts:

1. ~~**The Lexicon stops re-tokenising itself.**~~ **DONE 2026-08.** The
   scoring loop is 2.1× faster and `Lexicon.search` is **1.35×** faster
   (0.849 → 0.626 ms per query); `python tools/benchmark_lexicon.py`. The
   plan first claimed 2.97× because it measured the loop rather than the call.
   The first implementation also had a variable-shadowing bug that made every
   lookup answer with the last word's tokens — pinned by
   `tests/test_lexicon_tokens.py`.
2. ~~**A threshold that prunes the DP.**~~ **MEASURED AND NOT INTEGRATED
   2026-08.** The gate cleared — 94–99.6% of a real pool's candidates are
   above θ — and the bounded DP is exact and 1.3–1.6× cheaper in C. At the
   Python API it is **0.92–1.03×**, i.e. nothing, because the per-candidate
   cost of asking eats the saving. Python integration reverted; the C function
   stays with `tests/c/test_bounded.c`. Do not re-propose it for
   `Lexicon.search` without measuring the entry point, not the kernel.
All three items are closed. The two that shipped are above; the third —
beating the DP by hand — is below with the reason it is not worth starting,
and the same entry covers the two versions of the idea that were built and
measured first.

### The DP restructuring is NOT worth it (measured, twice)

Two versions of this idea have been measured and both are closed:

1. **Removing the function pointers `run_dp` takes.** A first prototype
   reported 4.5–5.6×, and that number was wrong: it compared against a
   HAND-WRITTEN pointer version, which is not what the compiler produces.
   `gcc -O2` specialises `run_dp` through `constprop`, inlines both cost
   functions and reads the cost table directly — ZERO calls to the cost
   function in the hot path. Against the shipped function the same
   restructuring is **1.31× on an 11-token pair, 1.41× on a 35-token one, and
   0.78× — slower — on a 5-token one**.
2. **A bounded DP that stops once a cell passes a threshold.** Exact, and
   1.30–1.64× cheaper in C on real pairs, and its gate cleared: 94–99.6% of a
   real search pool sits above the threshold. At the Python API it measures
   **0.92–1.03×**, i.e. nothing, because the per-candidate cost of asking
   eats the saving. The C function stays (`abugida_word_distance_bounded`,
   with `tests/c/test_bounded.c`); the Python integration is reverted.

**Do not re-propose either** without measuring against
`abugida_word_distance` AS COMPILED and at the Python entry point rather than
at the kernel. Both mistakes were the same mistake: a gate or a baseline that
measured the mechanism instead of the call.

## Measured and closed — do not redo

- **The residual weights of dims 8–11 are fine at 1.0: measured, nothing to
  win** (2026-08-02). The prompt was a real observation: phoneme norm and
  mean cost against the inventory correlate at **r = −0.667** (`o` and `e`,
  norm 2.24/2.12, average 0.708/0.713; `kh`/`ch`, norm 1.10, average 0.853).
  So segments with more active dimensions sit closer to everything, and
  nobody chose that — `SYLLABIC`, `LENGTH`, `CONTINUANT`, `LATERAL` are all
  at 1.0 by default, the last implicit constants in the system. Two repairs
  were tried and both fail:

  - **Normalising every phoneme to unit norm: vacuous.** The cosine is
    already scale-invariant, `cos(u,v) = cos(αu,βv)`. The correlation is not
    the norm dividing; it is that more active dimensions means more overlap
    with more things. The norm is the symptom, not the mechanism.
  - **Deriving `LENGTH` by the balance principle** (make `a↔ā` cost what
    `k↔kh` costs) gives w = 1.5747 and is clearly worse: battery 29/29 →
    **25/29**, AUC down, and it breaks "degemination = one move" (`tt↔t`
    0.470 → 0.612). Vowel length being CHEAPER than an algebra move is not
    an oversight — it is the commonest transmission variant and the data
    wants it cheap.

  Sweeping w_LENGTH the other way: below 0.6 the lexicon collapses (41
  spurious near-identical pairs per 700 lemmas at 0.4, 67 at 0.2 — distinct
  lemmas made indistinguishable). Between 0.6 and 1.0 collapses are flat at
  3 and the gain is AUC 0.9037 → 0.9074, top-1 69.0% → 70.8% — inside one
  standard error (±2.1 points on 480 queries). The default is justified
  a posteriori.

  Note the battery cannot referee this: it stays at 29/29 across the whole
  range, even at w = 0.2 where `a↔ā` is 0.073. It is saturated at its
  ceiling and can only detect regressions, not improvements.

- **A concave re-warp of `cost`: implemented, measured, REVERTED**
  (2026-08-02). `log(1+x)/log 2` applied to the angular cost. Admissible —
  any increasing concave f with f(0)=0 is subadditive, which is what carries
  the triangle inequality through; a convex one (x²) is not, and measurably
  breaks it. It was reverted because at EQUAL CANDIDATE VOLUME it buys
  nothing:

  | cand/lemma | recall unwarped | recall warped |
  |---|---|---|
  | 0.38 | **52.3%** | ~47.1% |
  | 0.65 | 59.2% | ~58.3% |
  | 1.10 | 65.5% | **~69.3%** |
  | 2.03 | 75.4% | ~76.7% |
  | 8.45 | ~84.5% | 84.7% |

  Mixed, and inside the noise. Against it: the scale shifts 4.3% towards
  Levenshtein (mean d/lev 0.5953 → 0.6386 over 4,000 random DPD pairs,
  though resolution holds at ~3,980 distinct values against Levenshtein's
  20), and it would be the only part of the cost not derived from a
  structure. In its favour, and unresolved: AUC over hard negatives does
  improve, 0.9041 → 0.9144 with top-1 unchanged. Re-measured paired
  (2026-08-02): that AUC gain is DECISIVE, 95% CI [+0.0074, +0.0156] — not
  noise, as first recorded. It does not overturn the reversal, which rested
  on the iso-volume recall curve, but the two measures genuinely disagree
  and that disagreement is unresolved: AUC scores ordering WITHIN an
  already-retrieved pool, iso-volume scores the system.

  Traps for anyone re-running this. Comparing at "equivalent thresholds"
  f(θ) is WRONG — f(0.470)=0.556 costs 0.51 cand/lemma against 0.38, and
  that mistake makes the warp look like +3.7 points. Comparing against
  RANDOM negatives is also useless: every warp scores ≥0.99. One-edit tasks
  cannot move at all under a monotone warp (battery 29/30 and every
  retrieval top-1 were identical), so they cannot decide it either.
- **`ONE_MOVE` is a maximum, not an alias** (2026-08-02). It was
  `INDEL_WEIGHT`, which happened to be the dearest elementary move. The
  concave warp expands the near field and compresses the far one, so the
  epenthetic indel (0.543) fell BELOW one algebra move (0.556) and the alias
  silently stopped covering k↔kh — `Lexicon.variants` returned nothing for
  kamma, which is how it surfaced. It is now `max(INDEL_WEIGHT, k↔kh, tt↔t,
  a↔ā)`, so "every cheaper move falls under theta" holds by construction
  rather than by coincidence. Do not collapse it back to an alias.

- **The dorsal karaṇa bridge: adopted** (2026-08-02, `eval/karana_bridges.py`).
  SPEC §14 used to claim the tongue tip was the only place confusion
  transmission attests; it is not. Guttural~palatal occurs 95 times (11.4%)
  in `var_phonetic`, second after cerebral~dental's 72.7%, and the tradition
  already supplies the principle — guttural is jivhāmūla and palatal
  jivhāmajjha, both the tongue body, exactly as cerebral and dental are both
  the tip. Same √½/√½ split, no new parameter, ρ* unchanged at 0.4580,
  within-series costs untouched, triangle inequality re-verified. k↔c and
  ṅ↔ñ join t↔ṭ and n↔ṇ at 0.601/0.437. Side effect: the derived
  `INDEL_WEIGHT` rises 0.6082 → 0.6271 (`y` gains dorsal mass and tightens
  the Lipschitz bound) — re-derived, not retuned. Worth +1.46 recall points
  with each layout at its own ONE_MOVE, and +2.8 to +3.9 at strict θ.
  The metric-independent positional count puts 90.1% of place confusions on
  the two bridges. **The trade is real and was accepted with both sides
  measured** — but the retrieval side was later shown to be mostly an
  artefact (Phase 3, 2026-08-02). It read as −1.9 points on n=80; at n=1000
  with the paired test it is −0.9 (p=0.0039), and once the benchmark's
  `CONFUSION_PAIRS` is corrected to include the tongue-body pairs it models
  — they were missing while the tongue-tip ones were present — it is −0.5
  and NOT significant (p=0.2266). Against +2.8 to +3.9 of variant recall at
  strict θ, plus a false claim removed from SPEC §14. Do not re-measure;
  do not quote the −1.9.
- **Removing the geminate transitions: rejected** (`eval/ablate_geminates.py`).
  They are the only special case stitched into the DP and so the standing
  candidate for simplification; ablating them costs **15.1 recall points**
  at the operating point and moves 20.5% of true pairs, always for the
  worse. What they lose is a whole phonological class — the geminate/simple
  alternation (`apaṇṇattika ~ appaññattika` 0.986 → 2.262). The Δ shrinks
  above θ=1.0 only because a loose threshold recovers those pairs the
  expensive way: the transitions do not add recall, they make it affordable,
  at 2–5× less volume. Do not remove them.
- **Repo hygiene: done** (2026-08-01, in the earlier history).
  `.gitignore` added, and the 69 tracked `.pyc` files untracked along with
  `build/` and `abugida.egg-info/`. The stale `build/lib/` copy is worth
  knowing about: it still held `aksara.py` and `alfabeto.py`, modules no
  longer in the package — do not read it as source.
- **`root_key` / `family_root` as a filter: rejected.** 41.2% lexicon
  coverage (94–98% on verbal classes, 23–29% on the nominal two thirds that
  hold the orthographic variation, 0% on sandhi/idiom). Decidable on only
  43% of true variant pairs. Would kill 15.6% of real variants —
  `bandhita ~ bādhita`, `carituṃ ~ gantuṃ` — precisely the scribal
  confusions the task is about. At equal volume it beats simply lowering θ
  by 0.7–4.1 points: real but marginal, because the signal is correlated
  with the distance rather than orthogonal to it.
- **Contraction as a 3:1 alignment transition inside `distance`: rejected.**
  Breaks the triangle inequality; counterexample and reasoning in SPEC
  §9.1. It lives in `sandhi.contract_word` as a normalisation instead.
- **The four contraction rules that do not pay for themselves**: `āya→e`
  and `āva→o` earn nothing alone; `iya→e` and `īya→e` lose recall
  (−2.80, −2.44 points). Per-rule table in SPEC §9.1.
- **Morphological formability as a candidate filter: rejected.** 43 roots
  span 3,920 forms covering 0.13% of the lexicon — three orders of
  magnitude short. It remains useful as an evaluation control
  (`eval/open_vocabulary.py --morphological`), not as a filter.

## Operating points (θ, against `var_phonetic`)

Re-measured on the 14-dim layout (the dorsal bridge, 2026-08-02).

| θ | recall | pipe@200 | + `contract_word` | cand/lemma |
|---|---|---|---|---|
| 0.470 | 52.3% | 52.1% | 61.0% | 0.38 |
| 0.6271 (`ONE_MOVE`) | 63.6% | 63.3% | 72.0% | 0.84 |
| 0.800 | 72.4% | 72.0% | 80.6% | 1.55 |
| 1.000 | 80.0% | 79.5% | 88.2% | 3.23 |
| 1.500 | 85.2% | 84.5% | 93.7% | 10.63 |

The economic knee is θ≈0.8, not 1.0. Above θ=1.15 the marginal cost runs
569–2,424 candidates per additional true pair.

The prefilter costs 0.3–0.7 points across the whole range (pipe@200 against
the metric ceiling), so it remains too small to be the "unexplained
discrepancy" above — consistent with the rounding hypothesis, though not a
direct replication of the two-sweep experiment that raised it.

**Sweep the constant, not its label.** `ONE_MOVE` is 0.62707…, and a large
share of true pairs sit at *exactly* one epenthetic indel. Sweeping a θ
written as 0.627 therefore drops all of them and reports 59.9% where the
operating point really yields 63.6% — a 3.7-point artefact of rounding.
This is also the leading suspect for the "unexplained discrepancy" open
item above, which compared a θ=0.608 sweep against a θ=1.0 sweep filtered
down to 0.608; not yet confirmed, since that item was about the pipeline
column rather than the metric one.
