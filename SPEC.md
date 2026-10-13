# abugida — specification

abugida measures the phonological distance between two Pāli words written in
IAST. This document defines what the library computes and why each piece has
the form it has: the algebra of phonological values (§1), the niggahīta
(§2), the places of articulation and their lattice (§3), the embedding (§4),
the input representation (§5), sandhi (§6), the alphabet (§7), phonotactics
and formability (§8), and the distance itself (§9). §10 lists the open
theoretical points; §11 the evaluation instruments and what they currently
report.

Every phoneme is described by a **place of articulation** (the traditional
*ṭhāna*) and a value of the algebra `A`, which encodes voicing, aspiration
and nasality. Everything else is derived from those two.

## 1. The algebra A

A carrier set of six elements, the product of two axes:

```
A  =  {0, 1}  ×  {ε, +, −}
       base       modifier
```

Notation: `0`, `0+`, `0−`, `1`, `1+`, `1−` (where `0` abbreviates `0ε`).

| | reading | realisation |
|---|---|---|
| `0`  | voiceless          | k c ṭ t p |
| `0+` | voiceless aspirate | kh ch ṭh th ph |
| `0−` | niggahīta          | ṃ |
| `1`  | voiced             | g j ḍ d b |
| `1+` | voiced aspirate    | gh jh ḍh dh bh |
| `1−` | nasal              | ṅ ñ ṇ n m |

The base axis is voicing. On the modifier axis `+` is aspiration, `−`
nasality, `ε` unmarked.

### The operation ⊗

Two axioms:

```
0+ ⊗ 0− = 0
1+ ⊗ 1− = 1
```

With associativity they determine the whole structure:

- **The modifier is Z₃.** `+ ⊗ − = ε` makes `+` and `−` mutual inverses; the
  submonoid they generate is a group of order 3, hence Z₃, and therefore
  `+ ⊗ + = −`. The idempotent alternative (`+ ⊗ + = +`) is not associative:
  `(+⊗+)⊗− = ε` but `+⊗(+⊗−) = +`.
- **The base is the OR semilattice, not Z₂.** With Z₂, `1+ ⊗ 1− = 0`,
  against the second axiom. Hence `1 ⊗ 1 = 1` and `1` absorbs: voicing,
  once present, is not undone; aspiration and nasality cancel.

`(A, ⊗)` is a commutative monoid — a Clifford semigroup, the semilattice
`{0 < 1}` of two copies of Z₃. Its units are the voiceless values
`{0, 0+, 0−}` ≅ Z₃; the voiced values `{1, 1+, 1−}` form an absorbing ideal
that is itself a Z₃ with identity `1`.

| ⊗ | 0 | 0+ | 0− | 1 | 1+ | 1− |
|---|---|---|---|---|---|---|
| **0**  | 0  | 0+ | 0− | 1  | 1+ | 1− |
| **0+** | 0+ | 0− | 0  | 1+ | 1− | 1  |
| **0−** | 0− | 0  | 0+ | 1− | 1  | 1+ |
| **1**  | 1  | 1+ | 1− | 1  | 1+ | 1− |
| **1+** | 1+ | 1− | 1  | 1+ | 1− | 1  |
| **1−** | 1− | 1  | 1+ | 1− | 1  | 1+ |

### 1.1 A is a commutative semiring

**No ring exists with ⊗ as one of its operations.** ⊗ is not a group (`1`
has no inverse: `1 ⊗ x` always has base 1) and has no absorbing element
(the modifier always turns). `test_algebra.py::TestNoRing`.

What exists is the next structure down:

```
A  ≅  B × F₃
      │    └─ modifier: the FIELD of three elements
      └────── base: the boolean semiring ({0,1}, OR, AND)
```

`⊗` is the sum of this semiring (OR on the base, + in F₃), and both axioms
follow from it. The componentwise product is the multiplication:

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

- **Zero** is `0`, the plain voiceless stop: neutral for ⊗, absorbing for ⊙.
- **One** is `1+`, the voiced aspirate.
- `1− ⊙ 1− = 1+` (2·2 ≡ 1 in F₃). The units of ⊙ are `{1+, 1−}` ≅ Z₂.
- `x ⊙ (y ⊗ z) = (x ⊙ y) ⊗ (x ⊙ z)`, verified over all 216 triples.

⊗ accumulates features (the union of what is present); ⊙ takes the
coincidence (what is shared; the unmarked value absorbs the mark). A
semiring is a ring without subtraction, and the absence of subtraction is
the algebraic form of "voicing is not undone".

Over the embedding, ⊙ descends as `mult_vec`, not bilinearly: the circular
representation is that of F₃'s additive group, and the field's product acts
on it by automorphisms — `·1` identity, `·2` complex conjugation, `·0`
collapse to the neutral point. `test_embed.py::test_mult_homomorphism`.

### 1.2 Two experimental structures

`algebra.py` also carries two operations that nothing above it imports.
They answer what the alternatives to this algebra would be.

