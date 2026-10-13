"""The alphabet is a theorem where it can be, and a declared convention
elsewhere."""

from abugida.alphabet import (
    ALPHABET,
    AVAGGA,
    ORDERED_VOWELS,
    VAGGA,
    sort_key,
    sort_words,
)

#: The traditional recitation order, as the empirical datum the derivation
#: is checked against.
TRADITIONAL = (
    "a ā i ī u ū e o "
    "k kh g gh ṅ c ch j jh ñ ṭ ṭh ḍ ḍh ṇ t th d dh n p ph b bh m "
    "y r l v s h ḷ ṃ"
).split()


def test_the_alphabet_is_the_traditional_one():
    assert [p.grapheme for p in ALPHABET] == TRADITIONAL
    assert len(ALPHABET) == 41


def test_the_vowels_are_derived():
    """a ā i ī u ū e o: simple ones by place and length, compounds after."""
    assert [p.grapheme for p in ORDERED_VOWELS] == TRADITIONAL[:8]


def test_the_vagga_is_the_lexicographic_product():
    """The theorem: the recitation order k kh g gh ṅ c ch j jh ñ … is the
    lexicographic order of (place, base, mod) — the tradition recites the
    semiring Place × A in order."""
    assert [p.grapheme for p in VAGGA] == TRADITIONAL[8:33]


def test_the_avagga_is_convention():
    """y r l v s h ḷ is not derivable (by place, h would come first): it is
    declared a convention and checked to still be one."""
    assert [p.grapheme for p in AVAGGA] == TRADITIONAL[33:40]


# --- Alphabetical ordering of words ----------------------------------------


def test_sort_words():
    """dh precedes b (dental vagga before labial); s comes near the end."""
    assert sort_words(["saṅgha", "buddha", "kamma", "dhamma"]) == [
        "kamma",
        "dhamma",
        "buddha",
        "saṅgha",
    ]


def test_digraphs_are_one_letter():
    """kha sorts by kh (letter 10), not by k+h: khaṇa follows kaṇṇa."""
    assert sort_words(["khaṇa", "kaṇṇa"]) == ["kaṇṇa", "khaṇa"]
    assert sort_key("kha")[0] != sort_key("ka")[0]


def test_vowel_length_sorts():
    assert sort_words(["pāla", "pala"]) == ["pala", "pāla"]


def test_total_order_over_the_inventory():
    """Every grapheme has a unique index: the order is total."""
    indices = [sort_key(p.grapheme) for p in ALPHABET]
    assert sorted(indices) == indices
    assert len(set(indices)) == 41
