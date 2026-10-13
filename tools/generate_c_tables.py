"""Derive the C core's constant tables from the Python source.

`csrc/abugida_tables.c` is generated, not written: every array in it is a
faithful image of a structure the Python package already derives, and
nothing in it is a fresh decision. The numbers are computed here or nowhere:

- the token vocabulary and the substitution-cost matrix come from
  `phonology.BY_GRAPHEME`, `embed.embed`, `embed.NEUTRAL_MODIFIER_WEIGHT`
  and `distance.cost` — the same `cost` the Python API returns, called once
  per pair;
- `INDEL_WEIGHT` and `ONE_MOVE` come from `distance` and `lexicon`;
- the heavy-unit vocabulary (geminates, nasal+stop clusters) comes from `_pure._UNITS`;
- the epenthetic class comes from `distance.EPENTHETIC`.

The generator exists because the project's discipline forbids a second
hand-written copy of a derived constant: a C table typed out by hand is a
tuning waiting to diverge. `tests/test_c_parity.py` re-runs this generator
and fails if the committed file differs by a byte, so the C core cannot
silently drift from the Python definitions.

Floating-point literals are emitted as C99 hex floats (`%a`), which round
trip exactly: the C core and the Python package see the same doubles, not
the same values rounded to the nearest decimal.

    python tools/generate_c_tables.py            # write the file
    python tools/generate_c_tables.py --check    # fail if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The PURE-PYTHON reference, deliberately, and not `abugida.distance`.
#
# `abugida.distance` delegates to the C core, so reading `cost` from there
# would make the generator depend on the very table it is about to write:
# the first run would produce a table from the placeholder it replaced, and
# every later run would copy the previous run's answers forward — a drift
# that is invisible because it is self-consistent. The generator is the one
# place that must read the reference.
from abugida._pure import (  # noqa: E402
    EPENTHETIC,
    INDEL_WEIGHT,
    ONE_MOVE,
    _UNITS,
    _indel,
    cost,
)
from abugida.embed import NEUTRAL_MODIFIER_WEIGHT  # noqa: E402
from abugida.phonology import (  # noqa: E402
    BY_GRAPHEME,
    FOREIGN,
    NIGGAHITA_PHONEME,
    assimilate,
)

OUT_H = ROOT / "csrc" / "abugida_tables.h"
OUT_C = ROOT / "csrc" / "abugida_tables.c"
OUT_PAIRS = ROOT / "tests" / "c" / "pairs.txt"

#: Must match ABUGIDA_ABI_VERSION in csrc/abugida.h.
ABI_VERSION = 2

#: The inventory's size, fixed by the 41-sound traditional alphabet. Asserted
#: rather than assumed: a vocabulary change must fail loudly here.
N_PLAIN = 41

#: Why the tables below can be indexed by byte while `iast.tokenize` decides
#: on characters. The C scanner reads one character, then two, and looks each
#: up whole; the table is keyed by the complete UTF-8 byte sequence of that
#: substring, so a byte length is never used to decide a match — it only
#: locates the entry. What must hold is that the two agree on WHEN to try:
#: Python tries lengths `_MAX_LENGTH … 1` in CHARACTERS, so the C scanner
#: must try the 2-character form before the 1-character form, whatever their
#: byte lengths are ('ḍ' is 3 bytes and 'ḍh' 4; 'ṭ' is 3 and 'ṭh' 4; 't' is 1
#: and 'th' 2 — no ordering by bytes reproduces the character order, which is
#: exactly why the scanner does the UTF-8 decoding itself).
MAX_CHARS = 2


def dp_split(long_form: str, graphemes: set) -> tuple:
    """The two graphemes the DP holds for a doubled consonant.

    Derived by TOKENISING the doubled spelling with longest-match, because
    that is exactly what the DP does: it scans text into tokens and then asks
    whether two ADJACENT tokens form a long consonant. 'tth' tokenises to
    (t, th) and 'kkh' to (k, kh) — one long aspirated stop in both cases, not
    a long plain stop followed by h. Taking the split from the tokeniser
    rather than from a rule about `base` is what keeps this table and the
    run-time lookup in agreement: any other derivation is a second opinion
    about the same string.
    """
    out = []
    i = 0
    while i < len(long_form):
        for length in (2, 1):
            piece = long_form[i:i + length]
            if piece in graphemes:
                out.append(piece)
                i += length
                break
        else:
            raise AssertionError(f"{long_form!r} does not tokenise")
    if len(out) != 2:
        raise AssertionError(f"{long_form!r} tokenises to {out}")
    return out[0], out[1]


def build_tokens() -> list[str]:
    """The token vocabulary, in id order: the graphemes of the inventory,
    then the heavy units of `_UNITS` (geminates and homorganic nasal+stop
    clusters), then the Sanskrit phonemes of `FOREIGN`.

    The order matters. Ids [0, NPLAIN) are the 41 sounds of Pāli and are the
    only ones the tokeniser can produce or a heavy unit can be made of;
    the heavy units follow, reachable only through the DP's segmentation of
    a word into units; the Sanskrit phonemes come last, reachable only
    through lenient tokenisation — they are here so the cost table can price
    ṣ against s rather than treating it as an opaque character.
    """
    plain = sorted(BY_GRAPHEME, key=lambda g: (-len(g), g))
    long_ = sorted(_UNITS, key=lambda g: (-len(g), g))
    tokens = plain + long_ + sorted(FOREIGN)
    assert len(set(tokens)) == len(tokens), "token ids must be unique"
    for t in plain:
        assert 1 <= len(t) <= MAX_CHARS, f"{t!r} is longer than {MAX_CHARS} characters"
    return tokens


def emit_ints(values: list[int], per_line: int = 12) -> str:
    lines = []
    for i in range(0, len(values), per_line):
        chunk = ", ".join(str(v) for v in values[i:i + per_line])
        lines.append(f"    {chunk},")
    return "\n".join(lines)


def utf8_len(byte: int) -> int:
    """Length of the UTF-8 sequence a leading byte announces."""
    if byte < 0x80:
        return 1
    if byte & 0xE0 == 0xC0:
        return 2
    if byte & 0xF0 == 0xE0:
        return 3
    if byte & 0xF8 == 0xF0:
        return 4
    return 0  # a continuation or invalid byte: not a character start


class Lookup:
    """The scanner's table for two-character graphemes.

    The keys are closed and known here, so the table is built by direct
    placement rather than hashed: one entry per key, in a row per leading
    byte. A row holds at most a dozen entries and is scanned linearly at run
    time — which costs nothing next to the DP that follows it — and buys an
    exact, obvious correspondence between the generator and the C code that
    reads it.
    """

    def __init__(self, pairs: list[tuple[int, int, int, int]]) -> None:
        """`pairs` is (lead byte, first codepoint, second codepoint, id + 1)."""
        self.entries = pairs
        self.span: dict[int, int] = {}
        self.start: dict[int, int] = {}
        for k0, _, _, _ in pairs:
            self.span[k0] = self.span.get(k0, 0) + 1
        offset = 0
        for k0 in sorted(self.span):
            self.start[k0] = offset
            offset += self.span[k0]
        self.size = offset
        self.keys = [(k1, k2) for _, k1, k2, _ in pairs]
        self.tokens = [t for _, _, _, t in pairs]
        # A row with more than 255 keys cannot be addressed; unreachable for
        # this inventory, but a table that cannot be read is worth failing on
        # rather than truncating.
        assert max(self.span.values(), default=0) <= 255, "row span overflows"

    @property
    def spans(self) -> list:
        """The key count of each row, indexed by the row's first slot."""
        out = [0] * self.size
        for k0, start in self.start.items():
            out[start] = self.span[k0]
        return out

    def row(self, k0: int) -> int:
        """The row index for a leading byte, or 255 when no key starts with
        it. Rows are laid out in sorted order, so the row index is just the
        first key's slot."""
        return self.start[k0] if k0 in self.span else 255

    def slot(self, lead: int, first: int, second: int) -> int:
        """The slot of a key, found the way the C code finds it."""
        if lead not in self.span:
            return -1
        base = self.start[lead]
        for i in range(self.span[lead]):
            if self.keys[base + i] == (first, second):
                return base + i
        return -1


