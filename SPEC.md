# abugida — specification

> **Scope note (2026-08-01).** The project has been refocused: abugida IS the
> phonological comparator (§14) and its supporting layers. Sections with live
> code: §1–§5 (algebra and embedding), §7 (IAST), §9 (sandhi), §11 (alphabet),
> §13 (phonotactics), §14 (distance). Sections §6 (information order), §8 (LP
> table), §10 (akṣara symbol) and §12 (the language L) document theory whose
> code was retired in the refocus — it was in the repository's earlier
> history (the commit "Full state before refocus"), which is not part of the
> history restarted on 2026-10-13. Their ideas survive inside the live code:
> the lattice meet and join operate in `assimilate`, `sandhi_join` and
> `phonotactics`; the glut reading of ṃ lives in the inventory.

An algebraic representation of Pāli phonology. Every phoneme is described by
a **place of articulation** (the traditional *ṭhāna* classification) and a
value of the algebra `A`, which encodes voicing, aspiration and nasality.

## 1. The algebra A

A carrier set of six elements, the product of two axes:

```
A  =  {0, 1}  ×  {ε, +, −}
       base       modifier
```

Notation: `0`, `0+`, `0−`, `1`, `1+`, `1−` (where `0` abbreviates `0ε`).

### Semantics

| | reading | realisation |
|---|---|---|
| `0`  | voiceless          | k c ṭ t p |
| `0+` | voiceless aspirate | kh ch ṭh th ph |
| `0−` | **niggahīta**      | ṃ |
| `1`  | voiced             | g j ḍ d b |
| `1+` | voiced aspirate    | gh jh ḍh dh bh |
| `1−` | nasal              | ṅ ñ ṇ n m |

Base axis = voicing. Modifier axis: `+` aspiration, `−` nasality, `ε` unmarked.

### The operation ⊗

The given axioms:

```
0+ ⊗ 0− = 0
1+ ⊗ 1− = 1
```

These two, plus associativity, determine the entire structure:

- **The modifier is Z₃.** `+ ⊗ − = ε` makes `+` and `−` mutual inverses; the
  submonoid they generate is a group, and a group of order 3 can only be Z₃.
  Therefore **`+ ⊗ + = −`**. The idempotent alternative (`+ ⊗ + = +`) is not
  associative: `(+⊗+)⊗− = ε` but `+⊗(+⊗−) = +`.
- **The base is NOT Z₂.** If it were, `1+ ⊗ 1− = (1+1, ε) = 0`, against the
  second axiom. Hence `1 ⊗ 1 = 1`: the base is idempotent, the OR
  semilattice, and `1` **absorbs**. Voicing, once present, cannot be undone;
  aspiration and nasality do cancel.

### Resulting structure

`(A, ⊗)` is a **commutative monoid**, not a group — specifically a Clifford
semigroup: the semilattice `{0 < 1}` of two copies of Z₃.

- Units (invertible elements) = the **voiceless** values `{0, 0+, 0−}` ≅ Z₃.
- The **voiced** values `{1, 1+, 1−}` form an absorbing ideal that is itself
  a Z₃, with its own identity `1`.

| ⊗ | 0 | 0+ | 0− | 1 | 1+ | 1− |
|---|---|---|---|---|---|---|
| **0**  | 0  | 0+ | 0− | 1  | 1+ | 1− |
| **0+** | 0+ | 0− | 0  | 1+ | 1− | 1  |
| **0−** | 0− | 0  | 0+ | 1− | 1  | 1+ |
| **1**  | 1  | 1+ | 1− | 1  | 1+ | 1− |
| **1+** | 1+ | 1− | 1  | 1+ | 1− | 1  |
| **1−** | 1− | 1  | 1+ | 1− | 1  | 1+ |

## 1.5 The second operation: A is a semiring

### Theorem: a ring with ⊗ is impossible

A ring requires one operation to be an abelian group and the other to be a
monoid with an absorbing zero. `⊗` serves neither role:

- **Not a group**: `1` has no inverse — `1 ⊗ x` always has base 1, by the
  axiom `1+ ⊗ 1− = 1`. Forcing the base to Z₂ would supply the inverse and
  break that axiom.
- **No absorbing element**: no `z` satisfies `z ⊗ x = z` for every `x`,
  because the modifier always turns. Every ring product requires `0 · x = 0`.

Verified in `test_algebra.py::TestNoRing`. What does exist is the next
structure down — and it fits the theory better:

> **The counterfactual, priced** (`algebra.compose_xor`, EXPERIMENTAL). The
> first bullet says forcing the base to Z₂ would break the axiom. It is worth
> following that through, because the result is sharper than "no ring": with
> XOR on the base, `⊙` still distributes, `0` still absorbs, `1+` is still
> neutral — so it IS a commutative ring, and by CRT F₂ × F₃ ≅ **Z/6Z**
> exactly, with `1+ ↦ 1` carrying both operations (0↦0, 1+↦1, 0−↦2, 1↦3,
> 0+↦4, 1−↦5). The ring is not unreachable; it costs one datum. And what it
> buys with that datum is subtraction — voicing becomes reversible,
> `1 ⊗ 1 = 0`, devoicing by composition — which is precisely the thing Pāli
> does not do, and precisely what §1.5 below means by "a semiring is a ring
> without subtraction". The paraconsistent reading of §2 goes with it: in
> Z/6Z nothing absorbs, so "the explosive element is voicing" has no content.
> Runnable and pinned in `test_algebra.py::TestXorVariant`; nothing above
> `algebra` imports it.
>
> **And the boolean reading, which fails differently** (`or_`, `and_`,
> `not_`, `sum_`, also EXPERIMENTAL). Read the base as {0 < 1} and the
> modifier as the chain ε < + < −; take join, meet, and the order-reversing
> complement. That much works: it is a **distributive De Morgan algebra**,
> involutive, both De Morgan laws over all pairs. But it is **not boolean** —
> exactly the aspirates `0+` and `1+` have no complement, because the
> modifier `+` is fixed by 2−m and so the modifier of `x ∧ ¬x` never falls to
> ε. A three-value chain with an order-reversing involution is Kleene's
> algebra, which is the shape §2 has in mind when it says a paraconsistent
> *consequence* would need an information order distinct from ⊗.
>
> The consequence is the interesting part. In a boolean algebra the symmetric
> difference `(a∧¬b) ∨ (¬a∧b)` IS xor, so `sum_` would recover Z/6Z. It does
> not: it agrees with `compose_xor` on exactly 20 of 36 pairs, and the rule
> is sharp — **iff at least one operand is unmarked**. With both marked the
> lattice cannot cancel: `sum_(0+, 0+) = 0+` where both ⊗ and xor give `0−`.
> `sum_` is a commutative monoid, not a group. And the failure is not an
> artefact of the chosen order — it holds under all twelve product orderings
> of the six elements, checked exhaustively.
>
> So: **a lattice cannot express cyclicity.** `+ ⊗ + = −` is arithmetic in
> Z₃, and no amount of join/meet/complement reconstructs it. That the
> modifier is a FIELD and not a boolean algebra is load-bearing, and this is
> the demonstration. Pinned in `test_algebra.py::TestLatticeOps`.

### A ≅ B × F₃, a commutative semiring

```
A  ≅  B × F₃
      │    └─ modifier: Z₃ not merely as a group — as the FIELD of 3 elements
      └────── base: the boolean semiring ({0,1}, OR, AND)
```

`⊗` **is the sum** of this semiring (OR on the base, + in F₃): both starting
axioms fall out on their own. And the componentwise product supplies the
missing multiplication:

```
x ⊙ y  =  (base: AND — voiced only if both are,
           modifier: product in F₃ — ε erases the mark)
```

| ⊙ | 0 | 0+ | 0− | 1 | 1+ | 1− |
|---|---|---|---|---|---|---|
| **0**  | 0 | 0  | 0  | 0 | 0  | 0  |
| **0+** | 0 | 0+ | 0− | 0 | 0+ | 0− |
| **0−** | 0 | 0− | 0+ | 0 | 0− | 0+ |
| **1**  | 0 | 0  | 0  | 1 | 1  | 1  |
| **1+** | 0 | 0+ | 0− | 1 | 1+ | 1− |
| **1−** | 0 | 0− | 0+ | 1 | 1− | 1+ |

Consequences:

- **Zero** = `0` (the plain voiceless stop): neutral for ⊗, absorbing for ⊙.
  The absorbing element ⊗ lacked does exist — in the right operation.
- **One** = `1+` (the voiced aspirate): gh, jh, ḍh, dh, bh are the
  multiplicative unit.
- **`1−` is an involution**: `1− ⊙ 1− = 1+` (2·2 ≡ 1 in F₃). Nasal times
  nasal gives aspirate.
