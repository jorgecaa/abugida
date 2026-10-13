"""The Pāli alphabet (akkharā): derived from structure, not listed.

See SPEC.md §11. The 41 sounds in traditional recitation order:

    a ā i ī u ū e o | k kh g gh ṅ | c ch j jh ñ | ṭ ṭh ḍ ḍh ṇ |
    t th d dh n | p ph b bh m | y r l v s h ḷ | ṃ

Which part of the order is structure and which is convention, stated
honestly:

- **Vowels**: DERIVED. Simple before compound, by place (back to front),
  short before long: a ā i ī u ū e o falls out on its own.
- **The vagga block (25)**: DERIVED. The recitation order k kh g gh ṅ … is
  exactly the lexicographic order of the product Place × A under the key
  (place, base, mod): (0,ε) < (0,+) < (1,ε) < (1,+) < (1,−). The tradition
  recites the semiring in order. `test_alphabet` demonstrates it.
- **The rest (avagga)**: CONVENTION. y r l v s h ḷ follows no structural key
  (by place, h would come first); it is inherited order and is declared as
  such here rather than dressed up as a theorem.
- **ṃ**: last, as in recitation (…ha ḷa aṃ).

With the alphabet comes alphabetical ordering of words (`sort_key`,
`sort_words`), over tokenised graphemes — kh counts as one letter, not k+h.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .iast import tokenize
from .phonology import (
    NIGGAHITA_PHONEME,
    OTHERS,
    PLACE_INDEX,
    STOPS,
    VOWELS,
    Phoneme,
)


def _vowel_key(p: Phoneme) -> Tuple:
    return (
        len(p.places),  # simple before compound
        sorted(PLACE_INDEX[place] for place in p.places),  # back → front
        p.long,  # short before long
    )


def _stop_key(p: Phoneme) -> Tuple:
    (place,) = p.places
    # The product Place × A, lexicographically. That this reproduces the
    # recitation order k kh g gh ṅ … is this module's theorem.
    return (PLACE_INDEX[place], p.value.base, p.value.mod)


ORDERED_VOWELS = tuple(sorted(VOWELS, key=_vowel_key))
VAGGA = tuple(sorted(STOPS, key=_stop_key))

#: Inherited convention, with no structural key (see the module docstring).
_AVAGGA_ORDER = ("y", "r", "l", "v", "s", "h", "ḷ")
AVAGGA = tuple(
    next(p for p in OTHERS if p.grapheme == g) for g in _AVAGGA_ORDER
)

ALPHABET: Tuple[Phoneme, ...] = (
    ORDERED_VOWELS + VAGGA + AVAGGA + (NIGGAHITA_PHONEME,)
)

INDEX: Dict[str, int] = {p.grapheme: i for i, p in enumerate(ALPHABET)}


def sort_key(word: str) -> Tuple[int, ...]:
    """Pāli alphabetical sort key for an IAST word.

    Tokenises first: the aspirated digraphs are ONE letter of the alphabet
    (dhamma < buddha, because dh precedes b in the dental→labial sweep).
    """
    return tuple(INDEX[t] for t in tokenize(word))


def sort_words(words: Iterable[str]) -> List[str]:
    """Sort IAST words by traditional Pāli alphabetical order."""
    return sorted(words, key=sort_key)