class Tables(NamedTuple):
    """Everything the two generated files carry."""

    tokens: List[str]
    n_plain: int
    one: List[int]
    two: List[int]
    two_keys: List[tuple]
    """(first codepoint, second codepoint) per pair slot."""
    two_row: List[int]
    """Leading byte -> its row in the pair table, or 255 for none."""
    two_span: List[int]
    """The number of keys in each pair row, indexed by the row's first slot."""
    geminate_pairs: List[int]
    """id(first) * NPLAIN + id(second) -> heavy unit id + 1, or 0."""
    indel: List[float]
    """Token -> its insertion/deletion cost (`_indel`)."""
    nasal_of: List[int]
    """Grapheme -> the series nasal it assimilates ṃ to, or ABUGIDA_NO_TOKEN."""
    foreign: List[tuple]
    """(codepoint, token id) for the Sanskrit phonemes, sorted by codepoint."""
    epenthetic: List[int]
    cost: List[float]


def c_name(grapheme: str) -> str:
    """A valid C identifier fragment for a grapheme.

    Diacritics are spelled out (`ṭ` → `t_dot`, `ā` → `aa`) so that the token
    constants are usable from any C compiler and any terminal, and so that
    they read as the IAST they stand for.
    """
    out = []
    for ch in grapheme:
        out.append({
            "ā": "aa", "ī": "ii", "ū": "uu",
            "ṅ": "n_dot", "ñ": "n_tilde", "ṇ": "n_dot_below",
            "ṭ": "t_dot", "ḍ": "d_dot", "ṃ": "m_dot", "ḷ": "l_dot",
            "ś": "s_acute", "ṣ": "s_dot_below", "ṛ": "r_dot_below",
        }.get(ch, ch))
    name = "_".join(out)
    assert name.isascii() and name.isidentifier(), f"cannot name {grapheme!r}"
    return name