- **XOR on the base** (`compose_xor`). With Z₂ in place of the OR
  semilattice, ⊙ still distributes, `0` still absorbs and `1+` is still
  neutral: the result is a commutative ring, F₂ × F₃ ≅ **Z/6Z**, with
  `1+ ↦ 1` (0↦0, 1+↦1, 0−↦2, 1↦3, 0+↦4, 1−↦5). It buys subtraction —
  devoicing by composition, `1 ⊗ 1 = 0` — which Pāli does not do.
  `test_algebra.py::TestXorVariant`.
- **A lattice reading** (`or_`, `and_`, `not_`, `sum_`). With the base
  ordered {0 < 1} and the modifier as the chain ε < + < −, join, meet and
  the order-reversing complement form a distributive De Morgan algebra that
  is not boolean: `0+` and `1+` have no complement. Its symmetric difference
  `sum_` agrees with `compose_xor` on exactly 20 of 36 pairs — those where
  at least one operand is unmarked — and the failure holds under all twelve
  product orderings of the six elements. A lattice cannot express the
  cyclicity `+ ⊗ + = −`; that the modifier is a field is load-bearing.
  `test_algebra.py::TestLatticeOps`.

## 2. The niggahīta as a glut

In classical features `0−` is a contradiction — a voiceless nasal. Here it is
a **unit** (`0− ⊗ 0+ = 0`), so the contradiction is reversible and local; the
absorbing element is `1`, voicing. This is the signature of a paraconsistent
system, with a caveat of scope: ⊗ is feature composition, not a logical
conjunction, and a paraconsistent *consequence* relation would need an
information order distinct from ⊗ (§3).

ṃ is read as a **glut**: it has all five places at once, and the context
selects one. `saṃ+gha → saṅgha`, `saṃ+jāta → sañjāta` are resolutions of an
overdetermination (§6.1). Word-finally and before a vowel nothing resolves
it, and the residual nasalisation remains. The reading is fixed in
`phonology.NIGGAHITA_PHONEME`.

## 3. Places and their lattice

The five traditional places, back to front — also the canonical order of the
alphabet:

`kaṇṭhaja` (guttural) · `tāluja` (palatal) · `muddhaja` (cerebral) ·
`dantaja` (dental) · `oṭṭhaja` (labial)

Traditional grammar assigns compound places: `e` is *kaṇṭhatāluja*, `o`
*kaṇṭhoṭṭhaja*, `v` *dantoṭṭhaja*. ṃ is the limiting case, with all five. A
place is therefore a **set** (multi-hot), and the sets form the lattice
(2^PLACES, ⊆):

```
                {G,P,C,D,L}  =  ṃ                ⊤  (the glut)
               /     |      \
     {G,P} = e    {G,L} = o    {D,L} = v          compound places
        |        /    |    \       |
       {G}    {P}   {C}   {D}    {L}              simple consonants
```

The lattice operations are phonological processes:

- **The meet is assimilation.** Resolving ṃ's glut before a stop is
  descending to ∧ (`phonology.assimilate`). The lattice supplies the
  mechanism; the trigger (only before a stop, §6.1) is phonological — the
  bare meet would also resolve before a vowel.
- **The join is vowel sandhi.** `places(a) ∨ places(i) = {G,P} = e`: a+i → e
  and a+u → o are the join (`sandhi.sandhi_join`, §6.2), and so is the
  word-internal contraction aya → e, ava → o (§6.3).

The order lives here and not in `A`: the modifier axis admits no non-trivial
partial order compatible with ⊗, because a translation-invariant order on a
finite group generates a strictly increasing chain that returns to its
origin.

## 4. The embedding

Each phoneme is a vector of 14 dimensions:

| dim | feature | values |
|---|---|---|
| 0–4  | place (gut, pal, cer, dent, lab) | multi-hot; bridged places carry √½ |
| 5    | voicing (base of A)              | 0 / 1 |
| 6–7  | modifier of A                    | (cos θ, sin θ), θ = 2πk/3 |
| 8    | syllabic                         | 0 / 1 |
| 9    | length                           | 0 short / 1 long |
| 10   | continuant                       | 0 / 1 |
| 11   | lateral                          | 0 / 1 |
| 12   | coronal (karaṇa: the tongue tip)  | √½ for cerebral/dental, else 0 |
| 13   | dorsal (karaṇa: the tongue body)  | √½ for guttural/palatal, else 0 |

Dims 0–7 are the algebra and the places; 8–11 cover what `A` does not reach
(vowels, semivowels, sibilant, aspirate). Voicing for segments outside `A`
is inventory data (`Phoneme.voiced`, read through `is_voiced`). For segments
with no value in `A`, dims 6–7 carry **⊥ = (0, 0)**, zero norm and distinct
from ε = (1, 0): neutral in `compose_vec`, absorbing in `mult_vec`.

### The karaṇa bridges