- Units of ⊙ = `{1+, 1−}` ≅ Z₂ — the mirror image of ⊗'s units (the
  voiceless ones, ≅ Z₃).
- Distributivity: `x ⊙ (y ⊗ z) = (x ⊙ y) ⊗ (x ⊙ z)`, because AND distributes
  over OR and F₃ is a field. Verified over all 216 triples.

Phonological reading: **⊗ accumulates** features (the union of what is
present), **⊙ takes the coincidence** (what is shared; the unmarked value
absorbs the mark).

That it is a semiring and not a ring is no defect: a semiring is a ring
**without subtraction**, and being unable to subtract is the algebraic form
of "voicing cannot be undone" — the same non-explosiveness of §2, seen from
the other side. Logics without explosion live naturally in semirings; rings,
with their total subtraction, are the habitat of classical logic.

Over the embedding, ⊙ descends too (`mult_vec`), but not bilinearly: the
circular representation is that of F₃'s *additive* group, and the field's
product acts on it by Galois automorphisms — `·1` identity, `·2` **complex
conjugation** (negating the angle), `·0` collapse to the neutral point.
Homomorphism verified in `test_embed.py::test_mult_homomorphism`.

## 2. Paraconsistent reading

In classical features, `0−` is a contradiction: *voiceless nasal* =
`voiced ∧ ¬voiced`. Classically this triggers *ex falso quodlibet* and
trivialises the system.

That does not happen here, and the reason is structural: `0−` is a **unit** —
invertible, `0− ⊗ 0+ = 0` — so the contradiction is reversible and local. The
element that absorbs is `1`, voicing. **In this algebra the explosive element
is voicing, not the contradiction**: the signature of a paraconsistent system.

Scope caveat: `⊗` is feature composition, **not** a logical conjunction. The
connectives of LP/Belnap/da Costa are lattice-based and idempotent; the
modifier axis is cyclic (`+⊗+ = −`) and therefore cannot be. Speaking of
paraconsistent *consequence* would require a second order over `A` (an
information order, bilattice-style), distinct from `⊗`.

### SETTLED DECISION — glut (confirmed)

The niggahīta admitted two readings that predict the same Pāli data:

- **glut** (ADOPTED AND CONFIRMED): ṃ has *all* places at once; the context
  selects one. `saṃ+gha → saṅgha`, `saṃ+jāta → sañjāta` is the *resolution*
  of an overdetermination. It makes `0−` a designated value — which is what
  justifies calling the system paraconsistent.
- **gap** (discarded): ṃ with no place at all; it would give a paracomplete
  rather than paraconsistent logic, and force a default rule.

They diverge only word-finally or before a vowel: under *glut* residual
nasalisation remains (an unresolved overdetermination); under *gap* nothing
would.

Materialised directly in `NIGGAHITA_PHONEME` (`abugida/phonology.py`); the
intermediate flag was removed when the decision was settled (§5.7).

## 3. Places (ṭhāna)

The five traditional places, ordered back to front — which is also the
canonical order of the alphabet:

`kaṇṭhaja` (guttural) · `tāluja` (palatal) · `muddhaja` (cerebral) ·
`dantaja` (dental) · `oṭṭhaja` (labial)

Traditional grammar assigns a place to vowels and semivowels too, and admits
**compound** places — `e` is *kaṇṭhatāluja*, `o` is *kaṇṭhoṭṭhaja*, `v` is
*dantoṭṭhaja*. That is: the traditional system already contemplates segments
with two simultaneous places. The niggahīta under the *glut* reading is the
limiting case of that same phenomenon, with all five.

This is why place is represented as a **set** (multi-hot), not as a scalar.

## 4. The embedding

14 dimensions per phoneme:

| dim | feature | values |
|---|---|---|
| 0–4  | place (gut, pal, cer, dent, lab) | multi-hot; coronal places carry √½ |
| 5    | voicing (base of A)              | 0 / 1 |
| 6–7  | modifier of A                    | (cos θ, sin θ), θ = 2πk/3 |
| 8    | syllabic                         | 0 / 1 |
| 9    | length                           | 0 short / 1 long |
| 10   | continuant                       | 0 / 1 |
| 11   | lateral                          | 0 / 1 |
| 12   | coronal (karaṇa: the tongue tip)  | √½ for cerebral/dental, else 0 |
| 13   | dorsal (karaṇa: the tongue body)  | √½ for guttural/palatal, else 0 |

Dims 12–13 are the **karaṇa bridges**: the tradition splits articulation
into ṭhāna (passive place) and karaṇa (active organ), and four of the five
ṭhāna pair up under an organ. Cerebral (jivhopagga, the underside of the
tip) and dental (jivhagga, the tip) share the tongue **tip**; guttural
(jivhāmūla, the root of the tongue) and palatal (jivhāmajjha, its middle)
share the tongue **body**. Labial is oṭṭhaja — the lower lip, no tongue at
all — so it bridges to nothing.

Each bridged place puts √½ of its identity in its own column and √½ in its
shared karaṇa column — an equal ṭhāna/karaṇa split, so every place keeps
unit norm and within-series costs are exactly unchanged (the balance
principle holds in every series, verified; ρ* re-derives to the same 0.4580
on the 14-dim layout as on the 12-dim one). What changes is only the
bridges: t↔ṭ drops from 0.889 to 0.601, n↔ṇ to 0.437, l↔ḷ to 0.322, and
symmetrically k↔c to 0.601, ṅ↔ñ and g↔j to 0.437 — while k↔p, t↔p, c↔ṭ,
k↔t and c↔t stay at full place-change cost. No general adjacency in the
tract is invented: guttural is exactly as far from dental as it is from
labial. The glut improves slightly as a side effect (ṅ↔ṃ 0.768 → 0.755 →
0.740: each organ counted once shrinks ṃ's norm).

The two bridges are **one principle, not two free parameters**: the same
√½/√½ split, applied wherever the tradition assigns a shared organ. They
are also the two confusions transmission actually attests. In DPD's
`var_phonetic`, of the 836 place substitutions between simple consonants,
cerebral~dental is 72.7% and guttural~palatal 11.4% — 84.1% between them,
against 15.9% spread over the eight non-bridging pairs.

That count is harvested from optimal alignments, which the bridges
themselves influence, so it cannot on its own justify them.
`eval/karana_bridges.py` breaks the circle by re-counting positionally over
the 3,006 equal-length pairs, where the alignment is forced by length
and no cost is consulted at all: **90.1%** share an organ (80.3% tip, 9.9%
body), same ranking. That breaks the circle with the metric, not with DPD:
the pairs are still `var_phonetic`, which DPD's own rules generate (TODO.md,
2026-10-13), so if those rules favour tip and body confusions the count
inherits it. Oberlies documents t~ṭ (§14.5) and kh~ch (§18.2) independently.
Ablating both bridges costs 8.5 points of agreement with DPD at
θ=0.470; ablating the dorsal one alone costs 1.46 points with each layout
measured at its own ONE_MOVE — small, and its real value is at strict θ,
where it is worth 2.8–3.9 points.

Downstream, the dorsal bridge also raises the derived `INDEL_WEIGHT` from
0.6082 to 0.6271: `y` (tāluja) gains dorsal mass, moving nearer the guttural
and palatal stops, and that tightens the Lipschitz bound the weight is the
extremal solution of (§14). The constant is not retuned — the same
derivation simply returns a different number on the new layout.

Dims 0–7 are the algebra; 8–11 cover what `A` does not reach (vowels,
semivowels, sibilant, aspirate).

For segments with no value in A, dims 6–7 carry **⊥ = (0, 0)** — zero norm,
distinct from ε = (1, 0). Voicing (dim 5) comes from the inventory
(`is_voiced`). In `compose_vec`, ⊥ is neutral; in `mult_vec`, absorbing.

### Why Z₃ takes two dimensions

A cyclic group of order 3 is faithfully represented as a 120° rotation in the
plane. With that choice, `⊗` **is not a table**: it is arithmetic on vectors.

```
compose(u, v):
    place     →  union            (componentwise max)
    voicing   →  maximum          (the OR semilattice)
    modifier  →  sum of angles    (complex multiplication)
```

The diagram commutes: composing two phonemes then embedding gives the same
vector as embedding then composing. `test_embed.py::test_homomorphism`
verifies it over all 36 pairs of `A`.

### The price: faithfulness versus similarity

The 120° rotation is what makes `⊗` exact, but it carries a cost worth
keeping in view. It places `ε`, `+` and `−` at cosine **−0.5** from each
other — mutually anti-correlated — whereas two distinct places are merely
**orthogonal** (cosine 0). The upshot on the raw vector: differing in
modifier is penalised more than differing in place, and `k` comes out closer
to `p` (0.5) than to `kh` (0.25).