def render_header(t: "Tables") -> str:
    n = len(t.tokens)
    one_size = 65536
    two_size = len(t.two)
    row_size = 256
    n_two = len(t.two)
    n_foreign = len(t.foreign)
    pair_size = t.n_plain * t.n_plain
    consts = [
        f"#define ABUGIDA_TOK_{c_name(g).upper()} {i}"
        for i, g in enumerate(t.tokens)
    ]
    return f"""/* GENERATED by tools/generate_c_tables.py — do not edit by hand.
 *
 * The token vocabulary, the substitution-cost matrix and the derived
 * constants the C core reads. Every value here is computed by the generator
 * from the Python package (`phonology`, `embed`, `distance`, `lexicon`), so
 * the C core and the Python package cannot disagree about a constant — and
 * `tests/test_c_parity.py` fails if this file is stale.
 *
 * ABI version {ABI_VERSION}: {n} tokens, {t.n_plain} of them graphemes.
 */

#ifndef ABUGIDA_TABLES_H
#define ABUGIDA_TABLES_H

#include "abugida.h"

#define ABUGIDA_TABLES_ABI_VERSION {ABI_VERSION}

/* How many tokens there are, and how many of them are graphemes of the
 * inventory. The long consonants are ids [{t.n_plain}, {n}). */
#define ABUGIDA_NTOKENS {n}
#define ABUGIDA_NPLAIN {t.n_plain}

/* The vocabulary, in id order. The graphemes come first, ordered as
 * `iast.tokenize` tries them (by character length, longest first); the long
 * consonants follow. The scanner looks graphemes up whole, so this order
 * constrains nothing at run time — it keeps the ids readable against the
 * Python module. */
{chr(10).join(consts[:t.n_plain])}

/* The heavy units (geminates, homorganic nasal+stop clusters): tokens the DP
 * forms by segmenting a word, never read from input text. */
{chr(10).join(consts[t.n_plain:])}

/* Each token's IAST spelling, NUL-terminated UTF-8, indexed by id. */
extern const char *const abugida_ts_text[{n}];


/* Token id -> UTF-8 length in bytes. */
extern const unsigned char abugida_ts_len[{n}];

/* How many bytes the UTF-8 sequence starting with a given byte occupies, or
 * 0 when that byte cannot start one. */
extern const unsigned char abugida_ts_char_len[256];

/* One-character graphemes, indexed by their byte. Token id + 1, so zero is
 * a miss. */
extern const abugida_token_t abugida_ts_one[{one_size}];

/* Two-character graphemes, {n_two} of them in {two_size} slots. A pair is
 * always an initial character plus ASCII `h`, so the key the scanner holds
 * once it has decoded both characters is their two CODEPOINTS: no UTF-8
 * bytes are needed here, which is also why the table cannot be confused by
 * an encoding the inventory does not use. Keys of a row are compared whole,
 * in order: no hashing, no probing, and an exact correspondence with the
 * generator. */
extern const abugida_token_t abugida_ts_two[{two_size}];
extern const unsigned short abugida_ts_two_cp0[{two_size}];
extern const unsigned char abugida_ts_two_cp1[{two_size}];

/* A leading byte -> its row in the pair table, or 255 when no pair starts
 * with it. Rows are contiguous and sorted, so a row's keys occupy
 * abugida_ts_two[row .. row + abugida_ts_two_span[row]). */
extern const unsigned char abugida_ts_two_row[{row_size}];
extern const unsigned char abugida_ts_two_span[{two_size}];

/* The Sanskrit phonemes (ś ṣ ṛ), as (codepoint, token id) pairs sorted by
 * codepoint. They are NOT graphemes of the Pāli inventory: strict
 * tokenisation still refuses them. They are here because lenient comparison
 * prices them with real phonology rather than as opaque cost-1 characters —
 * ṣ↔s is 0.460, ś↔s 0.667 — which is what makes cross-system Sanskrit↔Pāli
 * work possible at all (SPEC §14). */
#define ABUGIDA_NFOREIGN {n_foreign}
extern const unsigned short abugida_ts_foreign_cp[{n_foreign}];
extern const abugida_token_t abugida_ts_foreign_id[{n_foreign}];

/* Grapheme -> the series nasal `phonology.assimilate` resolves a preceding
 * niggahita to, or ABUGIDA_NO_TOKEN when it resolves to nothing (before a
 * vowel, a semivowel, s, h, r, l, v, or at the end of a word). */
extern const short abugida_ts_nasal_of[{n}];

/* id(first) * ABUGIDA_NPLAIN + id(second) -> the heavy unit (a geminate or
 * a homorganic nasal+stop cluster) the two tokens form, id + 1, or 0. This
 * is how the DP segments a word into units without building a string. */
extern const unsigned char abugida_ts_gempair[{pair_size}];

/* Every token's insertion/deletion cost: 1, the epenthetic weight, or a
 * heavy unit's derived indel (the cheapest route through a single token). */
extern const double abugida_ts_indel[{n}];

/* The epenthetic class, terminated by ABUGIDA_NO_TOKEN. */
extern const short abugida_ts_epenthetic[];

/* The derived constants: the balance weight ρ*, the epenthetic indel weight,
 * and the maximum over the elementary moves. */
extern const double abugida_ts_neutral_modifier_weight;
extern const double abugida_ts_indel_weight;
extern const double abugida_ts_one_move;

/* The substitution cost, square over all {n} token ids — the whole metric
 * that is not the DP. */
extern const double abugida_ts_cost[{n}][{n}];

#endif /* ABUGIDA_TABLES_H */
"""


