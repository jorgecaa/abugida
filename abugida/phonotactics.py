"""Executable phonotactics: which strings of Σ* could be Pāli.

See SPEC.md §8. Defines P = {phonotactically possible strings}, with
L ⊂ P ⊂ Σ*. `tokenize` validates graphemes; this validates SEQUENCES — it is
the layer that knows dharma is not Pāli even though all its graphemes are.

Word-level rules:
  1. At least one vowel; ends in a vowel or ṃ.
  2. ṃ only immediately after a vowel.
  3. Onset: at most one consonant, or a permitted initial cluster (C+y/r/v:
     dve, tvaṃ, brāhmaṇa…; s+nasal: sneha; nh/mh: nhāru, mhita).
  4. Between vowels: 0, 1 or 2 consonants; two-consonant clusters must be
     valid.
  5. ṅ never appears alone between vowels: only in a homorganic cluster
     (aṅga, saṅkhāra).

Valid internal clusters — STRUCTURAL core (derived from the system):
  a. geminate:            C + C                      (identity)
  b. aspirated geminate:  C + (C ⊗ 0+)               (composition in A: kkh,
                          ggh, cch, jjh, ṭṭh, ḍḍh, tth, ddh, pph, bbh)
  c. nasal + homorganic stop: non-empty meet of places in the lattice
                          (ṅk ṅkh ṅg ṅgh, ñc…, ṇṭ…, nt…, mp… — the same rule
                          as `assimilate`)

RESIDUAL families — declared convention, like the avagga ordering:
  d. sonorant + h:  ñh ṇh nh mh yh lh ḷh vh   (pañha, taṇhā, mayhaṃ, jivhā)
  e. h + m:         hm                        (brahmā)
  f. s + nasal/t:   sm sn st                  (tasmā, sneha, bhastā)
  g. C + y/r/v:     ky ty dy…, tr br…, tv sv… (sakya, tatra, katvā, disvā)

Everything else — rm, kṣ (which does not even tokenise), kt, rk… — falls
outside: these are exactly the clusters historical Pāli assimilated
(dharma → dhamma, karma → kamma). st is usually assimilated too (hasta →
hattha), but a few canonical words keep it (family f), so it is possible
word-internally; no word opens with it. P is a regular language: the predicate is
a linear scan.
"""

from __future__ import annotations

from typing import List, Optional

from .algebra import VOICELESS_ASPIRATED, compose
from .iast import tokenize
from .phonology import BY_GRAPHEME, phoneme

_VOWELS = frozenset("aāiīuūeo")

#: Consonants that may geminate (rr, hh, ḷḷ, ṃṃ do not occur).
_GEMINABLE = frozenset(
    ["k", "g", "c", "j", "ṭ", "ḍ", "t", "d", "p", "b",
     "ñ", "ṇ", "n", "m", "y", "l", "v", "s"]
)

#: Residual families (declared convention).
_SONORANT_H = frozenset(["ñ", "ṇ", "n", "m", "y", "l", "ḷ", "v"])
_S_NASAL = frozenset(["m", "n"])
#: y/r/v as a second consonant (sakya, tatra, katvā); l is marginal but real
#: (plavati).
_SECOND_LIQUID = frozenset(["y", "r", "v", "l"])

_NASALS = frozenset(["ṅ", "ñ", "ṇ", "n", "m"])

#: The aspirated nasals that may open a word (nhāru, mhita; Oberlies §15.1).
_INITIAL_ASPIRATED_NASALS = frozenset(["n", "m"])


def _is_vowel(t: str) -> bool:
    return t in _VOWELS


def _is_stop(t: str) -> bool:
    p = BY_GRAPHEME[t]
    return p.value is not None and t != "ṃ"


def _aspirate_of(t: str) -> Optional[str]:
    """The aspirated counterpart of an unaspirated stop, via ⊗ in A."""
    p = BY_GRAPHEME[t]
    if p.value is None or p.value.mod != 0:
        return None
    target = compose(p.value, VOICELESS_ASPIRATED)
    for g, other in BY_GRAPHEME.items():
        if other.value == target and other.places == p.places:
            return g
    return None


def _valid_cluster(c1: str, c2: str) -> bool:
    """Is c1+c2 a possible internal consonant cluster?"""
    # a. geminate
    if c1 == c2:
        return c1 in _GEMINABLE
    # b. aspirated geminate: c2 = c1 ⊗ 0+ (same series)
    if _is_stop(c1) and _aspirate_of(c1) == c2:
        return True
    # c. nasal + homorganic stop: non-empty meet in the lattice
    if c1 in _NASALS and _is_stop(c2):
        # this also covers nasal + series aspirate (ṅkh, nth, mbh…)
        return bool(phoneme(c1).places & phoneme(c2).places)
    # d. sonorant + h
    if c2 == "h" and c1 in _SONORANT_H:
        return True
    # e. h + m
    if c1 == "h" and c2 == "m":
        return True
    # f. s + nasal, and s + t: the sibilant clusters Pāli sometimes leaves
    # unassimilated (Oberlies, Pali §16 rem. (a), p. 102): asnāti, bhasma-,
    # and with st (vaṅka)ghasta- 'having swallowed the hook', bhasta- 'bag'
    # (Th 1151); also viddhasta-, anuddhasta-. st is word-internal only:
    # it is not added to the onsets, and the regular outcome stays tth
    # (hasta -> hattha), so this admits the exception without making it
    # the rule.
    if c1 == "s" and (c2 in _S_NASAL or c2 == "t"):
        return True
    # g. C + y/r/v (C can be neither ṃ nor the liquid itself)
    if c2 in _SECOND_LIQUID and c1 != "ṃ" and c1 != c2:
        return True
    return False