This is not a flaw in the embedding: it is what representing Z₃ faithfully
means. But it implies the raw vector **is not directly an articulatory
metric**.

`cosine(u, w, modifier_weight=ρ)` scales dims 6–7 for measurement only:

```
cosine(k, kh)  =  (1 − ρ²/2) / (1 + ρ²)
cosine(k, p)   =       ρ²    / (1 + ρ²)
```

They cross at **ρ = √(2/3) ≈ 0.816**: below it, the series groups. The
default is `ρ = 1.0` (the untouched embedding);
`NEUTRAL_MODIFIER_WEIGHT ≈ 0.458` is derived from the balance principle (see
§5.8). `compose_vec` always requires the unweighted vector — the weight is
for measuring, not for composing.

> **Why an angle and not a weighted sum of components?**
> (`distance.weighted_cost`, EXPERIMENTAL.) The obvious alternative to the
> angular distance is Σᵢ wᵢ·|xᵢ − yᵢ| over the embedding. It is admissible: a
> weighted L1 with non-negative weights is a metric, and it takes the SAME
> calibration — its modifier weight, 0.4226, is derived by the identical
> balance principle that gives ρ* = 0.4580, by bisection. (The fully general
> Σᵢ |xᵢcᵢ − yᵢdᵢ| with cᵢ ≠ dᵢ is not a candidate at all: it is asymmetric
> and loses identity, d(g,g) ≠ 0. Only c = d survives.)
>
> Uncalibrated it breaks both structural properties — aspiration costs 2.4×
> voicing, and k↔gh (two algebra moves) overtakes k↔p (a whole change of
> place). Deriving the weight repairs both, so calibration is not the
> objection. Calibrated, it still scores **24–25 of 29** on the
> discrimination battery against the angular cost's **29**, with **4 ties**
> where the angular has none.
>
> The ties diagnose it: the L1 prices `a↔ā`, `k↔kh` and `k↔g` identically at
> 0.128, where the angle separates them (0.333, 0.470). An angle divides by
> the vectors' norms, so the same absolute displacement counts for more on a
> lightly specified segment than on a heavily specified one — and that is
> phonological content, not normalisation hygiene. The L1 sum cannot see it.
> Its scale also sits far lower against the indels: 0.4% of letter pairs
> reach the 1.0 cap against the angular's 22.8%, so delete+insert is almost
> never competitive. Pinned in `test_distance.py::TestWeightedCost`.

What is gained over encoding the modifier as a scalar (−1, 0, +1): with a
scalar, aspirate and nasal would be collinear with the unmarked value and
maximally distant from each other. Here they are equidistant from `ε` and
from each other, which is right — none of the three marks lies "between" the
other two.

## 5. Known design issues

Recorded honestly, by severity; those marked ✦ are resolved or mitigated.

1. ✦ **The algebra did not touch the implemented phonology.** `assimilate`
   was computed by set intersection, using neither ⊗ nor ⊙. Resolved by §6:
   assimilation is the meet of the place lattice.
2. **Totality generates equations with no phonological content.** `+⊗+ = −`
   and `1−⊙1− = 1+` are forced by totality plus associativity, not by Pāli.
   An accepted cost of totalising; the faithful alternative would be a
   partial operation with far less structure.
3. **⊙ lacks independent phonological motivation.** "Coincidence" is a
   post-hoc reading; no Pāli process instantiates it. Mathematically ⊙ is
   canonical (the only componentwise multiplication); phonologically it is
   half-justified.
4. ✦ **Incoherent treatment of undefinedness.** RESOLVED: ⊥ (no value in A)
   is encoded with zero norm in dims 6–7, distinct from ε (norm 1, angle 0).
   In the vector operations, ⊥ is neutral for ⊗ (no information + information
   = information) and absorbing for ⊙ (coincidence with the unknown is
   unknown).