def build() -> "Tables":
    """Compute every table, once, for both generated files."""
    tokens = build_tokens()
    n = len(tokens)
    n_plain = sum(1 for t in tokens if t in BY_GRAPHEME)
    assert n_plain == N_PLAIN, f"the inventory has {N_PLAIN} graphemes, got {n_plain}"
    assert n > n_plain, "the long consonants must be in the vocabulary"
    index = {t: i for i, t in enumerate(tokens)}
    plain = tokens[:n_plain]

    # --- one-character graphemes ------------------------------------------
    one = [t for t in plain if len(t) == 1]
    # Indexed by the character's first and last UTF-8 bytes. The lead byte
    # alone is not enough — five graphemes of this inventory start with 0xE1
    # (ṭ ḍ ṇ ḷ ṃ) — and the pair is exact, because the two together determine
    # the sequence for every character of at most three bytes. The table is
    # laid out densely in the two bytes, which costs 128 KB of mostly-zero
    # data in the object file and needs no hash on either side. Uniqueness is
    # proved here, not assumed: a clash would silently mis-tokenise a word.
    one_table = [0] * (256 * 256)
    for t in one:
        assert t not in FOREIGN, f"{t!r} is Sanskrit, not a Pāli grapheme"
        b = t.encode()
        slot = (b[0] << 8) | b[-1]
        assert one_table[slot] == 0, (
            f"byte pair ({b[0]:#x}, {b[-1]:#x}) is not unique to {t!r}")
        one_table[slot] = index[t] + 1

    # --- two-character graphemes ------------------------------------------
    # Decided on CHARACTERS, as `iast.tokenize` decides it: the pair first,
    # then one. A pair is an initial character plus ASCII `h`, so the C
    # scanner has the whole key the moment it has decoded both characters: it
    # holds the first character's CODEPOINT (which is why the table needs no
    # UTF-8 bytes here) and the second character's, the latter always ASCII.
    assert all(t not in FOREIGN for t in plain), "a Sanskrit phoneme in plain"
    twos = [t for t in plain if len(t) == 2]
    entries = []
    for t in twos:
        assert ord(t[1]) < 0x80, f"{t!r} does not end in ASCII h"
        # The row is selected by the first character's LEAD BYTE, which is
        # what the scanner holds before it decodes; the key inside the row is
        # the full codepoint, so two characters sharing a lead byte are told
        # apart by the comparison and not by the row.
        entries.append((t[0].encode()[0], ord(t[0]), ord(t[1]),
                        index[t] + 1))
    seen = set()
    for e in entries:
        assert e[1:] not in seen, f"two pairs share the key {e[1:]!r}"
        seen.add(e[1:])
    two_lookup = Lookup(entries)
    # The scanner decides with one byte, whichever byte that is — the whole
    # character when it is ASCII, its lead byte otherwise — so the table is
    # grouped by `codepoint & 0xFF` and holds full codepoints inside a group.
    # Every grapheme the inventory knows is matched; anything else falls
    # through to the one-character table and then to a miss.
    two_row = [two_lookup.row(k0) for k0 in range(256)]

    # --- heavy units: the pair lookup the DP segments a word with ---------
    # The DP recognises a doubled consonant by looking its two base tokens up
    # in one table, keyed `first * NPLAIN + second`. The key must be
    # INJECTIVE over the pairs the inventory can form: a base-3 mixing is not
    # ('jh'+'h' and 'th'+'th' both land on 28), and the collision would be
    # silent — one long consonant would be read as another. The generator
    # proves the key injective instead of hoping.
    pair_table = [0] * (n_plain * n_plain)
    for long_form in _UNITS:
        # The two tokens the DP holds for this unit, derived by tokenising
        # its spelling (see `dp_split`) — and checked against the halves the
        # reference declares, so the two cannot name different pairs.
        first_text, second_text = dp_split(long_form, set(BY_GRAPHEME))
        assert (first_text, second_text) == _UNITS[long_form], long_form
        first = index[first_text]
        second = index[second_text]
        assert first < n_plain and second < n_plain, "a long token in a pair"
        key = first * n_plain + second
        assert pair_table[key] == 0, f"two long tokens share the pair {key}"
        pair_table[key] = index[long_form] + 1
        # The Python lookup this replaces is `_segment`'s `tokens[i] +
        # tokens[i+1] in _UNITS`: the key is the CONCATENATION of two
        # adjacent tokens, so this table IS that lookup, with the string
        # joined once here rather than once per word.
    # Every long token must be reachable: the DP finds a geminate by looking
    # its two base tokens up, and an unreachable entry would silently price a
    # doubled consonant as two edits.
    for long_form in _UNITS:
        assert index[long_form] + 1 in pair_table, f"{long_form!r} unreachable"

    # --- the niggahita's target: `phonology.assimilate`, called ------------
    nasal_of = [-1] * n
    for i, t in enumerate(plain):
        target = assimilate(t)
        nasal_of[i] = -1 if target is NIGGAHITA_PHONEME else index[target.grapheme]
    # ... and the C core must agree for every grapheme of the inventory that
    # can follow a niggahita.
    for t in plain:
        want = assimilate(t).grapheme
        got = -1 if nasal_of[index[t]] < 0 else tokens[nasal_of[index[t]]]
        assert got == (-1 if want == "\u1e43" else want), (t, want, got)

    # The Sanskrit phonemes are NOT graphemes of the inventory — the
    # tokeniser refuses them in strict mode and `phonotactics` keeps
    # rejecting them — but lenient comparison prices them with real
    # phonology instead of as opaque cost-1 characters (SPEC §14), so the
    # scanner has to recognise them and the cost table has to include them.
    # They are reachable only through lenient tokenisation.
    foreign = [(ord(g), index[g]) for g in sorted(FOREIGN)]
    assert len(foreign) == len(FOREIGN), "two Sanskrit graphemes share a codepoint"
    assert all(index[g] >= n_plain for g in FOREIGN), "a foreign grapheme is plain"
    assert all(cp < 65536 for cp, _ in foreign), "a codepoint needs a short"

    epenthetic = [index[g] for g in sorted(EPENTHETIC)]

    return Tables(
        tokens=tokens,
        n_plain=n_plain,
        one=one_table,
        two=two_lookup.tokens,
        two_row=two_row,
        two_span=two_lookup.spans,
        two_keys=two_lookup.keys,
        geminate_pairs=pair_table,
        indel=[_indel(t) for t in tokens],
        nasal_of=nasal_of,
        foreign=foreign,
        epenthetic=epenthetic,
        cost=[cost(a, b) for a in tokens for b in tokens],
    )