The tradition splits articulation into ṭhāna (the passive place) and karaṇa
(the active organ), and four of the five places pair up under an organ.
Cerebral (*jivhopagga*, the underside of the tip) and dental (*jivhagga*, the
tip) share the tongue **tip**; guttural (*jivhāmūla*, the root of the tongue)
and palatal (*jivhāmajjha*, its middle) share the tongue **body**. Labial
uses the lip and bridges to nothing.

Each bridged place puts √½ of its identity in its own place column and √½ in
its organ's column. Every place keeps unit norm, so within-series costs and
the balance principle are unaffected, and only the bridges are cheaper:
t↔ṭ and k↔c cost 0.601, n↔ṇ, ṅ↔ñ and g↔j 0.437, l↔ḷ 0.322, while k↔p, t↔p,
c↔ṭ, k↔t and c↔t keep the full place-change cost of 0.889. No other
adjacency in the tract is assumed: guttural is exactly as far from dental as
from labial. The two bridges are one principle applied wherever the
tradition assigns a shared organ, not two parameters.

They are also the two place confusions transmission attests. Counted
positionally over the 3,006 equal-length pairs of DPD's `var_phonetic`
(where length forces the alignment and no cost is consulted), 90.1% of the
place substitutions between simple consonants share an organ: 80.3% the
tip, 9.9% the body (`eval/karana_bridges.py`). The pairs come from DPD's
own rules, so this is agreement with DPD, not independent evidence; Oberlies
documents t~ṭ (*Pali* §14.5) and kh~ch (§18.2) independently.

### Why Z₃ takes two dimensions

A cyclic group of order 3 is represented faithfully as a 120° rotation in
the plane, and with it ⊗ is arithmetic on vectors rather than a table:

```
compose(u, v):
    place     →  union            (componentwise max)
    voicing   →  maximum          (the OR semilattice)
    modifier  →  sum of angles    (complex multiplication)
```

Composing then embedding equals embedding then composing:
`test_embed.py::test_homomorphism`, over all 36 pairs of `A`. Encoding the
modifier as a scalar (−1, 0, +1) would make aspirate and nasal collinear
with the unmarked value and maximally distant from each other; in the plane
the three marks are equidistant, none lying between the other two.

### Faithfulness versus similarity: ρ*

The rotation places ε, + and − at cosine −0.5 from each other, while two
distinct places are orthogonal (cosine 0). On the raw vector, differing in
modifier therefore costs more than differing in place: `k` is closer to `p`
(cosine 0.5) than to `kh` (0.25). The raw vector is faithful to the algebra
and is not directly an articulatory metric.

`cosine(u, w, modifier_weight=ρ)` scales dims 6–7 for measuring only:

```
cosine(k, kh)  =  (1 − ρ²/2) / (1 + ρ²)
cosine(k, p)   =       ρ²    / (1 + ρ²)
```

They cross at ρ = √(2/3) ≈ 0.816. The weight the metric uses,
`NEUTRAL_MODIFIER_WEIGHT` = ρ* ≈ 0.4580, is derived by bisection from the
**balance principle**: aspirating (k→kh) costs exactly as much as voicing
(k→g). ρ* < √(2/3), so the series group, and ρ* recomputes itself if the
layout changes. `compose_vec` always takes the unweighted vector: the weight
is for measuring, not for composing.

### Why an angle and not a weighted sum

The alternative to the angular distance is Σᵢ wᵢ·|xᵢ − yᵢ| over the
embedding (`distance.weighted_cost`, experimental). A weighted L1 with
non-negative weights is a metric and takes the same calibration — its
modifier weight, 0.4226, comes from the same balance principle. (The general
Σᵢ |xᵢcᵢ − yᵢdᵢ| with cᵢ ≠ dᵢ is asymmetric and loses identity; only c = d
is a candidate.) Calibrated, it wins 26 of the 30 battery triples (§11),
with 4 ties, against the angular cost's 30.

The ties are the diagnosis: the L1 sum prices a↔ā, k↔kh and k↔g identically
(0.128), where the angle separates them (0.333 and 0.470). An angle divides
by the vectors' norms, so the same displacement counts for more on a lightly
specified segment than on a heavily specified one — phonological content
the L1 sum cannot see. Its scale also sits far below the indels: 0.4% of
letter pairs reach the 1.0 cap against the angular cost's 22.8%, so
deletion plus insertion is almost never competitive.
`test_distance.py::TestWeightedCost`.

## 5. Representation: IAST

The native scripts of Pāli (Devanāgarī, Sinhala, Burmese, Thai, Khmer…) are
abugidas: their unit is the akṣara, a consonant with an inherent `a`, vowels
as diacritics, a virāma to suppress the vowel. IAST is a flat phonemic
representation — one grapheme to one phoneme, no inherent vowel — and the
whole system works over it. `iast.py` absorbs its two complications:

- **Aspirated digraphs** (kh gh ch jh ṭh ḍh th dh ph bh) are two characters
  and one phoneme: tokenisation is longest-match. Word-internally, stop + h
  is always the aspirate in Pāli.
- **Unicode**: NFC normalisation (ṃ as U+1E43 ≡ m + U+0323), the variant ṁ
  (U+1E41) canonicalised to ṃ, lowercase; the compound hyphen and the elision
  apostrophe are dropped.

The diacritics exclusive to Sanskrit (ṛ ṝ ṣ ś) are rejected by strict
tokenisation with their own error: Pāli ḷ is the retroflex lateral, and a
text with ṛ, ṣ or ś is not Pāli. The tokeniser validates graphemes, not
phonotactics — `dharma` tokenises, and rejecting it is §8's job. ḷh (ruḷha,
aḷhaka) is the cluster ḷ + h, as in the traditional 41-sound alphabet.

`lenient=True` turns characters outside the inventory into opaque tokens
(§9.6) instead of raising, and `diagnose` reports them.

API: `normalize`, `tokenize`, `transcribe` (word → phonemes), `vectors`
(word → embeddings).

## 6. Sandhi

### 6.1 Assimilation of the niggahīta (`sandhi.assimilate_word`)

Each ṃ is resolved against what follows (Kaccāyana, «vagge vaggantaṃ»):

- **ṃ + stop → that series' nasal**: saṃgha → saṅgha, saṃjāta → sañjāta,
  saṃṭhāna → saṇṭhāna, saṃtāna → santāna, saṃbodhi → sambodhi. Mechanism:
  the meet of §3.
- **ṃ + y → ññ**: saṃyutta → saññutta, saṃyojana → saññojana. A rule of its
  own (y is not a stop): nasalise and geminate.
- **Otherwise** (vowel, s h r l v, word-final) ṃ stays: the unresolved glut.

Assimilation is optional in manuscript orthography (saṃgha and saṅgha
coexist); the function produces the canonical assimilated form.

### 6.2 Vowel sandhi (`sandhi.sandhi_join`)

The join of §3 across a word boundary:

- a/ā + i/ī → e ({G}∪{P}), a/ā + u/ū → o ({G}∪{L}): upa+ikkhā → upekkhā,
  mahā+udadhi → mahodadhi;
- a/ā + e/o → e/o (the union already is the compound): ca+eva → ceva;
- same places → the long vowel: tatra+ayaṃ → tatrāyaṃ, gāmī+iva → gāmīva.

Only the guṇa pattern (first vowel a/ā) and vowels of the same place join.
i+a, u+i and the like proceed by glide formation or elision (aggi+agāraṃ →
aggyagāraṃ), which are not the join and are left untouched.

### 6.3 Contraction (`sandhi.contract_word`)

`aya` → `e` is {guttural} ∪ {palatal} and `ava` → `o` is {guttural} ∪
{labial}: the join of §3 inside the word. It is attested and productive —
abhibhavati ~ abhibhoti, anavakāsa ~ anokāsa, palāyati ~ paleti — and
`ayi` → `e` covers the causative absolutives (bhāvayitvā ~ bhāvetvā).

Exactly three rules. Each candidate was measured alone against DPD's
`var_phonetic` (5,002 pairs; `eval/variant_curve.py`; agreement with DPD,
not accuracy), from a baseline of 63.55% at θ = ONE_MOVE:

| rule | Δagreement at ONE_MOVE | Δvolume | |
|---|---|---|---|
| `aya` → `e` | +6.74 | +2.8% | kept |
| `ava` → `o` | +1.72 | −1.4% | kept |
| `ayi` → `e` | +0.86 | ~0 | kept |
| `āya` → `e` | −0.20 | +2.8% | |
| `āva` → `o` | −0.26 | +0.5% | |
| `āyi` → `e` | −0.08 | ~0 | |
| `ayu` → `e` | −0.10 | ~0 | |
| `avi` → `o` | −0.46 | ~0 | |
| `īya` → `e` | −2.62 | +2.8% | |
| `iya` → `e` | −3.06 | +3.7% | |

**Contraction is a normalisation, not an edit operation.** As a 3:1
alignment transition inside `distance` it breaks the triangle inequality:
monotone alignments are not closed under path composition once a transition
consumes three tokens on one side (d(abhibhavati, kave) = 4.673 against
2.007 + 2.469 = 4.476 through bhavati). So it is applied before measuring:

    distance(contract_word(w1), contract_word(w2))

`lexicon.phonological_form` applies both steps, assimilation then
contraction — phonology first, metric second.

## 7. The alphabet (akkharā)

`alphabet.py` defines the 41 sounds in traditional recitation order,
separating structure from convention:

- **Vowels — derived**: simple before compound, by place (back to front),
  short before long ⇒ a ā i ī u ū e o.
