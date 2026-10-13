"""Phonemic inventory of Pāli, in terms of place (ṭhāna) and the algebra A.

See SPEC.md §3. Place assignments follow traditional grammar, including the
compound places: `e` is kaṇṭhatāluja, `o` kaṇṭhoṭṭhaja, `v` dantoṭṭhaja.
"""

from __future__ import annotations

from typing import FrozenSet, NamedTuple, Optional

from .algebra import (
    A,
    NASAL,
    NIGGAHITA,
    VOICED,
    VOICED_ASPIRATED,
    VOICELESS,
    VOICELESS_ASPIRATED,
)

# --- Places of articulation (ṭhāna), from back to front --------------------

GUTTURAL = "guttural"  # kaṇṭhaja
PALATAL = "palatal"  # tāluja
CEREBRAL = "cerebral"  # muddhaja
DENTAL = "dental"  # dantaja
LABIAL = "labial"  # oṭṭhaja

PLACES = (GUTTURAL, PALATAL, CEREBRAL, DENTAL, LABIAL)
PLACE_INDEX = {place: i for i, place in enumerate(PLACES)}


class Phoneme(NamedTuple):
    """A phoneme: roman grapheme, place(s), value in A, residual features."""

    grapheme: str
    places: FrozenSet[str]
    value: Optional[A]  # None for the segments A does not reach
    syllabic: bool = False
    long: bool = False
    continuant: bool = False
    lateral: bool = False
    #: Voicing for segments WITHOUT a value in A (vowels, semivowels, s, h).
    #: For algebraic ones it derives from value.base and this field is
    #: ignored. A phonological datum in the inventory, not an embedding
    #: decision.
    voiced: bool = False


def is_voiced(p: Phoneme) -> bool:
    """Voicing of any phoneme: value.base if algebraic, else the inventory's
    `voiced` field."""
    if p.value is not None:
        return p.value.base == 1
    return p.voiced


def _P(*names: str) -> FrozenSet[str]:
    return frozenset(names)


# --- Vowels ----------------------------------------------------------------
# Tradition gives them a place too; e and o are compound (two simultaneous
# places), the same phenomenon as the niggahīta under the glut reading, in
# miniature.

VOWELS = (
    Phoneme("a", _P(GUTTURAL), None, syllabic=True, voiced=True),
    Phoneme("ā", _P(GUTTURAL), None, syllabic=True, long=True, voiced=True),
    Phoneme("i", _P(PALATAL), None, syllabic=True, voiced=True),
    Phoneme("ī", _P(PALATAL), None, syllabic=True, long=True, voiced=True),
    Phoneme("u", _P(LABIAL), None, syllabic=True, voiced=True),
    Phoneme("ū", _P(LABIAL), None, syllabic=True, long=True, voiced=True),
    Phoneme(
        "e", _P(GUTTURAL, PALATAL), None, syllabic=True, long=True, voiced=True
    ),
    Phoneme(
        "o", _P(GUTTURAL, LABIAL), None, syllabic=True, long=True, voiced=True
    ),
)

# --- The five series of stops ----------------------------------------------
# The clean product Place × A: 5 places × 5 values = 25 phonemes.

_SERIES = {
    GUTTURAL: ("k", "kh", "g", "gh", "ṅ"),
    PALATAL: ("c", "ch", "j", "jh", "ñ"),
    CEREBRAL: ("ṭ", "ṭh", "ḍ", "ḍh", "ṇ"),
    DENTAL: ("t", "th", "d", "dh", "n"),
    LABIAL: ("p", "ph", "b", "bh", "m"),
}

_COLUMNS = (VOICELESS, VOICELESS_ASPIRATED, VOICED, VOICED_ASPIRATED, NASAL)

STOPS = tuple(
    Phoneme(grapheme, _P(place), value)
    for place in PLACES
    for grapheme, value in zip(_SERIES[place], _COLUMNS)
)

# --- Semivowels, sibilant, aspirate ----------------------------------------
# They have a traditional place, but their manner falls outside A: value=None.

OTHERS = (
    Phoneme("y", _P(PALATAL), None, continuant=True, voiced=True),
    Phoneme("r", _P(CEREBRAL), None, continuant=True, voiced=True),
    Phoneme("l", _P(DENTAL), None, continuant=True, lateral=True, voiced=True),
    Phoneme(
        "ḷ", _P(CEREBRAL), None, continuant=True, lateral=True, voiced=True
    ),
    Phoneme("v", _P(DENTAL, LABIAL), None, continuant=True, voiced=True),
    # s is the only voiceless segment outside A
    Phoneme("s", _P(DENTAL), None, continuant=True, voiced=False),
    Phoneme("h", _P(GUTTURAL), None, continuant=True, voiced=True),
)

# --- Niggahīta -------------------------------------------------------------

# Glut reading, a settled decision (SPEC §2): all places at once, with the
# context selecting one. The gap alternative (no place) was discarded.
NIGGAHITA_PHONEME = Phoneme("ṃ", frozenset(PLACES), NIGGAHITA)

INVENTORY = VOWELS + STOPS + OTHERS + (NIGGAHITA_PHONEME,)

# --- Foreign (Sanskrit) phonemes -------------------------------------------
# NOT part of the Pāli inventory: strict tokenisation and phonotactics keep
# rejecting them. They exist so that lenient comparison can price Sanskrit
# input with real phonology instead of opaque cost 1 — justified by the
# Geiger tadbhava data (157 scholar-attested Sanskrit→Pāli pairs). Pāli
# merged all three sibilants into s; ṛ is the vocalic r.

FOREIGN = {
    "ś": Phoneme("ś", _P(PALATAL), None, continuant=True, voiced=False),
    "ṣ": Phoneme("ṣ", _P(CEREBRAL), None, continuant=True, voiced=False),
    "ṛ": Phoneme("ṛ", _P(CEREBRAL), None, syllabic=True, continuant=True,
                 voiced=True),
}

BY_GRAPHEME = {p.grapheme: p for p in INVENTORY}


def phoneme(grapheme: str) -> Phoneme:
    try:
        return BY_GRAPHEME[grapheme]
    except KeyError:
        raise KeyError(f"not in the Pāli inventory: {grapheme!r}") from None


def assimilate(following: str) -> Phoneme:
    """Resolve the niggahīta before the consonant `following`.

    saṃ+gha → saṅgha, saṃ+jāta → sañjāta: ṃ takes the place of what follows
    and is realised as that series' nasal. Under the glut reading this is
    *selection* within an overdetermined set; under gap it would be *filling*
    a hole. Both give the same result here — they diverge only when there is
    nothing following.
    """
    following_phoneme = phoneme(following)
    if following_phoneme.value is None or following_phoneme is NIGGAHITA_PHONEME:
        # Only stops confer a place: they are the only ones with a simple
        # place and a series nasal to serve as target. Before a vowel, a
        # semivowel, or ṃ itself there is nothing to select, so ṃ stays.
        return NIGGAHITA_PHONEME
    places = following_phoneme.places & NIGGAHITA_PHONEME.places
    if len(places) != 1:
        return NIGGAHITA_PHONEME
    (place,) = places
    return next(p for p in STOPS if p.value == NASAL and place in p.places)