5. ✦ **Phonological decisions hidden in the embedding.** RESOLVED: voicing
   for segments outside A is now inventory data (the `voiced` field of
   `Phoneme`; `is_voiced` unifies it with A's base). Still unexpressed: the
   relation between `h` (a phoneme) and `+` (a modifier).
6. **`0−` is overloaded**: both a column of the product Place × A and a
   single phoneme. Multi-hot patches it; the asymmetry is constitutive.
7. ✦ **A dead flag** (`NIGGAHITA_GLUT`): RESOLVED — removed; the glut reading
   is fixed directly in `NIGGAHITA_PHONEME` with a comment.
8. ✦ **Thin empirical coverage.** RESOLVED in all three parts: ṃ+y → ññ (§9);
   executable vowel sandhi (`sandhi_join`, §9 — the lattice join); and ρ is
   no longer magic: `NEUTRAL_MODIFIER_WEIGHT` is derived from the balance
   principle — aspirating (k→kh) must cost as much as voicing (k→g) — by
   bisection over the actual vectors (ρ* ≈ 0.458 < √(2/3), so the series
   groups; if the embedding layout changes, ρ* recomputes itself).

What remains are theoretical decisions rather than actionable debt: №2
(contentless equations, an accepted cost of totalising), №3 (⊙ half-motivated)
and №6 (the overloading of `0−`, constitutive).

## 6. The information order *(retired code; ideas live on)*

### Negative theorem: the order cannot live in A

The modifier axis admits no non-trivial partial order compatible with ⊗: the
voiceless values are units, monotonicity of ⊗ forces the order to be
translation-invariant in Z₃, and a translation-invariant order on a finite
group generates a strictly increasing chain that returns to its origin. It
is the dichotomy of §2 again: the modifier axis is algebraic; the
lattice-like part is elsewhere.

### Where it lives: the lattice of places (2^PLACES, ⊆)

Tradition had already populated it:

```
                {G,P,C,D,L}  =  ṃ                ⊤  (the glut)
               /     |      \
     {G,P} = e    {G,L} = o    {D,L} = v          traditional compounds
        |        /    |    \       |
       {G}    {P}   {C}   {D}    {L}              simple consonants (atoms)
                                                  (∅ = gap: discarded in §2)
```

It buys three things:

1. **Assimilation = the meet.** Resolving ṃ's glut before a consonant is
   descending to ∧. The lattice supplies the *mechanism*; the trigger (only
   before a stop) remains phonological — the bare meet would also resolve
   before a vowel, which would be an empirical error. Live in `assimilate`.
2. **⊗ over places = the join.** And `places(a) ∨ places(i) = {G,P} = e`:
   the vowel sandhi a+i → e (and a+u → o) is literally the join. It was not
   designed in; it was there. Live in `sandhi_join`.
3. **A genuine paraconsistent consequence relation**: Γ ⊨ φ iff every
   phoneme of the inventory satisfying Γ satisfies φ. Non-explosion becomes a
   theorem rather than an analogy: `{guttural, palatal}` has witnesses (e, ṃ),
   so it does not entail everything; restricted to the stops (single place),
   every pair explodes — classical vacuity. **Paraconsistency lives in the
   inventory, not in the definition of ⊨**: it is the gluts that block *ex
   falso quodlibet*.

## 7. Representation: IAST as the canonical form

The native scripts of Pāli (Devanāgarī, Sinhala, Burmese, Thai, Khmer…) are
**abugidas**: their unit is the akṣara — a consonant with an inherent `a`,
vowels as diacritics, virāma to suppress the vowel. IAST is the pivot that
dissolves that complication: a flat phonemic representation, one grapheme to
one phoneme, with no inherent vowel. The whole system (inventory, algebra,
embedding) works over IAST.

Terminological precision: IAST for Pāli is *phonemic* rather than "100%
phonetic", with two caveats that `iast.py` absorbs:

- **Aspirated digraphs** (kh gh ch jh ṭh ḍh th dh ph bh): two characters,
  one phoneme → longest-match tokenisation. No converse ambiguity in Pāli:
  word-internally, stop + h is always the aspirate.
- **Unicode**: NFC normalisation (ṃ composed U+1E43 ≡ m + U+0323) and the ṁ
  variant (U+1E41) canonicalised to ṃ. Lowercase; the compound hyphen and
  the elision apostrophe are dropped.

Guardrail: IAST diacritics exclusive to Sanskrit (ṛ ṝ ṣ ś) are **rejected**
with their own error — Pāli ḷ is the retroflex lateral, not the Sanskrit
vocalic ḷ; if ṛ/ṣ/ś appear, the text is not Pāli. The tokeniser validates
graphemes, not phonotactics (`dharma` tokenises; detecting that it is not
phonotactically Pāli is §13's job).

ḷh (ruḷha, aḷhaka): the inventory follows the traditional 41-sound alphabet,
which analyses ḷh as the cluster ḷ + h, and it is tokenised that way.

API: `normalize`, `tokenize`, `transcribe` (word → phonemes), `vectors`
(word → embeddings).

## 8. The possibility game: LP *(retired code; result recorded)*

The project's original idea: at a given moment, when someone pronounces a
sound, each feature is either *possible* or *impossible* to co-articulate,
and one computes by applying operations between possibilities — "nasal or
guttural = another possible". That produced a table echoing paraconsistency.

Reconstruction: ask the inventory which segments attest each pair of features
AT ONCE, and **three** statuses appear, not two:

| | criterion | example |
|---|---|---|
| **P** possible | an ordinary witness | nasal+guttural → ṅ |
| **I** impossible | no witness | voiceless+voiced |
| **G** glut | ONLY overdetermined witnesses (ṃ, e, o, v) | voiceless+nasal → only ṃ |

G is "nobody can pronounce it at once — and yet the language has a symbol
that realises it": possible-and-impossible. With the order `I < G < P`,
disjunction = max, conjunction = min, negation swapping P↔I with **G as a
fixed point**, and designated values {P, G}, this is exactly **LP** (Priest's
Logic of Paradox). The glut/gap fork of §2 reappears at the logical level as
the LP/K3 choice.

Verified at the time: the designated contradiction does not explode
(`G ∧ ¬G = G`, designated), De Morgan, lattice laws; and removing the
overdetermined segments from the inventory makes **G disappear and the table
collapse to classical two-valued logic** — once again, paraconsistency lives
in the inventory, not in the definitions.

## 9. Word-level sandhi

`sandhi.assimilate_word` resolves each ṃ in an IAST word against what follows
(Kaccāyana, «vagge vaggantaṃ»):

- **ṃ + stop → that series' nasal**: saṃgha → saṅgha, saṃjāta → sañjāta,
  saṃṭhāna → saṇṭhāna, saṃtāna → santāna, saṃbodhi → sambodhi. Mechanism:
  the meet of the lattice of §6 (`assimilate`).
- **ṃ + y → ññ**: saṃyutta → saññutta, saṃyojana → saññojana. A rule of its
  own (y is not a stop; not the plain meet): nasalise and geminate.
- **Otherwise** (vowel, s h r l v, word-final): ṃ stays — the unresolved
  glut, residual nasalisation (the glut/gap divergence of §2, glut side).

Assimilation is optional in manuscript orthography (saṃgha and saṅgha
coexist); the function produces the canonical assimilated form. All ten test
outputs are attested in DPD (the `lookup` table), including the ññ forms and
the unresolved ones.

### Vowel sandhi (`sandhi.sandhi_join`)

The lattice join (§6), executable over word boundaries:

- a/ā + i/ī → e ({G}∪{P}), a/ā + u/ū → o ({G}∪{L}): upa+ikkhā → upekkhā,
  mahā+udadhi → mahodadhi (DPD decomposes it exactly that way);
- a/ā + e/o → e/o (the union already is the compound): ca+eva → ceva;
- same places → the long vowel: tatra+ayaṃ → tatrāyaṃ, gāmī+iva → gāmīva.

Empirical restriction: only the guṇa pattern (first vowel a/ā) or vowels of
the same place. i+a, u+i and so on proceed by glide formation or elision
(aggi+agāraṃ → aggyagāraṃ), which are NOT the join and are left untouched.
The join is the mechanism; which boundaries trigger it is phonology, just as
in the niggahīta case.

### 9.1 Contraction: the same join, word-internally

`aya` → `e` is exactly {guttural} ∪ {palatal}; `ava` → `o` is
{guttural} ∪ {labial}. That is the join of §6 — the one `sandhi_join`
already performs at a word boundary — applied inside the word. It is
attested and productive: abhibhavati ~ abhibhoti, anavakāsa ~ anokāsa,
palāyati ~ paleti.

**Only these three rules.** Each was measured in isolation against DPD's
5,002 `var_phonetic` pairs (eval/variant_curve.py; agreement with DPD, not
accuracy — see README, "Agreement with DPD is not accuracy"), baseline 63.55%
at θ=ONE_MOVE:

| rule | Δagreement @ONE_MOVE | Δvolume | verdict |
|---|---|---|---|
| `aya` → `e` | +6.74 | +2.8% | the bulk of the gain |
| `ava` → `o` | +1.72 | **−1.4%** | pays for itself twice over |
| `ayi` → `e` | +0.86 | ~0 | adopted 2026-08-02, see below |
| `āya` → `e` | −0.20 | +2.8% | earns nothing alone |
| `āva` → `o` | −0.26 | +0.5% | earns nothing alone |
| `āyi` → `e` | −0.08 | ~0 | earns nothing alone |
| `ayu` → `e` | −0.10 | ~0 | earns nothing alone |
| `avi` → `o` | −0.46 | ~0 | loses ground |
| `īya` → `e` | −2.62 | +2.8% | loses ground |
| `iya` → `e` | −3.06 | +3.7% | loses ground |

**How `ayi` → `e` was found, because the route matters.** It came from
outside: a dpd-db integration benchmark listed the handful of pairs its own
detector caught and this one missed, and three of them were causative
absolutives — bhāvayitvā ~ bhāvetvā, pakappayitvā ~ pakappetvā, visosayitvā ~
visosetvā — sitting at d=1.65, where no threshold reaches. The join is the
one `aya`→`e` already performs, before a front vowel; the rule was missing,
not the principle. All three go to 0.000 with it. Its long-vowel counterpart
`āyi` loses, as do `ayu` and `avi`, so the shape of the other six holds.

Measured effect of the three, as a pipeline step: agreement with DPD
63.6% → **72.9%** at θ=ONE_MOVE and 80.0% → **89.0%** at θ=1.0, for +2.8% candidate volume. With
`assimilate_word` before it, **78.2%**. For comparison, buying those points by raising θ
instead costs roughly double the volume, and the unaided metric does not
reach 88% at any usable threshold (85.0% at θ=1.5, at 17× the volume).

**Why it is a normalisation and not an edit operation.** Admitting
contraction as a 3:1 alignment transition inside `distance` was implemented
and measured: it **breaks the triangle inequality**. The DP minimises over
monotone alignments, and that class is not closed under path composition
once a transition consumes three tokens on one side — the counterexample is
d(abhibhavati, kave) = 4.673 against the path through bhavati at
2.007 + 2.469 = 4.476. (Without the transition the same triple holds with
exact equality, 5.260 = 5.260.) The geminate 2:1 transitions of §14 failed
the same way, only later found (§14, amendment), and were replaced by heavy
units in 2026-10. Since the metric guarantee is load-bearing — BK-trees are
built on it — the contraction lives in `sandhi.contract_word` and is applied
before measuring:

    distance(contract_word(w1), contract_word(w2))

Phonology first, metric second — the same shape as `assimilate_word`.

## 10. The akṣara layer *(retired code)*

The abugida unit — a consonant cluster + vowel (the inherent `a` if unmarked)
+ an optional niggahīta as a diacritic — was defined as an abstract object,
deliberately without any concrete script. `silabea` split IAST words into
akṣaras (buddha → bu·ddha, saṃyutta → saṃ·yu·tta), and a `Simbolo` aggregated
each akṣara's content using the existing operations: places by lattice join,
value by ⊗, vector by `compose_vec`. Retired in the refocus; the syllabic
segmentation is not needed by the comparator.

## 11. The alphabet (akkharā): derived, not listed

`alphabet.py` defines the 41 sounds in traditional recitation order as a
derived object, separating structure from convention:

- **Vowels — derived**: simple before compound, by place (back→front), short
  before long ⇒ a ā i ī u ū e o.
- **Vagga (25) — A THEOREM**: the recitation order k kh g gh ṅ c ch j jh ñ …
  is exactly the lexicographic order of the product Place × A under the key
  (place, base, mod): (0,ε) < (0,+) < (1,ε) < (1,+) < (1,−). The tradition
  recites the semiring in order
  (`test_the_vagga_is_the_lexicographic_product`).
- **Avagga — declared convention**: y r l v s h ḷ follows no structural key
  (by place, h would come first); it is inherited order and is stored as such.
- **ṃ** last, as in recitation.

From the alphabet comes alphabetical ordering of words (`sort_key`,
`sort_words`) over tokenised graphemes: the aspirated digraphs are ONE letter
(khaṇa > kaṇṇa; dhamma < buddha because dh precedes b).

## 12. The language L *(retired code)*

A 20-word subset of Σ*, all attested in DPD, chosen so that between them they
cover all 41 akkharas — a pangram of the alphabet, with deliberate rare
carriers (jaḷa for ḷ, vuḍḍhi for ḍh, thūpa for th and ū, sīha for ī and h,
saṃsāra for ṃ). Retired as a concept; the word list survives as a test
fixture, since a pangrammatic set is the best positive fixture available.

## 13. Executable phonotactics: P, what could be Pāli

`phonotactics.is_possible` defines P with L ⊂ P ⊂ Σ*: which strings are
phonotactically possible as a Pāli word. It is the layer that knows dharma is
not Pāli even though all its graphemes are. P is regular (a linear scan).

Word rules: at least one vowel; ends in a vowel or ṃ; ṃ only after a vowel
(but ṃ + stop is legal: the unassimilated spelling saṃgha coexists with
saṅgha); onset of at most one consonant, or a C+y/r/v cluster (dve, brāhmaṇa),
s+nasal (sneha), or one of the aspirated nasals nh/mh, which are unitary
phonemes and open words (nhāru, nhāyati, mhita; Oberlies, *Pali* §15.1 —
added 2026-10-13, after `eval/oberlies.py` found `nhāyati` rejected); 0–2 consonants between vowels (3 if a valid pair plus a liquid
that also pairs with the second: indriya = n·d·r, lakkhyā = k·kh·y); ṅ never
alone and never initial (only in a homorganic cluster).

Internal clusters — the STRUCTURAL core, derived from the system:
- geminate (identity); aspirated geminate = C + (C ⊗ 0+), composition in A;
- nasal + homorganic stop = non-empty meet of places (the `assimilate` rule
  once more).

Declared RESIDUAL families (like the avagga): sonorant+h (pañha, taṇhā,
mayhaṃ, jivhā), h+m (brahmā), s+nasal (tasmā), C+y/r/v/l (sakya, tatra,
katvā, plavati), and s+t word-internally (bhastā, ghasta, viddhasta). The
last is the sibilant cluster Pāli sometimes leaves unassimilated (Oberlies,
*Pali* §16 rem. (a), p. 102: (vaṅka)ghasta-, bhasta- 'bag', Th 1151, beside
asnāti and bhasma-, which s+nasal already covered). It was excluded until
2026-10-13 as "the marginal st cluster of Sanskritisms"; the grammar lists
these words as Pāli, so the exclusion rejected attested canonical words.
st opens no word (thana, thūpa), and its regular outcome is still tth
(hasta → hattha): admitting it makes Sanskrit-shaped strings such as hasta
possible, which is what "possible" means — P is wider than the lexicon, and
rejecting Sanskrit is the strict tokeniser's job (ś ṣ ṛ), not this
predicate's. The morphological generator's output is unchanged by it (3,920
distinct words before and after).

**Empirical calibration** (DPD, 74,438 cleaned lemmas, 2026-08-01): 98.93%
accepted. Of the 1.07% rejected, 662 are citation lemmas ending in a
consonant (satthar, -vant: grammatical abstractions, correctly rejected) and
137 (0.18%) are DPD's own typos (alkkhika), variant non-homorganic spellings
(ahaṇkāra for ahaṅkāra) and the marginal st cluster of Sanskritisms (bhastā),
excluded knowingly. Of lemmas with a valid ending, 99.82% pass.
These figures had no script behind them. `eval/phonotactics_calibration.py
--dpd` reproduces them: re-run on 2026-10-13 against a newer DPD (74,800
single-word lemmas), with the nh/mh onsets, 98.99% accepted and 99.88% of
lemmas with a valid ending; the 0.06-point rise is the 47 nh/mh lemmas.
With medial st, 99.03% and 99.91%: 26 more lemmas, every one Pāli (the
bhastā compounds, ghasta, the -dhasta and -trasta/-tasta participles). The
64 still rejected for a reason other than a final consonant are DPD typos
(alkkhika, kakcana), non-standard nasal spellings (ahaṇkāra, samukkaṅseti,
ekatimsā: spelling, which normalisation would have to settle, not
phonotactics), suffixes and letter names entered as headwords (ssa, yya,
ṅa), and Sanskrit forms whose Pāli counterpart Oberlies gives (ratna for
ratana, vanaspati for vanappati, padma for paduma).

`phonotactics.pseudoword` inverts the predicate into a generator: legal
pseudo-Pāli, used by the open-vocabulary evaluation of §14.

### 13.1 A second criterion: formability (`morphology.py`)

P answers *could this be a Pāli word?* at the level of sequences. It does
not ask whether the string could be **formed**: a legal syllable sequence
is not yet something anyone could inflect or gloss. `morphology.py` adds
that criterion as an optional generator — `pseudoword` keeps its role and
the numbers that cite it are unchanged.

A form is built as the grammarians build one, dhātu → aṅga → vibhatti
(root → base → ending): pac → paca → -ti = pacati; pac → pacana → -assa =
pacanassa. The present bases are **declared, not derived** — guṇa, vuddhi
and the class infixes admit no small honest rule set, so `ROOTS` records
each root's attested base alongside its gaṇa, the same policy §11 applies
to the avagga order. What is derived is everything downstream: the kita
bases, the junction, and the phonotactic filter every output must pass
(F ⊂ P: formability is added on top of possibility, never traded for it).

Junction, all conditioned by the shape of the boundary rather than by the
identity of the morphemes:

- **hiatus** — the base loses its vowel (paca + antu → pacantu), except
  after the guṇa bases in -e/-o, which carry their class and survive at the
  ending's expense (karo + antu → karontu), unless that would erase the
  ending entirely (karo + e → kare);
- **lengthening** before the first-person endings and imperative -hi
  (paca + mi → pacāmi, paca + hi → pacāhi);
- **shortening** of a long final vowel before a cluster, Pāli admitting no
  long vowel before a double consonant (jānā + nti → jānanti);
- **retroflexion** (nati) — intervocalic n → ṇ after r, blocked by an
  intervening coronal: kar + ana → karaṇa, car + ana → caraṇa, but rudh +
  ana → rundhana. The blocking class is read off the inventory's places,
  the same tongue-tip set the embedding gives its own CORONAL dimension
  (§4).

Novelty comes from **crossing**: bases and endings the canon happens not to
combine. The criterion is the rules alone — whether a form is attested is
no part of it. Attestation serves only to check the junction: of the 4,429
forms the generator can build, **47.9% turn out to be real Pāli** (74.0% of
the verbs, 37.1% of the nominals; DPD lemmas ∪ inflections, 2026-08-01),
with no dictionary consulted in their construction.

**How much the criterion prunes.** `is_formable` applies it to strings the
generator did not build (`analyse` splits a word into aṅga + vibhatti), so
the reduction is measurable against the phonotactic generator. Over 20,000
`pseudoword` samples:

| criterion | survives | reduction |
|---|---|---|
| necessary — any known ending over a syllabic base | 36.4% | **63.6%** |
| discriminating — the ending is ≥ 2 graphemes | 8.9% | **91.1%** |
| strict — the form lies in the generable space | 0.000% (0/20,000) | **100%** |

The first is permissive because the single-grapheme case endings -e, -o and
-ā are satisfied by any vowel-final word; the second is the honest figure
for "ends in a real ending". The third is not a property of the criterion
but of this root list: 42 roots span 3,920 distinct words, so the space is
small and disjoint from random legal syllable sequences. Read the middle
row as the answer: **roughly nine in ten phonotactically legal strings are
not formable words.**

Two structural facts fell out of the measurement. The junction rules never
leave P — 0 of 4,429 combinations were discarded by the phonotactic filter,
so the rules are closed with respect to the phonotactics rather than
needing repair. And the space contains 4,429 forms over 3,920 distinct
strings: the 509 collisions are real syncretism (pacanaṃ is accusative
singular masculine and nominative singular neuter at once), not a defect.

Scope, stated plainly: this models word formation, not the history of any
particular word. It does not model consonant loss (kar + ta → kata) or the
assimilations that reshaped inherited clusters, so the irregular agent
suffix -tar (kar → kattā) and the -ti abstracts (gam → gati) are left out
rather than approximated. Forms whose junction would leave P are dropped,
not repaired.

Re-run of the §14 open-vocabulary evaluation over morphological base words
(`--morphological --oov-only`, attested forms discarded because that
experiment's premise is measuring without a dictionary — an option of the
evaluation, not a criterion of the generator): the phonological distance
tells a scribal variant from an arbitrary one in 91.9% / 98.8% / 99.8% of
cases at 1 / 2 / 3 edits, against Levenshtein's 50.9% / 50.7% / 51.9%. The
conclusion holds on the harder population. (Measured before the heavy
units of §14; this run needs DPD and has not been repeated.)

## 14. Phonological distance between words (`distance.py`)

Three layers, with the algebra as the metric:

1. **`algebraic_cost(x, y)`** over A: the word metric of the group generated
   by ⊗ — [bases differ] + [modifiers differ] ∈ {0, 1, 2}. Any modifier
   change is ONE move because + ⊗ + = −.
2. **`cost(g1, g2)`** between phonemes: the truncated ANGULAR distance,
   min(1, arccos(cosine at ρ*)/(π/2)). Because the embedding is the
   homomorphic image of ⊗, ρ* balances the elementary moves, and arccos is
   monotone, the geometry is the algebra: cost(k,kh) = cost(k,g) exactly, and
   cost grows monotonically with the algebraic cost within each series
   (tested). It also sees what A does not reach: places (the multi-hot
   lattice) and vowel length.

   **Why LINEAR in the angle, and not re-warped — derived, not defaulted**
   (`eval/noisy_channel.py`). A concave f (log, sqrt) would preserve the
   metric: concave with f(0)=0 is subadditive, and subadditivity carries the
   triangle inequality through a re-warp. So the choice needs an argument,
   and there is one. Read the edit distance as a NOISY CHANNEL — the standard
   reading, and the reason costs SUM at all: a word is corrupted by
   independent operations, the cost of one is −log P(operation), and a path's
   cost is the corruption's negative log-likelihood. Then the transformation
   is fixed rather than chosen: cost ∝ −log P, so exponential decay of
   confusability implies a LINEAR cost and power-law decay a logarithmic one.

   Measured, by binning real search candidates by distance and taking the
   fraction that are annotated variants, the decay over the operating range
   is exponential — R² 0.974 for the identity against 0.932 for log at
   d ≤ 1.5, and the identity wins at every cut through 2.5. Log overtakes it
   only past d ≈ 3, where P ≈ 0.0001 and no usable threshold reaches (θ=1.5
   already costs 10.6 candidates per lemma). A concave warp was separately
   implemented and reverted on volume grounds (TODO.md); this says it was
   also wrong in principle, its R² advantage coming from a tail with no
   signal.

   Bound on the claim: this fixes the right transformation OF THIS GEOMETRY.
   It does not validate the geometry, which rests on §4.
3. **`distance(w1, w2)`** between words: weighted edit distance over
   tokenised graphemes (substitution = cost, ins/del = 1). Always ≤
   `levenshtein` (same tokenisation, every change = 1), which is the baseline.

Against DPD (38,819 lemmas, probe *dhamma*): Levenshtein returns an arbitrary
tie at distance 1 (camma, amma, dhammā, damma indistinguishable); the
phonological distance grades them: dhammā 0.33 < damma 0.34 < vamma 0.53 <
dhammī 0.61 … Levenshtein is blind to kinship; the phonological distance IS a
theory of kinship (the algebra's).

**`distance` is a true metric**, by two chained theorems: the angular
distance is the spherical geodesic (spherical triangle inequality) and
truncation min(1,·) preserves it; and weighted edit distance with a metric
substitution cost and sub ≤ ins+del is a metric over sequences
(Wagner–Fischer). Verified: the triangle inequality exhaustively over all
41³ grapheme triples and by sampling over word triples. (Originally
1 − cosine was used, which is not a metric; the angular distance replaced it
without structural loss — arccos is monotone, so orderings, the balance and
the Levenshtein bound all survive; only the scale changes.)

**Amendment (2026-08, measured — see docs/c-core.md).** The second theorem's
hypothesis is not met once §9's geminate transitions are added, and the
sampling above did not reach a counterexample. `sub ≤ ins+del` still holds
per substitution, but the 2:1 and 1:2 transitions are not substitution-and-
indel paths, so the class of monotone alignments is not closed under
composition — the same failure §9.1 records for contraction. Measured: 42
violating triples in 10,648 over 22 words with the transitions enabled, 0
with them disabled, e.g.

    d("makka", "saṅgha") = 2.262374
      > d("makka", "magga") + d("magga", "saṅgha") = 2.064786

So the word-level guarantee was: identity and symmetry always; the triangle
over words without doubled consonants; and neither for the empty string.
The geminate transitions were worth +15.1 points of agreement with DPD
(`eval/ablate_geminates.py`), so removing them was not on the table. (Their
replacement, the heavy units, is worth +14.4 at θ = ONE_MOVE on the newer
5,143-pair build: 62.6% with them, 48.2% without.)

**Resolution (2026-10-13): heavy units, one segmentation per word.**
`eval/triangle_geminates.py` traced every violation to one cause — each
comparison decided for itself whether a doubled pair was one long consonant
or two letters, and a unit change is cheaper than changing both halves
(kk~gg 0.377 against k~g 0.470 each) — and measured the repairs that keep
that per-comparison choice: pricing the transitions so that composition
closes needs every unit cost raised to 2.0, which is removing them; closing
the transitions under composition leaves 50 of 86 violations, because a
geminate can be split across other material. What works is the classical
setting itself. Each word is segmented ONCE, left to right, into letters
and HEAVY UNITS — the geminates, and the homorganic nasal+stop clusters
(the non-empty meet of §13 family c; the niggahīta carries all five places,
so ṃ + any stop is one too) — and the DP is plain substitution and indel
over the units. A unit is priced by its halves: a token is (first half,
second half, weight), a letter X being (X, X, light), and

    cost(u, v) = max(cost(u₁, v₁), cost(u₂, v₂), |w(u) − w(v)|)

with w(u) the angular cost of making u's second half long (the LENGTH
dimension; exactly what degemination cost before, consonant by consonant).
The max of metrics on a product is a metric, so cost stays one over all 126
tokens (verified exhaustively, 2,000,376 triples); a unit's indel is the
cheapest route through a single token, which satisfies both cost/indel
conditions (verified over all 15,876 pairs). With one sequence per word,
Wagner–Fischer applies and `distance` is a metric over all words, the empty
one included. A geminate counts once (kk~gg = k~g), a cluster differs from
a geminate by the half that differs (tt~nt = t~n, so citta~cinta keeps its
0.631), a change inside a cluster costs what it costs alone (nt~nd = t~d),
and costs between letters do not move. The battery goes to 30/30
(saṅgha/saṃgha/saṇgha resolved). The price, measured: a unit cannot align
letter by letter with a cluster of two articulations, so Sanskrit-shaped
pairs move away (tatra~tattha 0.831 → 1.470; Sanskrit forms within two moves
of their Pāli reflex 40.0% → 31.6% in Oberlies, 47.8% → 35.0% in Geiger),
and `distance ≤ levenshtein` no longer holds in general; a one-letter change
that leaves half a geminate costs a broken unit (open vocabulary, see below).
Pāli doublets do not move. Every agreement figure predates the change.

**Where information is and is not lost** — the design's flattening points,
audited (2026-08-01):

- The scalar aggregation of the edit script is recoverable: `alignment`
  returns the optimal script and its costs sum exactly to `distance`
  (tested), so the pair (scalar, script) loses nothing.
- The 1.0 cap on `cost` flattens 100 of 820 letter pairs (12.2%) — but their
  raw values lie in 1.041–1.055 (a sliver beyond orthogonal), none of them
  shares a place of articulation, and removing the cap changes zero
  decisions in the discrimination battery. Beyond-orthogonal values are an
  artifact of the 120° modifier representation, not phonological signal:
  the cap flattens noise, where Levenshtein's flat matrix flattens the near
  field — the signal itself. Asserted in
  `test_distance.py::test_the_cap_only_flattens_unrelated_pairs`.

Known limitations:
- ✦ Place adjacency: RESOLVED for the attested cases by the two karaṇa
  bridges (§4, dims 12–13) — t↔ṭ and k↔c now 0.601 < k↔p 0.889, with
  within-series costs untouched. The remaining eight place pairs get no
  adjacency, deliberately: they share no active organ, and they account for
  only 15.9% of the place substitutions in `var_phonetic` against the
  bridges' 84.1%.

  *Superseded claim*: this entry previously read "the tongue-tip confusion
  is the one transmission attests", which the data does not support —
  guttural~palatal occurs 95 times (11.4%) in the same `var_phonetic` count. The
  coronal bridge was right and incomplete.
- The glut inflates ṃ's norm (five places): saṅgha~saṃgha gives 0.77 — less
  than Levenshtein, but more than manuscript variation warrants. The distance
  treats ṃ as the overdetermined object it is, not as the orthographic
  variant it sometimes plays; for collating spellings, compare the RESOLVED
  forms first (`assimilate_word`).
- It compares words, not sentences.
- Keyboard-typo noise is outside the operating envelope: an independent
  benchmark (full DPD lexicon, n=150/scenario) measured 80.0% vs
  rapidfuzz's 87.3% on random ASCII edits — non-Pāli characters are
  rejected by strict tokenisation (`lenient=True` absorbs them as opaque
  tokens at uniform cost 1 — the metric survives, but a typo has no
  phonology to discriminate by; independently measured: on out-of-inventory
  input lenient equals char-level accuracy and removes the 100%-exception
  failure mode — robustness, not accuracy, and on Pāli-only noise strict
  and lenient are identical), digraph-straddling typos amplify at token
  level, and there is no transposition operation. On scribal/phonological confusions the same
  benchmark measured 100% (150/150, no ties) vs 88.7%. The error model
  decides the measure — as a universal rule now: accuracy over a mix is
  linear in the typo share p, so there is a single crossover, measured at
  p* = 56.8% (95% CI 45.4–68.7%, eval/decision_curve.py, n=600 per error
  model, tie-aware, full lexicon: char-level scores 91.6% on typos and 89.3%
  on phonological confusions, the hybrid 85.5% and 97.3%). Re-derived
  2026-08-02 after the dorsal bridge and the pipeline work; the figure has
  moved twice (50% → 63% → 56.8%) as the metric changed, so quote the script
  rather than a remembered number. Deploy the hybrid iff p < p*; measure your own
  p with eval/profile_error_mix.py. docs/comparator.md documents the rule,
  the measured fact that upstream ASCII-normalisation routes skim
  only ~4% of phonological confusions (the ASCII→diacritic direction cannot
  be intercepted by construction), and the recommended hybrid (rapidfuzz
  prefilter → phonological re-rank, 12–15 ms/query, +10.8 points on the
  post-normalisation residue).

### Side-by-side battery (tests/test_battery.py)

A dictionary-free regression battery of 30 **discrimination triples**
(base, nearer, farther) where linguistics fixes the answer: `nearer` differs
from `base` by a smaller phonological step than `farther` does. A measure
passes only on a strict ordering — a tie counts as a failure, since a tie
forces the caller to guess. Families covered: vowel length, aspiration,
voicing, place (the retroflex/dental manuscript confusion), nasals, clusters
and gemination, Sanskrit reflexes, and morphology.

| measure | cases won |
|---|---|
| phonological | **29 / 30 (96.7%)** |
| levenshtein | 8 / 30 (26.7%) |

Levenshtein wins exactly the eight cases where the *edit count* differs
(1 vs 2). Wherever both alternatives are one edit away — which is the normal
situation for manuscript variants — it ties and cannot choose.

The mechanism, measured over the 190 pairs of a fixed 20-word set:

| measure | distinct values |
|---|---|
| phonological | 169 |
| levenshtein | 7 |

The one loss is the documented glut limitation, kept in the battery rather
than quietly dropped: saṅgha~saṃgha (0.740, a real orthographic variant)
lands further than saṅgha~saṇgha (0.631, ill-formed), because the glut gives
ṃ all five places. Two tests pin it down — one asserting the limitation is
still exactly this one, another asserting that the documented remedy
(`assimilate_word` first, compare second) turns it into the strongest
possible hit: the two spellings become the same word, at distance 0.

Run `python tests/test_battery.py` to print the full side-by-side table.

### Ground-truth evaluation (eval/compare_levenshtein.py, 2026-08-01)

Three retrieval tasks against the full DPD lexicon (38,819 lemmas, fixed
seed; ties credited 1/k — the expected value under random tie-breaking):

| task | n | phonological | levenshtein | mean rank p/l | tied at top p/l |
|---|---|---|---|---|---|
| scribal corruption → original | 400 | **95.5%** [93.0, 97.1] | 83.9% | 1.06 / 1.33 | 1.0 / 1.7 |
| sandhi ṃC → attested assimilated | 40 | **82.5%** [68.0, 91.3] | 77.1% | 1.27 / 1.29 | 1.1 / 1.6 |
| tadbhava Sanskrit → Pāli reflex | 12 | **58.3%** [32.0, 80.7] | 36.1% | **2.54** / 9.50 | 1.2 / 2.8 |

Re-run 2026-10-13, after the heavy units, on a newer DPD (75,733 lemmas):
scribal 95.2% against 81.4% (mean rank 1.06 / 1.42), sandhi 87.5% against
83.8% (100% / 100% through `assimilate_word`), tadbhava 58.3% against 36.1%
unchanged. The Levenshtein column moved as much as the phonological one, so
the shift from the table is mostly the new lexicon; it is not the units'
effect, which needs a paired run on one lexicon.

Wilson 95% intervals, and they should be read: only the first row has the
sample to resolve anything. At n=40 the interval spans ±11.6 points and at
n=12 ±24.4, so those rows separate the two MEASURES but cannot rank
calibrations of one. The sandhi row moved 87.5% → 82.5% purely from being
redrawn when the experiments were given independent RNG streams — no change
to the metric. Row 1 was re-measured at n=400 against a corrected
`CONFUSION_PAIRS`: it had omitted the tongue-body confusions the dorsal
bridge models while including the tongue-tip ones (TODO.md, Phase 3), which
is why it rose from the 92.5% previously published here.

(The tadbhava row improved most from the coronal bridge — 41.7% → 58.3%,
mean rank 3.08 → 2.46 — which is no accident: Sanskrit→Pāli correspondences
are full of dental/retroflex adjustments, exactly the adjacency the bridge
encodes.

**The dorsal bridge looked as though it were paid for here — and it was not.**
When it landed, scribal-corruption retrieval appeared to fall 94.4% → 92.5%
and tadbhava drifted 2.46 → 2.54, so it was recorded as a genuine trade:
−1.9 retrieval points against +2.8 to +3.9 of agreement with DPD. Both parts of
that were wrong (TODO.md, Phase 3):

- 92.5% came from n=80, i.e. 1.5 cases. At n=1000 with a paired test the
  loss is 0.9 points, half as large.
- The remainder was the benchmark scoring against its own hypothesis.
  `CONFUSION_PAIRS` listed the tongue-TIP confusions but not the tongue-BODY
  ones, so no generated corruption was ever dorsal and this metric could
  only be penalised here, never rewarded. Corrected — the omission has no
  support in the data — the difference is 97.1% vs 97.6%, McNemar p=0.2266,
  not significant, and the headline row rose to 95.5%.

What survives is the mechanism, not the price: making k↔c cheap does promote
guttural/palatal near-misses in a ranking. It just does not cost what was
recorded. Do not quote the −1.9.)

**Failure analysis (why not ~100%?)** — each task has a different ceiling,
diagnosed case by case:

- **Exp. 1: an information ceiling, already reached.** The 4 failures out of
  80 are corruptions that genuinely land closer to ANOTHER real word (pāṭu ←
  pātu, but paṭu exists one lengthening away). The corruption destroys the
  information; the metric picks the most plausible posterior, which is
  sometimes not our ground truth. Beating it requires context (frequency, the
  surrounding phrase), not finer phonology.
- **Exp. 2: 100% reachable, and reached.** The 4 failures were the glut's
  inflated norm (ṃ→ṅ 0.77 > a final vowel's 0.61: saṃghī beat saṅgha).
  Resolving sandhi before comparing (`assimilate_word`, the documented
  workaround) fixes every failure: **82.5% → 100%**. The right pipeline is
  phonology first, metric second.
- **Exp. 3: missing laws, not missing precision.** Tadbhava is not noise but
  SYSTEMATIC sound change (rm→mm = assimilation + gemination: correlated
  edits), while edit distance assumes independent edits. A mean rank of 2.54
  says the metric brings the answer into the immediate neighbourhood of
  38,819; picking it would require a transducer of Sanskrit→Pāli sound laws —
  historical grammar, not distance between sounds, and out of scope for this
  library (decided 2026-10-13).

**Verdict: the phonological distance wins all three tasks.** The mechanism is
in the tie column: Levenshtein reaches the top with 1.6–2.8 indistinguishable
candidates and has to guess; the phonological distance almost never ties. In
scribal corruption the error drops ~3× (5.6% vs 16.4%); in tadbhava the mean
rank is 3× better (the kinship signal survives several accumulated edits,
where Levenshtein is left counting them).

Methodological lesson: with a 6,000-lemma sample the two measures nearly tied
— the phonological advantage grows with lexicon density, because
Levenshtein's ties grow with it. An honest comparison must run at real scale.

### OPEN-vocabulary evaluation (eval/open_vocabulary.py)

A fair objection to the above: evaluating by retrieval against DPD inherits
its closed world — comparisons between forms that are NOT in the dictionary
(real misspellings, unrecorded variants) are never measured, and a metric
should not depend on any lexicon.

Answer: forced choice with no dictionary. Base words = pseudo-Pāli from the
phonotactic generator (`phonotactics.pseudoword`, legal by construction;
99.5–99.8% certified outside DPD — the dictionary used only as a negative
control). For each base: a SCRIBAL variant (a documented manuscript
confusion) and an ARBITRARY one (same number of edits, an unrelated
grapheme). Which is closer? (a tie scores 0.5):

| edits | phonological | levenshtein |
|---|---|---|
| 1 | **88.0%** | 50.4% |
| 2 | **92.4%** | 50.5% |
| 3 | **96.2%** | 50.5% |

(With the heavy units, 2026-10-13. Before them, on the same base words:
90.9 / 96.0 / 99.2. The drop is the generator's: it changes ONE letter, so
it writes half-geminates (`tṭ`) and half-clusters that Pāli does not spell,
and with one segmentation per word such a string costs a broken unit. On
the trials where both variants are possible Pāli the two metrics agree
within noise — 92.8 / 99.5 / 100% before, 92.2 / 97.9 / 100% after, n = 548
/ 211 / 68 over 1,500 trials per level, `eval/triangle_geminates.py`.
Earlier still, until the medial-st change of the same day: 90.5 / 95.8 /
99.2 and 50.2 / 50.2 / 50.6. Admitting
medial st (§13) widened the clusters `pseudoword` draws from, so the same
seed draws different base words; the metric did not change. The
`--morphological` variant, whose bases do not come from `pseudoword`, gives
identical output before and after.)

**Levenshtein sits at exact chance, by construction**: with no lexicon to
disambiguate for it, it cannot tell a plausible variant from an arbitrary
mutation — every edit weighs 1. The phonological distance tells them apart on
its own, and does so better as edits accumulate. The residual at one edit
(12% before any karaṇa bridge, 9.1% with both, 12.0% with the heavy units) is
dominated by cases where the arbitrary substitution happens to land on a
non-scribal phonological neighbour (t→n, same place), and since the units by
scribal edits that break a geminate into a string Pāli does not write.

Methodological conclusion: the metric does not have the dictionary's
limitation — the retrieval evaluation did. The two evaluations complement
each other: the closed one measures the practical task (searching DPD); the
open one measures the metric itself.

### Scholarly ground truth: Geiger's Pāli Grammar (eval/geiger.py)

Geiger, *A Pāli Grammar* (PTS) supplies the first NON-synthetic evaluation
data. The book is in copyright and is not shipped; what the repository
does not carry even the extraction: the word pairs live in a local case file,
`geiger_cases.json` (`eval/_data.py`, `NOTICE`), which `--harvest PATH`
derives from your own OCR. Extraction is
precision-first (the Pāli side must be DPD-attested;
relatedness filtered with the rival char measure — anti-circular by
construction):

- **Tadbhava at scale** — 157 Sanskrit→Pāli pairs from the grammar itself
  (previous tadbhava evals had 12–18 hand-picked pairs). Ranking the full
  lemma space, expected top-1: **hybrid 32.8% vs char-level 22.4%**
  (n=131, DPD v0.4.20260728). Re-run 2026-10-13 after the heavy units, on a
  newer DPD: **hybrid 24.5% vs char-level 22.4%**, the doublets at 25.0%
  unchanged. How much of that drop is the units and how much the lexicon is
  what `eval/geiger_history.py` answered, replaying the same pairs against
  each historical `distance` (the script and that history were retired when
  the repository restarted from one commit on 2026-10-13; the figures below
  are its record). Measured, with the same pairs and pools: the last two
  commits before the units 32.8% on the newer lexicon (the lexicon did not move
  it), HEAD 24.5% — **the heavy units cost this evaluation 8.4 points**
  (11 pairs of 131; the step alone: paired bootstrap [−13.0%, −4.2%],
  McNemar 15 vs 1 discordant, p < 0.01). From the first published 35.6% the total is −11.2,
  paired bootstrap [−17.7%, −4.7%], McNemar 24 vs 7 discordant, p < 0.01: no
  longer a trade within noise but a real loss on Sanskrit→Pāli ranking, the
  same direction as the Oberlies distances. The doublets stay at 25.0%.
  (A first run blamed the wrong commit: an editable install handed old
  worktrees today's C core. Fixed in the script.) The strongest at-scale evidence for the
  metric so far, on scholar-attested pairs. First published as 35.6%, and
  the difference is this section's own doing: the epenthetic indel class
  (−1.1), the geminate transitions (−1.5) and the dorsal karaṇa bridge
  (−0.1) each cost tadbhava a little, and the same work took the doublets
  below from 11.4% to 25.0%. The loss is 3.6 pairs of 131 and is not
  significant — paired bootstrap [−7.9%, +1.8%], McNemar p = 0.63 — so it
  prices the trade, it does not establish a regression
  (measured by the same retired replay). char-level and n
  are unchanged, which is what says the lexicon underneath did not move.
- **Attested doublets** — 24 "X beside Y" variant pairs (vuṭṭhita/uṭṭhita,
  dāni/idāni, sve/suve, sotthi/suvatthi, maññeti/maññati, ekārasa/ekādasa,
  asmi/amhi…). These exposed the flat-indel gap — genuine transmission
  variation is dominated by insertions and deletions (svarabhakti,
  v-prothesis, aphaeresis, final-ṃ loss), which the metric used to charge a
  flat 1.0. RESOLVED by the EPENTHETIC class (distance.py): vowels, y, v
  and ṃ carry a DERIVED indel weight of 0.627 — the cheapest value the
  triangle inequality on Σ ∪ {ε} allows (the extremal solution, like ρ*),
  verified exhaustively with foreign and opaque tokens included. Measured
  effect: doublet retrieval doubled, 11.4% → 25.0%, now level with
  char-level (25.0%); the closed and open evaluations are unchanged; and
  the typo endpoint of the decision curve improved too (82.8% → 86.0%,
  vowel typos benefit), widening p* from 50% to 61%. Independent re-benchmark of the epenthetic work (dpd-db side, public
  API): on an insertion/deletion error class the hybrid rose 82.0% → 89.3%
  (half the measured gap closed) with no regression on typos (+3.3),
  scribal (+0.7) or coronal (noise) controls; char-level keeps a 6.7-point
  lead on that class — the cross-class inversion price of weighting (an
  expensive-edit truth loses to cheap-edit impostors). Their endpoint
  arithmetic puts the deployment crossover near 75% typo share. Gemination
  RESOLVED from below, as the mathematics suggested: Pāli geminates are
  LONG consonants — the same phonological parameter as vowel length, and
  the metrical tradition prices both alike. First priced by alignment
  transitions (2:1, 2:2), which broke the triangle inequality (§14,
  amendment); since 2026-10-13 by heavy units, one segmentation per word,
  the cluster made a unit too so that citta/cinta — which an earlier
  collapse-based design broke — keeps 0.631: attha↔atha = 0.470, one
  elementary move, the battery at 30/30, and the metric a theorem again.
- **Foreign phonemes** (phonology.FOREIGN): ś, ṣ, ṛ now carry real
  phonology in lenient mode (ṣ↔s 0.460 via the coronal bridge, ś↔s 0.667,
  ṛ↔a 0.608) instead of opaque cost 1 — justified by the tadbhava data at
  scale. Strict tokenisation, is_possible and the inventory are untouched:
  they are priced, not admitted. Also in the grammar, unharvested: irregular and suppletive
paradigms (hoti/bhavati, kāhisi/dakkhasi) — lexical alternations for a
synonym/variant table rather than metric material.

### Against DPD's hand-written PHONETIC_RULES (eval/phonetic_rules.py)

dpd-db carries 66 hand-written substitution rules (tools/synonym_variant.py)
generating phonetic-variant candidates between headwords — exactly the task
this metric models. Measured (2026-08-01):

- **Rule level**: hand-rule median distance 0.608 vs 0.782 for non-rule
  letter pairs; AUC 0.831. The expensive tail is not disagreement about
  sounds but rules that are secretly MORPHOLOGICAL laws (e↔aya 1.65,
  o↔ava — the guṇa correspondence; ṭhā↔ṭhaha) — the same "transducer, not
  metric" category as tadbhava, consistently priced as such.
- **Database level**: over a 20% lemma sample, 3,784 real headword pairs
  are connected by one hand-rule application. **The metric reaches 100% of
  them at θ = max rule cost, 85.7% at θ = the rule median**.
- **The metric's candidate additions**: 114 non-rule pairs priced below the
  rule median, headed by the compound-place vowels (ā↔e, ā↔o, ū↔o) and the
  entire ASPIRATION tier (g↔gh, j↔jh, b↔bh… plus voiced-aspirate↔nasal,
  dh↔n) — a systematic family absent from the rule list (it has voicing
  pairs but no aspiration pairs). Candidates for review, not automatic
  truths: the rules encode attested variation, the metric encodes
  phonological proximity; the metric alone would over-generate.

The 0.2% of base words that were NOT out-of-vocabulary are pseudo-words that
turned out to exist: `ajā` (she-goat), `guda`, `khaḷa` (rough; rascal),
`sohajja` (friendship). Not a defect — evidence that the generator samples
the right space, since real Pāli lives in P. The collision rate is itself a
measure of how densely Pāli occupies its own phonotactic space at short
lengths.