- **Vagga (25) — a theorem**: the recitation order k kh g gh ṅ c ch j jh ñ …
  is exactly the lexicographic order of Place × A under the key
  (place, base, mod): (0,ε) < (0,+) < (1,ε) < (1,+) < (1,−).
  `test_the_vagga_is_the_lexicographic_product`.
- **Avagga — declared convention**: y r l v s h ḷ follows no structural key
  and is stored as inherited order.
- **ṃ** last.

Alphabetical ordering of words (`sort_key`, `sort_words`) works over
tokenised graphemes, so an aspirated digraph is one letter (khaṇa > kaṇṇa;
dhamma < buddha because dh precedes b).

## 8. Phonotactics: what could be Pāli

`phonotactics.is_possible` defines P ⊂ Σ*: the strings that are
phonotactically possible as a Pāli word. It is what knows that dharma is not
Pāli although all its graphemes are. P is regular (a linear scan).

Word rules: at least one vowel; ends in a vowel or ṃ; ṃ only after a vowel
(ṃ + stop is legal: the unassimilated spelling saṃgha coexists with saṅgha);
an onset of at most one consonant, or C+y/r/v (dve, brāhmaṇa), s+nasal
(sneha), or the aspirated nasals nh/mh, which are unitary phonemes (nhāru,
nhāyati, mhita; Oberlies, *Pali* §15.1); 0–2 consonants between vowels, or
3 when a valid pair is followed by a liquid that also pairs with its second
member (indriya = n·d·r, lakkhyā = k·kh·y); ṅ never alone and never initial.

Internal clusters. The structural core is derived from the system:

- a geminate (identity), and the aspirated geminate C + (C ⊗ 0+), a
  composition in `A`;
- nasal + homorganic stop: the non-empty meet of places (§3).

Declared residual families, stored like the avagga: sonorant+h (pañha,
taṇhā, mayhaṃ, jivhā), h+m (brahmā), s+nasal (tasmā), C+y/r/v/l (sakya,
tatra, katvā, plavati), and s+t word-internally (bhastā, ghasta, viddhasta;
Oberlies §16 rem. (a)). st opens no word (thana, thūpa). P is wider than the
lexicon by design: rejecting Sanskrit is the strict tokeniser's job (§5),
not this predicate's.

On the lemmas of DPD (`eval/phonotactics_calibration.py --dpd`), 99.03% of
single-word lemmas are accepted, and 99.91% of those with a valid ending.
The rejected ones with a valid ending are typos (alkkhika), non-standard
nasal spellings (ahaṇkāra), suffixes and letter names entered as headwords
(ssa, ṅa), and Sanskrit forms whose Pāli counterpart exists (ratna for
ratana, padma for paduma).

`phonotactics.pseudoword` inverts the predicate into a generator of legal
pseudo-Pāli, used by the open-vocabulary evaluation (§11).

### 8.1 Formability (`morphology.py`)

P answers whether a string could be a Pāli word as a sequence; formability
asks whether it could be **formed**. A form is built as the grammarians
build it, dhātu → aṅga → vibhatti (root → base → ending): pac → paca → -ti =
pacati; pac → pacana → -assa = pacanassa. The criterion is optional —
`pseudoword` keeps its role — and stronger: every output passes
`is_possible`, so F ⊂ P.

The present bases are **declared, not derived**: guṇa, vuddhi and the class
infixes admit no small honest rule set, so `ROOTS` records each root's
attested base with its gaṇa (43 roots). Everything downstream is derived —
the kita bases, the junction and the phonotactic filter. The junction rules
depend on the shape of the boundary, not on the identity of the morphemes:

- **hiatus** — the base loses its vowel (paca + antu → pacantu), except
  the guṇa bases in -e/-o, which survive at the ending's expense (karo +
  antu → karontu) unless the ending would vanish (karo + e → kare);
- **lengthening** before the first-person endings and imperative -hi
  (pacāmi, pacāhi);
- **shortening** of a long final vowel before a cluster (jānā + nti →
  jānanti);
- **retroflexion** (nati) — intervocalic n → ṇ after r, blocked by an
  intervening coronal: karaṇa, caraṇa, but rundhana. The blocking class is
  read off the inventory's places, the same tongue-tip set as the coronal
  dimension of §4.

The generator builds 4,429 forms over 3,920 distinct strings; the 509
collisions are real syncretism (pacanaṃ is accusative singular masculine
and nominative singular neuter). None of the 4,429 leaves P: the junction
rules are closed with respect to the phonotactics. Of them, 47.9% are
attested in DPD (lemmas ∪ inflections), though no dictionary is consulted
in their construction.

`is_formable` applies the criterion to strings the generator did not build
(`analyse` splits a word into aṅga + vibhatti). Over 20,000 `pseudoword`
samples:

| criterion | survives | reduction |
|---|---|---|
| any known ending over a syllabic base | 36.4% | 63.6% |
| the ending is ≥ 2 graphemes | 8.9% | **91.1%** |
| the form lies in the generable space | 0 of 20,000 | 100% |