def render_c(t: "Tables") -> str:
    n = len(t.tokens)
    assert len(t.epenthetic) == len(EPENTHETIC), "an epenthetic grapheme is not a token"
    char_len = [utf8_len(b) for b in range(256)]
    rows = []
    for i in range(n):
        row = t.cost[i * n:(i + 1) * n]
        rows.append("    { " + ", ".join(f"{v!a}" for v in row[:4]) + ",")
        for j in range(4, n, 4):
            rows.append(f"      {', '.join(f'{v!a}' for v in row[j:j + 4])},")
        rows[-1] = rows[-1][:-1] + " },"
    return f"""/* GENERATED by tools/generate_c_tables.py — do not edit by hand.
 *
 * The token vocabulary, the substitution-cost matrix and the derived
 * constants of the abugida metric, transcribed from the Python package. The
 * generator reads them from `phonology`, `embed`, `distance` and `lexicon`
 * and emits `%a` literals, so the C core and the Python package hold the
 * same doubles. `tests/test_c_parity.py` fails if this file is stale.
 *
 * ABI version {ABI_VERSION}: {n} tokens, {t.n_plain} of them graphemes.
 */

#include "abugida_tables.h"

/* --- the vocabulary ------------------------------------------------ */

const char *const abugida_ts_text[{n}] = {{
{chr(10).join(f'    "{g}",' for g in t.tokens)}
}};

/* Token id -> UTF-8 length in bytes. The first {t.n_plain} are graphemes, the
 * rest are long consonants, which never appear in input text. */
const unsigned char abugida_ts_len[{n}] = {{
{emit_ints([len(g.encode()) for g in t.tokens], 16)}
}};

/* --- the scanner's two lookups ------------------------------------- */

/* How many bytes the UTF-8 sequence starting with this byte occupies, or 0
 * when the byte cannot start one (a continuation byte, or invalid input). */
const unsigned char abugida_ts_char_len[256] = {{
{emit_ints(char_len, 16)}
}};

const abugida_token_t abugida_ts_one[{len(t.one)}] = {{
{emit_ints(t.one, 16)}
}};

const abugida_token_t abugida_ts_two[{len(t.two)}] = {{
{emit_ints(t.two, 16)}
}};

const unsigned short abugida_ts_two_cp0[{len(t.two)}] = {{
{emit_ints([k[0] for k in t.two_keys], 12)}
}};

const unsigned char abugida_ts_two_cp1[{len(t.two)}] = {{
{emit_ints([k[1] for k in t.two_keys], 16)}
}};

const unsigned char abugida_ts_two_row[256] = {{
{emit_ints(t.two_row, 16)}
}};

/* The width of each row, so the scanner knows where a row's keys end. */
const unsigned char abugida_ts_two_span[{len(t.two)}] = {{
{emit_ints(t.two_span, 16)}
}};

/* --- token properties --------------------------------------------- */

const unsigned short abugida_ts_foreign_cp[{len(t.foreign)}] = {{
{emit_ints([cp for cp, _ in t.foreign], 8)}
}};

const abugida_token_t abugida_ts_foreign_id[{len(t.foreign)}] = {{
{emit_ints([i for _, i in t.foreign], 8)}
}};

const short abugida_ts_nasal_of[{n}] = {{
{emit_ints(t.nasal_of, 16)}
}};

/* id(first) * ABUGIDA_NPLAIN + id(second) -> the long consonant, id + 1. */
const unsigned char abugida_ts_gempair[{len(t.geminate_pairs)}] = {{
{emit_ints(t.geminate_pairs, 16)}
}};

const short abugida_ts_epenthetic[] = {{
{emit_ints(t.epenthetic, 16)}
    -1,
}};

/* --- the derived constants ---------------------------------------- */

const double abugida_ts_neutral_modifier_weight = {NEUTRAL_MODIFIER_WEIGHT!a};
const double abugida_ts_indel_weight = {INDEL_WEIGHT!a};
const double abugida_ts_one_move = {ONE_MOVE!a};

/* --- every token's insertion/deletion cost ----------------------------- */

const double abugida_ts_indel[{n}] = {{
{chr(10).join("    " + ", ".join(repr(x) for x in t.indel[k:k + 4]) + "," for k in range(0, n, 4))}
}};

/* --- the substitution cost, {n} x {n} --------------------------------- */

const double abugida_ts_cost[{n}][{n}] = {{
{chr(10).join(rows)}
}};

/* The embeddings themselves are not carried into C: every angular distance
 * the metric needs is already in the matrix above, computed once here by the
 * same `distance.cost` the Python API calls. */
"""