def _valid_onset(cluster: List[str]) -> bool:
    if len(cluster) == 1 and cluster[0] == "ṅ":
        return False  # ṅ exists only in a homorganic cluster, never initially
    if len(cluster) <= 1:
        return True
    if len(cluster) == 2:
        c1, c2 = cluster
        # Only C + y/r/v (dve, tvaṃ, brāhmaṇa, svākkhāta), s+nasal (sneha)
        # and the aspirated nasals nh/mh.
        if c2 in _SECOND_LIQUID and c1 not in ("ṃ", c2):
            return True
        if c1 == "s" and c2 in _S_NASAL:
            return True
        # nh and mh are unitary phonemes, aspirated nasals /Nh/, and so may
        # open a word: nhāru 'sinew', nhusā 'daughter-in-law', nhāyati
        # 'bathes', mhita 'smile' (Oberlies, Pali §15.1). The tokeniser
        # still reads them as two letters, so they are admitted here, as an
        # onset, and only these two: the other sonorant+h clusters of
        # family d (ñh ṇh yh lh ḷh vh) occur word-internally only, and no
        # word-initial example of them is attested.
        if c2 == "h" and c1 in _INITIAL_ASPIRATED_NASALS:
            return True
    return False


def is_possible(word: str) -> bool:
    """Could this string be a Pāli word, phonotactically?

    False both for illegal sequences (dharma, buddh) and for what does not
    even tokenise (kṛṣṇa) — without exception: the question "could this be
    Pāli?" always has an answer.
    """
    try:
        tokens = tokenize(word)
    except ValueError:
        return False
    if not tokens or not any(_is_vowel(t) for t in tokens):
        return False
    if not (_is_vowel(tokens[-1]) or tokens[-1] == "ṃ"):
        return False

    # ṃ only after a vowel.
    for i, t in enumerate(tokens):
        if t == "ṃ" and (i == 0 or not _is_vowel(tokens[i - 1])):
            return False

    # Split into consonant runs between vowels (ṃ, already validated, acts
    # as a boundary: whatever follows starts a syllable).
    run: List[str] = []
    seen_vowel = False
    for t in tokens:
        if _is_vowel(t) or t == "ṃ":
            if run:
                if not seen_vowel:
                    if not _valid_onset(run):
                        return False
                elif len(run) == 1:
                    if run[0] == "ṅ":  # ṅ never alone between vowels
                        return False
                elif len(run) == 2:
                    if not _valid_cluster(run[0], run[1]):
                        return False
                elif len(run) == 3:
                    # Triple cluster: a valid pair plus a liquid that also
                    # forms a pair with the second (indriya = n·d·r,
                    # lakkhyā = k·kh·y).
                    if not (
                        run[2] in _SECOND_LIQUID
                        and _valid_cluster(run[0], run[1])
                        and _valid_cluster(run[1], run[2])
                    ):
                        return False
                else:
                    return False
                run = []
            if _is_vowel(t):
                seen_vowel = True
        else:
            run.append(t)
    # tokens ends in a vowel or ṃ, so no run is left pending.
    return True


# --- Pseudo-Pāli generator -------------------------------------------------

_CONSONANTS = sorted(g for g in BY_GRAPHEME if g not in _VOWELS and g != "ṃ")
_VOWEL_LIST = sorted(_VOWELS)


def pseudoword(rng, syllables: Optional[int] = None) -> str:
    """Generate a pseudo-Pāli word: legal per `is_possible`, with no promise
    of existing in any dictionary.

    `rng` is a random.Random supplied by the caller (determinism stays under
    their control). Syllable shape (C)(C)V(ṃ), with internal clusters drawn
    from those `_valid_cluster` accepts; the final filter is `is_possible`,
    so the generator can never drift away from the phonotactics: whatever
    they reject, this does not produce.
    """
    while True:
        n = syllables or rng.randint(2, 4)
        tokens: List[str] = []
        for i in range(n):
            if i == 0:
                if rng.random() < 0.85:
                    tokens.append(rng.choice(_CONSONANTS))
            else:
                c = rng.choice(_CONSONANTS)
                if rng.random() < 0.35:
                    partners = [x for x in _CONSONANTS if _valid_cluster(x, c)]
                    if partners:
                        tokens.append(rng.choice(partners))
                tokens.append(c)
            tokens.append(rng.choice(_VOWEL_LIST))
            if rng.random() < (0.25 if i == n - 1 else 0.08):
                tokens.append("ṃ")
        word = "".join(tokens)
        if is_possible(word):
            return word