The first row is permissive because the one-letter endings -e, -o, -ā
match any vowel-final word; the third is a property of this root list, not
of the criterion. The middle row is the answer: about nine in ten
phonotactically legal strings are not formable words.

Scope: word formation, not the history of words. Consonant loss (kar + ta →
kata) and the assimilations that reshaped inherited clusters are not
modelled, so the agent suffix -tar (kattā) and the -ti abstracts (gati) are
left out rather than approximated, and a form whose junction would leave P
is dropped, not repaired.

## 9. The distance (`distance.py`)

### 9.1 The algebraic cost

`algebraic_cost(x, y)` over `A` is the word metric of the group generated by
⊗: [bases differ] + [modifiers differ] ∈ {0, 1, 2}. Any modifier change is
one move, because + ⊗ + = −.

### 9.2 The cost between phonemes

`cost(g1, g2)` is the truncated angular distance between the embeddings at
ρ*:

    cost = min(1, arccos(cosine at ρ*) / (π/2))

Because the embedding is the homomorphic image of ⊗, ρ* balances the
elementary moves and arccos is monotone, the geometry is the algebra:
cost(k, kh) = cost(k, g) exactly, and the cost grows monotonically with the
algebraic cost within each series (tested). It also sees what `A` does not
reach: places, the karaṇa bridges and vowel length.

The scale, by elementary move:

| move | cost |
|---|---|
| l↔ḷ (karaṇa bridge, laterals) | 0.322 |
| vowel length (a↔ā) | 0.333 |
| n↔ṇ, ṅ↔ñ, g↔j (karaṇa bridge) | 0.437 |
| one algebra move: aspiration (k↔kh) or voicing (k↔g) | 0.470 |
| consonant length (tt↔t) | 0.470 |
| t↔ṭ, k↔c (karaṇa bridge) | 0.601 |
| epenthetic insertion or deletion (§9.3) | 0.627 |
| two algebra moves (k↔gh) | 0.631 |
| ṅ↔ṃ (the glut) | 0.740 |
| change of place without a shared organ (k↔p) | 0.889 |
| unrelated | 1.0 |

`ONE_MOVE` is the maximum over the elementary moves of attested variation
(an epenthetic indel, one algebra move, consonant length, vowel length):
0.627.

**Linear in the angle, not re-warped.** A concave warp (log, sqrt) would
preserve the metric, so the choice needs an argument. Read the edit distance
as a noisy channel — the reason costs sum at all: independent operations
corrupt a word, an operation costs −log P(operation), and a path's cost is
the corruption's negative log-likelihood. Exponential decay of
confusability then implies a linear cost, and power-law decay a logarithmic
one. Binning real search candidates by distance and taking the fraction
that are annotated variants, the decay over the operating range is
exponential: R² 0.974 for the identity against 0.932 for log at d ≤ 1.5,
and the identity wins at every cut up to 2.5; log overtakes it only past
d ≈ 3, where P ≈ 0.0001 (`eval/noisy_channel.py`). This fixes the right
transformation of this geometry; it does not validate the geometry, which
rests on §4.

**The cap.** min(1, ·) flattens 80 of the 820 letter pairs, whose raw values
lie in 1.041–1.055, a sliver beyond orthogonal. None of them shares a place,
and removing the cap changes no decision in the battery: beyond-orthogonal
values are an artefact of the 120° modifier representation, not
phonological signal. `test_distance.py::test_the_cap_only_flattens_unrelated_pairs`.

### 9.3 Insertion and deletion

A consonant's insertion or deletion costs 1. The **epenthetic class** —
the vowels, y, v and ṃ, the segments transmission inserts and drops
(svarabhakti, v-prothesis, aphaeresis, final-ṃ loss) — costs
`INDEL_WEIGHT` ≈ 0.627, derived rather than tuned: it is the smallest value
the triangle inequality on Σ ∪ {ε} admits. For every full-price symbol c and
epenthetic g, indel(c) ≤ cost(c, g) + indel(g), so indel(g) ≥ 1 − min
cost(class, non-class); and for g₁, g₂ in the class, cost(g₁, g₂) ≤
indel(g₁) + indel(g₂), so indel ≥ max in-class cost / 2. `INDEL_WEIGHT` is
the larger of the two bounds, computed at import over the alphabet and the
foreign phonemes.

### 9.4 Heavy units

Pāli geminates are long consonants — the same phonological parameter as
vowel length, which the metrical tradition prices alike. Each word is
segmented **once**, left to right, into letters and **heavy units**: the
geminates (tt, tth) and the homorganic nasal+stop clusters (nt, ṅkh — the
non-empty meet of §8; ṃ carries all five places, so ṃ + any stop is a unit
too). 41 graphemes, 82 units and the 3 foreign phonemes make 126 tokens.

A token is a triple (first half, second half, weight): a letter X is
(X, X, light). Two tokens cost

    cost(u, v) = max(cost(u₁, v₁), cost(u₂, v₂), |w(u) − w(v)|)