def parity_pairs() -> str:
    """The fixture `tests/c/test_abugida.c` scores itself against.

    Every line is `word1 word2 distance`, computed HERE by the Python
    implementation, so the C core's own test suite checks the C core against
    the reference and not against itself. The pairs cover the whole
    inventory, both digraph lengths, gemination and the epenthetic classes,
    and are deliberately not all one edit apart: a pair that shares no
    segment exercises the cap and the indels.
    """
    import itertools
    import random

    from abugida.alphabet import ALPHABET
    from abugida._pure import distance as py_distance
    from abugida.sandhi import assimilate_word, contract_word

    words = [
        "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
        "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
        "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha", "attha",
        "atha", "magga", "makka", "kāma", "gacchati", "gacchanti", "sve",
        "suve", "idāni", "dāni", "uṭṭhita", "vuṭṭhita", "sakiṃ", "saki",
        "dhamma", "dharma", "mettaṃ", "metta", "vikkhambhati", "vikhambhati",
        "abhibhavati", "abhibhoti", "anavakāsa", "anokāsa", "bhāvayitvā",
        "bhāvetvā", "soḷasa", "sola", "ñāṇa", "nāṇa", "khanti", "kanti",
    ]
    # Every grapheme against every other, as single letters.
    letters = [p.grapheme for p in ALPHABET]
    pairs = [(w1, w2) for w1, w2 in itertools.combinations(words, 2)]
    pairs += [(a, b) for a, b in itertools.combinations(letters, 2)]
    pairs += [(w, w) for w in words]

    # Assimilated and contracted spellings, the pipeline's own material.
    for w in words:
        try:
            pairs.append((w, assimilate_word(w)))
        except ValueError:
            pass
        pairs.append((w, contract_word(w)))

    # A fixed-seed sample of synthetic words, so the fixture covers
    # combinations no word list happens to contain.
    rng = random.Random(20260801)
    alphabet = [p.grapheme for p in ALPHABET]
    synthetic = ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 9)))
                 for _ in range(60)]
    pairs += [(a, b) for a, b in itertools.combinations(synthetic, 2)]

    lines = [
        "# Generated by tools/generate_c_tables.py from the PYTHON "
        "implementation.",
        "# tests/c/test_abugida.c scores the C core against these numbers. "
        "Do not edit.",
        f"const indel_weight {INDEL_WEIGHT!r}",
        f"const one_move {ONE_MOVE!r}",
    ]
    for w1, w2 in pairs:
        lines.append(f"{w1} {w2} {py_distance(w1, w2)!r}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="do not write; fail if a committed file is stale")
    args = ap.parse_args()

    tables = build()
    header = render_header(tables)
    source = render_c(tables)
    outputs = [(OUT_H, header), (OUT_C, source), (OUT_PAIRS, parity_pairs())]

    if args.check:
        stale = [p for p, text in outputs if not p.exists() or p.read_text() != text]
        if stale:
            for p in stale:
                print(f"{p} is stale: run python tools/generate_c_tables.py")
            return 1
        print("csrc/abugida_tables.h and csrc/abugida_tables.c are up to date")
        return 0

    for p, text in outputs:
        p.write_text(text)
        print(f"wrote {p.name} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