where w(u) is the angular cost of making u's second half long (the length
dimension). Consequences: a geminate counts once (kk~gg = k~g = 0.470); a
cluster differs from a geminate by the half that differs (tt~nt = t~n =
0.631, so citta~cinta is 0.631); a change inside a cluster costs what it
costs alone (nt~nd = t~d = 0.470); consonant length costs one move
(attha~atha = 0.470); costs between letters are unchanged. A unit's
insertion or deletion is the cheapest route through a single token (tt
through v: 1.327).

The segmentation is per word, not per comparison, and that is what keeps
the metric (§9.5). Letting each comparison decide whether a doubled pair is
one long consonant or two letters — alignment transitions of 2:1 and 2:2 —
breaks the triangle inequality: a middle word can be read as a unit in one
leg and as two letters in the other (`eval/triangle_geminates.py` measures
this and the repairs that keep the per-comparison choice; none works).

What the units cost: a unit cannot align letter by letter with a cluster of
two articulations, so Sanskrit-shaped correspondences sit further away
(tatra~tattha 1.470), and a one-letter change that leaves half a geminate —
a string Pāli does not write — costs a broken unit.

### 9.5 The word distance and the metric guarantee

`distance(w1, w2)` is the weighted edit distance over the segmented words:
substitution at `cost`, insertion and deletion at the token's indel.

**`distance` is a true metric** — identity, symmetry and the triangle
inequality — over all words, the empty one included. The angular distance is
the spherical geodesic and min(1, ·) preserves the triangle inequality; the
max of metrics on a product is a metric, so the cost by halves is one over
all 126 tokens; and weighted edit distance over a single sequence per word,
with a metric substitution cost and indels satisfying indel(g) ≤ cost(g, h)
+ indel(h) and cost(g, h) ≤ indel(g) + indel(h), is a metric over sequences
(Wagner–Fischer). All three token-level conditions are verified
exhaustively: 2,000,376 triples for the cost, 15,876 pairs for the indel
conditions (`tests/test_distance.py`, `tests/c/test_abugida.c`). Structures
built on the metric — the BK-tree of `index.py` — rely on this.

`distance` is not bounded by `levenshtein` (the same tokenisation with every
change costing 1): a unit against two letters can cost more than one edit
(tatra~tattha 1.470).

Against the DPD lexicon, the probe *dhamma*: Levenshtein ties camma, amma,
dhammā and damma at distance 1; the phonological distance grades them —
dhammā 0.333 < damma 0.344 < dhammī 0.487 < vamma 0.530.

`alignment(w1, w2)` returns the optimal edit script, whose costs sum
exactly to `distance` (tested), so the pair (scalar, script) loses nothing;
`lexicon.edit_tag` writes the script as a label ("t↔ṭ +a").

### 9.6 Lenient input and foreign phonemes

With `lenient=True`, a character outside the inventory becomes an opaque
token: cost 1 against everything, 0 against itself, which preserves the
metric. The Sanskrit phonemes ś, ṣ, ṛ (`phonology.FOREIGN`) are the
exception: in lenient mode they carry real phonology (ṣ↔s 0.460 through the
coronal bridge, ś↔s 0.667, ṛ↔a 0.608), so Sanskrit input is priced rather
than treated as noise. They stay outside `INVENTORY`: strict tokenisation
and `is_possible` keep rejecting them. Lenient mode restores comparability
on noisy input, not discrimination — a typo has no phonology.

### 9.7 Limits

- **The glut has a price.** ṃ's five places give it a large norm, so
  saṅgha~saṃgha is 0.740 — less than Levenshtein, more than a spelling
  variant warrants. To collate spellings, compare the resolved forms
  (`assimilate_word`, or `phonological_form`), which turns the pair into
  one word.
- **Sound laws are not distance.** Sanskrit → Pāli correspondences are
  systematic, correlated changes (rm → mm is assimilation plus gemination),
  while edit distance assumes independent edits. The metric brings the
  reflex into the immediate neighbourhood; picking it out would need a
  transducer of historical sound laws, which is outside this library.
- **Typing errors are outside the envelope.** A keyboard typo has no
  phonology, digraph-straddling typos amplify at token level, and there is
  no transposition operation. Over a mix of typos and phonological
  confusions, accuracy is linear in the typo share p, with a single
  crossover against character-level matching (`eval/decision_curve.py`;
  `eval/profile_error_mix.py` measures p from a query log).
  `docs/comparator.md` documents the hybrid (a character-level prefilter,
  then a phonological re-rank).
- It compares words, not sentences.

## 10. Open theoretical points

- **Totality produces equations with no phonological content.** `+⊗+ = −`
  and `1−⊙1− = 1+` follow from totality and associativity, not from Pāli.
  The faithful alternative is a partial operation with far less structure.
- **⊙ is canonical but only half-motivated.** It is the only componentwise
  multiplication; no Pāli process instantiates "coincidence".
- **`0−` is overloaded**: a column of the product Place × A and a single
  phoneme at once. The multi-hot place set accommodates it.
- **The relation between `h` (a phoneme) and `+` (a modifier)** is not
  expressed.

## 11. Evaluation

What each instrument measures, and its current result. The scripts are in
`eval/`; those marked DPD need the Digital Pāḷi Dictionary database, and
figures against DPD's `var_phonetic` are **agreement with DPD**, not
accuracy — those pairs are produced by DPD's own phonetic rules (README,
"Agreement with DPD is not accuracy").

**Discrimination battery** (`tests/test_battery.py`, no dictionary). Thirty
triples (base, nearer, farther) where linguistics fixes the answer —
vowel length, aspiration, voicing, place, nasals, clusters and gemination,
Sanskrit reflexes, morphology — scored on a strict ordering (a tie fails).

| measure | triples won | distinct values over 190 pairs |
|---|---|---|
| phonological | **30 / 30** | 167 |
| levenshtein | 8 / 30 | 7 |

Levenshtein wins exactly the cases where the edit count differs; wherever
both alternatives are one edit away — the normal case for manuscript
variants — it ties.

**Hard battery** (`eval/hard_battery.py`). 3,000 triples where Levenshtein
ties by construction, harvested from `var_phonetic` pairs: 50.9%
[49.1, 52.7] raw, 68.1% [66.4, 69.7] through `phonological_form`.

**Open vocabulary** (`eval/open_vocabulary.py`; DPD only as a negative
control). Base words are pseudo-Pāli from `pseudoword`, certified outside
DPD; for each, a scribal variant (a documented manuscript confusion) and an
arbitrary one (same number of edits, an unrelated grapheme). Which is
closer?

| edits | phonological | levenshtein |
|---|---|---|
| 1 | **88.0%** | 50.4% |
| 2 | **92.4%** | 50.5% |
| 3 | **96.2%** | 50.5% |

Levenshtein sits at chance by construction. Part of the residual is the
generator writing half-geminates that Pāli does not spell (§9.4); on the
trials where both variants are possible Pāli the figures are 92.2 / 97.9 /
100% (`eval/triangle_geminates.py`).

**Retrieval** (`eval/compare_levenshtein.py`, DPD, 75,733 lemmas; ties
credited 1/k):

| task | n | phonological | levenshtein |
|---|---|---|---|
| scribal corruption → original | 400 | **95.2%** | 81.4% |
| sandhi ṃC → attested assimilated form | 40 | **87.5%** | 83.8% |
| Sanskrit → Pāli reflex | 12 | **58.3%** | 36.1% |

Only the first row has the sample to rank calibrations (±11.6 points at
n = 40, ±24.4 at n = 12). Through `assimilate_word` the sandhi row is 100%
for both measures. The scribal failures land closer to another real word
(pāṭu ← pātu, with paṭu one lengthening away): the corruption destroyed the
information, and recovering it would need context, not finer phonology.

**Grammars.** Oberlies, *Pali* (`eval/oberlies.py`; 740 Sanskrit → Pāli
pairs and 134 Pāli doublets) and Geiger, *A Pāli Grammar* (`eval/geiger.py`,
DPD; 157 tadbhava pairs, 24 doublets), read from local case files that are
not distributed (`NOTICE`). Within two moves (2 × ONE_MOVE): Sanskrit forms
of their Pāli reflex 31.6% (Oberlies) and 35.0% (Geiger); Oberlies' doublets
91.8%. Ranking the whole DPD lexicon, expected top-1 for the Geiger tadbhava
pairs: 24.5% against 22.4% for character-level matching (n = 131); for the
doublets 25.0% against 25.0%.

**DPD's hand-written phonetic rules** (`eval/phonetic_rules.py`, DPD). DPD
generates variant candidates with 66 substitution rules. Rule level: median
distance 0.608 for the rules against 0.782 for other letter pairs, AUC
0.831; the expensive tail is morphological correspondences (e↔aya 1.65,
o↔ava, ṭhā↔ṭhaha), which §6.3 handles as normalisation. Database level: of
3,784 headword pairs one rule application connects, the metric reaches 100%
at θ = the maximum rule cost and 85.7% at the rule median, and it prices
low a family the rules do not contain — the aspiration pairs (g↔gh, j↔jh,
b↔bh) — as candidates for review, not automatic truths.

**Agreement with DPD and Levenshtein at matched volume**
(`eval/head_to_head.py`, `eval/variant_curve.py`, DPD; 5,143 pairs). At
θ = ONE_MOVE the metric generates 62.6% of `var_phonetic`, and the heavy
units are worth 14.4 points of it (`eval/ablate_geminates.py`). With the
same pipeline available to both measures and at equal candidate volume, the
metric leads Levenshtein by 5.6 and 7.4 points at 1 and 2 candidates per
lemma, ties at 4 and trails by a point at 8.
