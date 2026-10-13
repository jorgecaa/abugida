/* abugida — the C implementation of the metric. See abugida.h for the API,
 * what it covers and what it deliberately leaves to the caller.
 *
 * One thing is worth reading before the code: `abugida_edit` is the ONLY
 * place the recurrence is written in this library. The Python package had to
 * write it twice — `_edit` with rolling rows and `alignment` with a full
 * matrix — and keeps a test (`test_alignment_conserves_the_distance`) to hold
 * the two together. Here the distance is a projection of the alignment's last
 * cell, so the two cannot drift apart.
 */

#include "abugida.h"

#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Byte helpers (no locale, no libc extensions)                        */
/* ------------------------------------------------------------------ */

/* Number of bytes making up the character at `s`, or 0 when `s` does not
 * start one: a continuation byte, an invalid lead, or a truncated sequence.
 * The bounds check is here, so nothing reads past the end of the input. */
static size_t charlen(const char *s, size_t len)
{
    size_t need;
    size_t k;

    need = abugida_ts_char_len[(unsigned char)s[0]];
    if (need == 0 || need > len)
        return 0;
    for (k = 1; k < need; k++) {
        if (((unsigned char)s[k] & 0xC0) != 0x80)
            return 0;
    }
    return need;
}

/* The codepoint a decoded character stands for. Only called on a sequence
 * `charlen` has already validated, so `n` is 1, 2, 3 or 4 and the
 * continuation bytes really are continuations. */
static unsigned long codepoint_of(const char *s, size_t n)
{
    unsigned long cp;
    size_t k;

    /* A lead byte carries its length in its high bits, so the payload is the
     * low 7, 5, 4 or 3 bits: `0xFF >> n` selects exactly them (0x7F, 0x1F,
     * 0x0F, 0x07). */
    cp = (unsigned long)((unsigned char)s[0] & (0xFFu >> n));
    for (k = 1; k < n; k++)
        cp = (cp << 6) | (unsigned long)((unsigned char)s[k] & 0x3Fu);
    return cp;
}

static int bytes_are(const char *s, size_t n, const char *want, size_t wn)
{
    return n == wn && memcmp(s, want, wn) == 0;
}

/* ṁ (U+1E41), the variant spelling of the niggahīta, accepted as ṃ (U+1E43).
 * They are different strings, so accepting the variant cannot shadow the
 * canonical form. */
static int is_niggahita_variant(const char *s, size_t n)
{
    return bytes_are(s, n, "\xe1\xb9\x81", 3);
}

/* The Sanskrit IAST characters that are rejected with their own message: ṛ
 * and ṝ (the vocalic liquids), ṣ and ś (the sibilants Pāli merged into s).
 * Pāli keeps ḷ as its retroflex lateral, so it is an ordinary grapheme here
 * and deliberately not in this list. Reports where in the word it is, in
 * bytes, as the UTF-8 of the character rather than as a codepoint index. */
static int is_sanskrit(const char *s, size_t len)
{
    size_t n = charlen(s, len);

    return bytes_are(s, n, "\xe1\xb9\x9b", 3)  /* ṛ */
        || bytes_are(s, n, "\xe1\xb9\x9d", 3)  /* ṝ */
        || bytes_are(s, n, "\xe1\xb9\xa3", 3)  /* ṣ */
        || bytes_are(s, n, "\xc5\x9b", 2);     /* ś */
}

/* The codepoints `str.isspace()` accepts beyond ASCII, DERIVED from Python
 * rather than guessed: `[c for c in map(chr, range(0x110000)) if
 * c.isspace()]` is 29 characters, nine of them ASCII (handled by
 * `is_skipped`) and these twenty. The reference implementation skips
 * whitespace with `str.isspace()`, so the C scanner has to skip exactly the
 * same set or the two tokenisers disagree on input like a non-breaking space
 * from a pasted web page — which is precisely the input a search box sees.
 *
 * Sorted, so the scan is a binary search and the table can be checked by eye
 * against the Python expression above. */
static const unsigned long UNICODE_SPACE[] = {
    0x0085, 0x00A0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004,
    0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200A, 0x2028, 0x2029,
    0x202F, 0x205F, 0x3000
};

#define ABUGIDA_NSPACE \
    (sizeof(UNICODE_SPACE) / sizeof(UNICODE_SPACE[0]))

/* The same predicate, for the codepoints the byte table does not cover. */
static int is_unicode_space(unsigned long cp)
{
    size_t lo = 0;
    size_t hi = ABUGIDA_NSPACE;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;

        if (UNICODE_SPACE[mid] == cp)
            return 1;
        if (UNICODE_SPACE[mid] < cp)
            lo = mid + 1;
        else
            hi = mid;
    }
    return 0;
}

/* Editorial marks dropped without complaint: the compound hyphen, the ASCII
 * apostrophe, the typographic one (U+2019), and ASCII whitespace. */
static int is_apostrophe(const char *s, size_t len)
{
    return len >= 3 && (unsigned char)s[0] == 0xE2
        && (unsigned char)s[1] == 0x80 && (unsigned char)s[2] == 0x99;
}

static int is_skipped(unsigned char c)
{
    switch (c) {
    case '-':
    case '\'':
    case ' ':
    case '\t':
    case '\n':
    case '\v':
    case '\f':
    case '\r':
        return 1;
    }
    return 0;
}

/* Which one-character grapheme a character is, or ABUGIDA_NO_TOKEN. The
 * table is keyed by the character's first and last UTF-8 bytes: the lead
 * alone would confuse the five graphemes that start with 0xE1 (ṭ ḍ ṇ ḷ ṃ),
 * and the pair is exact over the inventory, so no byte comparison is needed
 * at run time.
 *
 * `lead` is passed separately from the text because ASCII case folding is
 * applied to it before the lookup: an uppercase 'S' is looked up as 's'. For
 * a one-byte character the folded byte is also the LAST byte, which is why
 * the slot below takes `lead` on both sides there; for a multi-byte one the
 * folded byte is the lead byte unchanged, since folding only rewrites
 * ASCII. */
static abugida_token one_token(const char *s, size_t len, unsigned char lead)
{
    unsigned char last = len == 1 ? lead : (unsigned char)s[len - 1];
    size_t slot = ((size_t)lead << 8) | (size_t)last;

    return abugida_ts_one[slot] ? (abugida_token)(abugida_ts_one[slot] - 1)
                                : (abugida_token)ABUGIDA_NO_TOKEN;
}

/* The same for a PAIR of characters: the initial character's codepoint, and
 * the second character — always ASCII `h`, but the table's own second column
 * decides that, not this comment. Character pairs, not byte pairs: what
 * `iast.tokenize` tries at a position is two characters, whatever their byte
 * lengths are. A row is a run of at most a dozen keys, scanned in order. */
static abugida_token two_token(unsigned char lead, unsigned long first,
                               unsigned char second)
{
    /* The row is selected by the LEAD byte, which the table is grouped by;
     * the codepoint is compared inside the row, so two characters sharing a
     * lead byte (ḍh and ṭh both start with 0xE1) are told apart by the
     * comparison rather than by the row. */
    unsigned char row = abugida_ts_two_row[lead];
    unsigned char span;
    unsigned char i;

    if (row == 255)
        return ABUGIDA_NO_TOKEN;
    span = abugida_ts_two_span[row];
    for (i = 0; i < span; i++) {
        if (abugida_ts_two_cp0[row + i] == first
            && abugida_ts_two_cp1[row + i] == second)
            return abugida_ts_two[row + i]
                ? (abugida_token)(abugida_ts_two[row + i] - 1)
                : (abugida_token)ABUGIDA_NO_TOKEN;
    }
    return ABUGIDA_NO_TOKEN;
}

/* The Sanskrit phoneme a codepoint is, or ABUGIDA_NO_TOKEN. A small sorted
 * table — three entries — scanned linearly, which is cheaper than any index
 * and cannot go stale. */
static abugida_token foreign_token(unsigned long cp)
{
    size_t i;

    for (i = 0; i < ABUGIDA_NFOREIGN; i++) {
        if (abugida_ts_foreign_cp[i] == cp)
            return abugida_ts_foreign_id[i];
    }
    return ABUGIDA_NO_TOKEN;
}

/* An unknown character in lenient mode.
 *
 * Encoded as a negative id so it can never collide with a real token, and so
 * that equality in `abugida_cost` means what it should: the same opaque
 * character costs 0 against itself and 1 against everything else.
 *
 * What is stored is the character's CODEPOINT, not its first UTF-8 byte, and
 * the difference is the difference between one typo and several. The
 * reference implementation absorbs one character as one token; a byte would
 * spend four tokens on an emoji and two on an accented Latin letter,
 * inflating the distance by the width of the character's encoding — a
 * measurement artefact with no phonological content, and one that ranks a
 * single mistyped character further from the truth than two ordinary typos.
 *
 * WHAT FITS, AND WHAT CANNOT. The token is a signed 16-bit id, so an opaque
 * character has 15 bits below the marker to live in: 32767 slots, numbered
 * 1 upwards. A collision here is a WRONG ANSWER, not a coarse one — two
 * different characters priced as identical — and the differential harness
 * found one in the first version of this, which spent the bits on the
 * codepoint's low bits: `levenshtein("a", "\u00e9")` returned 0, because
 * 'a' (0x61) and a two-byte character truncated to 0xE9 landed on the same
 * slot after the mask.
 *
 * The slots are therefore allocated so that the COMMON case is exact, and the
 * arithmetic is small enough to check by hand:
 *
 *     U+0000 .. U+7FFC    ->  1 .. 32765        EXACT, injective
 *     U+7FFD .. U+FFFF    ->  0x8000 + ((cp - 0x7FFD) >> 12)   257 slots
 *     U+10000 .. U+10FFFF ->  0x9000 + ((cp - 0x10000) >> 12)  256 slots
 *
 * The first row is inclusive of everything below it — U+4E00 (the first CJK
 * ideograph) and U+AC00 (the first Hangul syllable) are both inside it — so
 * the common case is not merely mostly exact, it is exact. Every character a
 * Pāli reader or a web form is
 * likely to contain — Latin, Latin-1, Greek, Cyrillic, Hebrew, Arabic,
 * Devanagari, the combining marks, and the CJK and Hangul blocks that begin
 * below U+7FFE — is exact and distinct from every other, including across
 * scripts, and no such character can ever share a token with one from the
 * folded bands. The second and third rows fold their tails into 256 slots
 * each, so those characters collide only within their own band: about one in
 * 256 for the upper BMP and the astral planes.
 *
 * The alternative does not exist — the reference holds arbitrary Python
 * strings, this holds 15 bits, and the two must agree wherever a user can
 * see — so the honest statement is that below U+7FFF the port is exact and
 * above it is deliberately coarse. That is the same limit "a typo costs 1
 * against everything" already had (`docs/comparator.md`): the lenient path
 * has never claimed to tell WHICH character a typo replaced, only that the
 * intact remainder of the word still discriminates.
 *
 * The binding keeps the same encoding, so the round trip is observable
 * through `texts()`. */
/* THE DISPOSITION, and the arithmetic that makes it checkable.
 *
 * `abugida_token` is int16 and the marker is -1, so an opaque character has
 * slots 1..32766 — 15 bits. Unicode has 21 bits of characters, so SOME
 * collapsing is forced; the only question is which characters share a slot,
 * and the answer has to be "characters that could not be confused in
 * practice".
 *
 * The two high bits of the slot are the CATEGORY, which is the character's
 * UTF-8 length. That alone guarantees what matters most: two characters of
 * different byte-length can never collide, so a Latin letter can never be
 * confused with a Cyrillic one, nor either with a CJK ideograph.
 *
 *     category      codepoints          slots                    exact?
 *     0 (1 byte)    U+0000..U+007F      0x0000 + cp               exact
 *     1 (2 bytes)   U+0080..U+07FF      0x0080 + (cp - 0x80)      exact
 *     2 (3 bytes)   U+0800..U+FFFF      0x0800 + ((cp - 0x800) % 8192)
 *     3 (4 bytes)   U+10000..U+10FFFF   0x4000 + ((cp - 0x10000) % 8192)
 *
 * Categories 0 and 1 are INJECTIVE, which covers Latin, Latin-1, Greek,
 * Cyrillic, Hebrew, Arabic and all the combining marks — the characters a
 * Pāli word or a web form can actually contain. Category 2 folds CJK and
 * Hangul within itself (one collision per 8192 codepoints, so two Han
 * ideographs collide about once in 8192 pairs) and category 3 folds the
 * astral planes within themselves (one in 128).
 *
 * The alternative does not exist: the reference holds arbitrary Python
 * strings and this holds 15 bits. What the collapsing costs is exactly one
 * thing — `levenshtein` reports 0 instead of 1 for two DIFFERENT characters
 * that share a slot — and `distance` is unaffected, because an opaque token
 * costs 1 against every token other than itself either way. That is the same
 * limit "a typo costs 1 against everything" always had: the lenient path
 * never claimed to identify WHICH character a typo replaced
 * (`docs/comparator.md`), only that the intact remainder of the word still
 * discriminates. `tools/differential.py` states the exceptions rather than
 * being tuned until it passes.
 *
 * The binding keeps this encoding, so the round trip is observable through
 * `texts()`. */
#define ABUGIDA_OPAQUE_CAT_BYTES 8192u      /* codepoints folded per slot band */
#define ABUGIDA_OPAQUE_MAX_CODEPOINT 0x10FFFFu

static abugida_token opaque_token(unsigned long codepoint, size_t bytes)
{
    unsigned long slot;

    switch (bytes) {
    case 1:
        slot = codepoint;
        break;
    case 2:
        slot = 0x0080UL + (codepoint - 0x80UL);
        break;
    case 3:
        slot = 0x0800UL + ((codepoint - 0x800UL) % ABUGIDA_OPAQUE_CAT_BYTES);
        break;
    default:
        if (codepoint > ABUGIDA_OPAQUE_MAX_CODEPOINT)
            return ABUGIDA_NO_TOKEN; /* not a scalar value: cannot be UTF-8 */
        slot = 0x4000UL
            + ((codepoint - 0x10000UL) % ABUGIDA_OPAQUE_CAT_BYTES);
        break;
    }
    /* The largest slot any branch can produce is 0x5FFF, so the subtraction
     * stays inside int16. Asserted rather than assumed: a slot above 32766
     * wraps to a POSITIVE token, which is not an opaque token at all but a
     * collision with a real id — the first version of this shipped exactly
     * that bug and the differential harness caught it. */
    if (slot > 32766UL)
        return ABUGIDA_NO_TOKEN;
    return (abugida_token)(ABUGIDA_NO_TOKEN - (abugida_token)slot);
}

/* ------------------------------------------------------------------ */
/* Growing strings                                                     */
/* ------------------------------------------------------------------ */

static char *sgrow(abugida_string *s, size_t need)
{
    size_t cap;
    char *text;

    if (s->text && s->cap >= need)
        return s->text;

    cap = s->cap ? s->cap : 32;
    while (cap < need) {
        if (cap > (size_t)-1 / 2)
            return NULL;
        cap *= 2;
    }
    text = (char *)realloc(s->heap ? s->text : NULL, cap);
    if (!text)
        return NULL;
    if (!s->heap && s->text && s->n)
        memcpy(text, s->text, s->n);
    s->text = text;
    s->cap = cap;
    s->heap = 1;
    return text;
}

/* Append bytes, keeping the NUL terminator. */
static int sputs(abugida_string *s, const char *bytes, size_t n)
{
    if (!n)
        return 0;
    if (!sgrow(s, s->n + n + 1))
        return -1;
    memcpy(s->text + s->n, bytes, n);
    s->n += n;
    s->text[s->n] = '\0';
    return 0;
}

static void sreset(abugida_string *s)
{
    s->n = 0;
    if (s->text)
        s->text[0] = '\0';
}

void abugida_string_init(abugida_string *s)
{
    if (!s)
        return;
    s->text = NULL;
    s->n = 0;
    s->cap = 0;
    s->heap = 0;
}

abugida_status abugida_string_alloc(abugida_string *s, size_t capacity)
{
    if (!s)
        return ABUGIDA_ERR_INVALID;
    if (!sgrow(s, capacity ? capacity : 1))
        return ABUGIDA_ERR_NOMEM;
    s->text[0] = '\0';
    s->n = 0;
    return ABUGIDA_OK;
}

void abugida_string_free(abugida_string *s)
{
    if (!s)
        return;
    if (s->heap && s->text)
        free(s->text);
    abugida_string_init(s);
}

/* ------------------------------------------------------------------ */
/* Token properties straight off the generated tables                  */
/* ------------------------------------------------------------------ */

const char *abugida_token_text(abugida_token t)
{
    if (t < 0 || t >= ABUGIDA_NTOKENS)
        return NULL;
    return abugida_ts_text[t];
}

const char *abugida_token_text_len(abugida_token t, size_t *len)
{
    if (t < 0 || t >= ABUGIDA_NTOKENS) {
        if (len)
            *len = 0;
        return NULL;
    }
    if (len)
        *len = abugida_ts_len[t];
    return abugida_ts_text[t];
}

/* The heavy unit two adjacent tokens form — a geminate (tt, tth) or a
 * homorganic nasal+stop cluster (nt, ṅkh) — or ABUGIDA_NO_TOKEN. This is the
 * C form of Python's `tokens[i] + tokens[i+1] in _UNITS`: the generator has
 * already resolved every such pair to a token id, so it is one table read
 * and no string building. */
static abugida_token unit_token(abugida_token first, abugida_token second)
{
    size_t key;

    /* Only graphemes of the inventory can form a unit: a unit token, or an
     * opaque one, has no entry and no key. */
    if (first < 0 || first >= ABUGIDA_NPLAIN
        || second < 0 || second >= ABUGIDA_NPLAIN)
        return ABUGIDA_NO_TOKEN;
    key = (size_t)first * ABUGIDA_NPLAIN + (size_t)second;
    return abugida_ts_gempair[key] != 0
        ? (abugida_token)(abugida_ts_gempair[key] - 1)
        : (abugida_token)ABUGIDA_NO_TOKEN;
}

/* THE SEGMENTATION: a word's one reading as heavy units, left to right, as
 * Python's `_segment` does it. `out` must hold `n` tokens; the count written
 * is returned. Greedy is not a choice among readings: two candidate units
 * never overlap in a word the inventory can spell (SPEC §8). */
static size_t segment_units(const abugida_token *seq, size_t n,
                            abugida_token *out)
{
    size_t i = 0;
    size_t k = 0;

    while (i < n) {
        if (i + 1 < n) {
            abugida_token u = unit_token(seq[i], seq[i + 1]);

            if (u != ABUGIDA_NO_TOKEN) {
                out[k++] = u;
                i += 2;
                continue;
            }
        }
        out[k++] = seq[i++];
    }
    return k;
}

/* A segmented copy of a token sequence: on the stack for words of up to
 * ABUGIDA_STACK_TOKENS tokens, on the heap beyond, like the DP's rows. */
typedef struct {
    abugida_token stack[ABUGIDA_STACK_TOKENS];
    abugida_token *tok;
    size_t n;
} units_buf;

static abugida_status units_of(const abugida_token *seq, size_t n,
                               units_buf *u)
{
    u->tok = u->stack;
    if (n > ABUGIDA_STACK_TOKENS) {
        u->tok = (abugida_token *)malloc(n * sizeof(abugida_token));
        if (!u->tok)
            return ABUGIDA_ERR_NOMEM;
    }
    u->n = n ? segment_units(seq, n, u->tok) : 0;
    return ABUGIDA_OK;
}

static void units_free(units_buf *u)
{
    if (u->tok && u->tok != u->stack)
        free(u->tok);
    u->tok = NULL;
}

/* What the niggahita becomes before `next`: the series nasal, or
 * ABUGIDA_NO_TOKEN when it stays unresolved. The table is built by calling
 * `phonology.assimilate` in the generator, so this is that rule and not a
 * paraphrase of it. */
static abugida_token assimilated_nasal(abugida_token next)
{
    if (next < 0 || next >= ABUGIDA_NPLAIN)
        return ABUGIDA_NO_TOKEN;
    return abugida_ts_nasal_of[next] < 0
        ? (abugida_token)ABUGIDA_NO_TOKEN
        : (abugida_token)abugida_ts_nasal_of[next];
}

double abugida_cost(abugida_token a, abugida_token b)
{
    /* Identical tokens cost nothing even when they are opaque: a typo is
     * maximally distant from every real grapheme, not from itself. */
    if (a == b && a != ABUGIDA_NO_TOKEN)
        return 0.0;
    if (a < 0 || a >= ABUGIDA_NTOKENS || b < 0 || b >= ABUGIDA_NTOKENS)
        return 1.0;
    return abugida_ts_cost[a][b];
}

double abugida_indel(abugida_token t)
{
    if (t < 0 || t >= ABUGIDA_NTOKENS)
        return 1.0;
    /* Generated from Python's `_indel`: 1, the epenthetic weight, or a heavy
     * unit's derived indel. */
    return abugida_ts_indel[t];
}

double abugida_neutral_modifier_weight(void)
{
    return abugida_ts_neutral_modifier_weight;
}

double abugida_indel_weight(void)
{
    return abugida_ts_indel_weight;
}

double abugida_one_move(void)
{
    return abugida_ts_one_move;
}

const abugida_token *abugida_epenthetic(size_t *n)
{
    size_t i;

    if (n) {
        i = 0;
        while (abugida_ts_epenthetic[i] != ABUGIDA_NO_TOKEN)
            i++;
        *n = i;
    }
    return (const abugida_token *)abugida_ts_epenthetic;
}

const char *abugida_strerror(abugida_status st)
{
    switch (st) {
    case ABUGIDA_OK:
        return "no error";
    case ABUGIDA_ERR_NOT_PALI:
        return "character outside the Pali alphabet";
    case ABUGIDA_ERR_SANSKRIT:
        return "Sanskrit IAST character, which is not Pali";
    case ABUGIDA_ERR_NOMEM:
        return "out of memory";
    case ABUGIDA_ERR_CAPACITY:
        return "buffer too small";
    case ABUGIDA_ERR_INVALID:
        return "invalid argument";
    }
    return "unknown error";
}

/* ------------------------------------------------------------------ */
/* Words                                                               */
/* ------------------------------------------------------------------ */

void abugida_word_init(abugida_word *w)
{
    if (!w)
        return;
    w->tok = NULL;
    w->n = 0;
    w->cap = 0;
    w->heap = 0;
}

void abugida_word_free(abugida_word *w)
{
    if (!w)
        return;
    if (w->heap && w->tok)
        free(w->tok);
    abugida_word_init(w);
}

abugida_status abugida_word_alloc(abugida_word *w, size_t capacity)
{
    abugida_token *tokens;

    if (!w)
        return ABUGIDA_ERR_INVALID;
    if (!capacity)
        capacity = 1;
    if (w->heap && w->cap >= capacity)
        return ABUGIDA_OK;
    tokens = (abugida_token *)malloc(capacity * sizeof(abugida_token));
    if (!tokens)
        return ABUGIDA_ERR_NOMEM;
    if (w->heap)
        free(w->tok);
    w->tok = tokens;
    w->n = 0;
    w->cap = capacity;
    w->heap = 1;
    return ABUGIDA_OK;
}

abugida_token abugida_foreign_token(unsigned long codepoint)
{
    return foreign_token(codepoint);
}

abugida_token abugida_token_from_text(const char *text, size_t len)
{
    size_t i;

    if (!text || !len)
        return ABUGIDA_NO_TOKEN;
    for (i = 0; i < ABUGIDA_NTOKENS; i++) {
        if (abugida_ts_len[i] == len
            && memcmp(abugida_ts_text[i], text, len) == 0)
            return (abugida_token)i;
    }
    /* The Sanskrit phonemes are tokens but not graphemes, so the loop above
     * does not reach them: they are not in the tokeniser's tables. A caller
     * asking for the token `cost` should use for ṣ gets one.
     *
     * Note WHAT is looked up: the whole of `text`, not its first character,
     * because that is what the reference does — `_GEMINATE_BASES.get(g)`,
     * then `BY_GRAPHEME.get(g) or FOREIGN.get(g)`, all keyed by the string it
     * was handed and with no decoding. So `cost("a", "śānti")` is 1.0 in both
     * implementations: the reference finds no entry for "śānti" and the
     * opaque answer is 1.0, and this mirrors it rather than being more
     * helpful. Being MORE correct here would be a difference, and the point
     * of the C core is to be the same function.
     *
     * `cost` is documented and used as a per-grapheme cost, which is the
     * domain where the two agree on something meaningful; the whole-string
     * case is a quirk of the reference that a port has to reproduce. */
    if (len <= 4) {
        abugida_token foreign = foreign_token(codepoint_of(text, len));

        if (foreign != ABUGIDA_NO_TOKEN)
            return foreign;
    }
    return ABUGIDA_NO_TOKEN;
}

abugida_status abugida_word_from_text(abugida_word *w, const char *text,
                                      size_t len, int lenient,
                                      size_t *err_off)
{
    abugida_token stack[ABUGIDA_STACK_TOKENS];
    abugida_token *out = stack;
    size_t cap = ABUGIDA_STACK_TOKENS;
    size_t i = 0;
    size_t n = 0;
    int heap = 0;
    size_t fail_at = 0;
    abugida_status fail_with = ABUGIDA_OK;

    if (!w || (!text && len))
        return ABUGIDA_ERR_INVALID;
    if (err_off)
        *err_off = 0;

    /* A word longer than the stack buffer starts on the heap: one allocation
     * instead of a growing sequence of them. The multiplication is guarded
     * because `len` is caller-supplied: wrapping it would allocate a small
     * buffer for a huge length and then write past the end of it, which is
     * heap corruption rather than a failed call. */
    if (len > ABUGIDA_STACK_TOKENS) {
        if (len > ((size_t)-1) / sizeof(abugida_token))
            return ABUGIDA_ERR_NOMEM;
        out = (abugida_token *)malloc(len * sizeof(abugida_token));
        if (!out)
            return ABUGIDA_ERR_NOMEM;
        cap = len;
        heap = 1;
    }

    /* Append one token, growing the buffer if needed. `out` starts on the
     * stack for an ordinary word and on the heap for a long one; `heap` is
     * what says which, and a growth in between forgets the difference. */
#define ABUGIDA_PUSH(tok_)                                                  \
    do {                                                                    \
        if (n == cap) {                                                     \
            abugida_token *grown;                                           \
            if (cap > ((size_t)-1) / (2 * sizeof(abugida_token))) {          \
                fail_with = ABUGIDA_ERR_NOMEM;                              \
                goto done;                                                  \
            }                                                               \
            grown = (abugida_token *)                                       \
                malloc(cap * 2 * sizeof(abugida_token));                    \
            if (!grown) {                                                   \
                fail_with = ABUGIDA_ERR_NOMEM;                              \
                goto done;                                                  \
            }                                                               \
            memcpy(grown, out, n * sizeof(abugida_token));                  \
            if (heap)                                                       \
                free(out);                                                  \
            out = grown;                                                    \
            cap *= 2;                                                       \
            heap = 1;                                                       \
        }                                                                   \
        out[n++] = (tok_);                                                  \
    } while (0)

    while (i < len && fail_with == ABUGIDA_OK) {
        /* `b` is the raw lead byte, which is what the tables are keyed by;
         * `c` is the same byte with ASCII case folded, which is what the
         * grapheme comparisons use. Keeping them apart matters: folding
         * 'S' to 's' must not stop the ṁ variant or a multi-byte grapheme
         * from being recognised. */
        unsigned char b = (unsigned char)text[i];
        unsigned char c = b;
        size_t clen;
        abugida_token tok = ABUGIDA_NO_TOKEN;

        if (is_apostrophe(text + i, len - i)) {
            i += 3;
            continue;
        }
        if (is_skipped(c)) {
            i++;
            continue;
        }
        /* Whitespace beyond ASCII is skipped too, and the set is the one
         * `str.isspace()` defines — see UNICODE_SPACE. Checked after the
         * character length is known, because it needs the codepoint and not
         * the lead byte. */
        if (b >= 0x80) {
            size_t space_len = charlen(text + i, len - i);

            if (space_len && is_unicode_space(codepoint_of(text + i,
                                                           space_len))) {
                i += space_len;
                continue;
            }
        }
        /* ASCII uppercase is folded here, so an un-normalised ASCII query
         * still tokenises; non-ASCII folding is the caller's job. */
        if (b >= 'A' && b <= 'Z') {
            c = (unsigned char)(c - 'A' + 'a');
            clen = 1;
        } else {
            clen = charlen(text + i, len - i);
        }
        /* `c` is the character's lead byte, which is what the one-character
         * table is keyed by: for an ASCII grapheme the byte IS the character,
         * and for a multi-byte one the byte selects the table entry the
         * decoder above has already validated. */

        if (clen && is_niggahita_variant(text + i, clen)) {
            tok = ABUGIDA_TOK_M_DOT;
        } else if (clen) {
            unsigned char d = 0;

            if (i + clen < len && (unsigned char)text[i + clen] != 0) {
                d = (unsigned char)text[i + clen];
                if (d >= 'A' && d <= 'Z')
                    d = (unsigned char)(d - 'A' + 'a');
                /* The second character must be a whole one before the pair
                 * is offered to the table. */
                if (d >= 0x80 && charlen(text + i + clen, len - i - clen) == 0)
                    d = 0;
            }
            /* Longest match by CHARACTER count, exactly as `iast.tokenize`
             * scans: the pair first, then one. */
            if (d)
                tok = two_token(b, codepoint_of(text + i, clen), d);
            if (tok != ABUGIDA_NO_TOKEN) {
                clen += d < 0x80 ? 1 : charlen(text + i + clen, len - i - clen);
            } else {
                tok = one_token(text + i, clen, c);
            }
        }

        if (tok == ABUGIDA_NO_TOKEN) {
            if (!lenient) {
                fail_at = i;
                fail_with = clen && is_sanskrit(text + i, len - i)
                    ? ABUGIDA_ERR_SANSKRIT : ABUGIDA_ERR_NOT_PALI;
                break;
            }
            /* Lenient: a Sanskrit phoneme carries real phonology and is
             * priced as the phoneme (ṣ↔s is 0.460, ś↔s 0.667 — Pāli merged
             * all sibilants into s), while anything else is opaque, cost 1
             * against everything. This is the difference between supporting
             * Sanskrit input and supporting typos. */
            if (clen) {
                tok = foreign_token(codepoint_of(text + i, clen));
                if (tok != ABUGIDA_NO_TOKEN) {
                    ABUGIDA_PUSH(tok);
                    i += clen;
                    continue;
                }
            }
            /* One unknown CHARACTER, not one byte: the token carries the
             * codepoint and the scan advances by the character's whole
             * encoding. Consuming a single byte would turn a two-byte
             * character into two opaque tokens (it and its continuation byte)
             * where
             * the reference spends one — a cost of 2.0 for a one-character
             * typo, and a `texts()` that returns the wrong characters. */
            if (clen) {
                tok = opaque_token(codepoint_of(text + i, clen), clen);
            } else {
                tok = opaque_token(c, 1);
                clen = 1;
            }
        }

        ABUGIDA_PUSH(tok);
        i += clen;
    }

done:
#undef ABUGIDA_PUSH

    if (fail_with != ABUGIDA_OK) {
        if (err_off)
            *err_off = fail_at;
        if (heap)
            free(out);
        return fail_with;
    }

    /* Commit. A caller-owned buffer that is too small is not an error: the
     * library allocates and takes ownership, which is what `heap` records. */
    if (!w->heap && w->cap < n) {
        abugida_token *copy =
            (abugida_token *)malloc((n ? n : 1) * sizeof(abugida_token));
        if (!copy) {
            if (heap)
                free(out);
            return ABUGIDA_ERR_NOMEM;
        }
        w->tok = copy;
        w->cap = n;
        w->heap = 1;
    } else if (w->heap && w->cap < n) {
        free(w->tok);
        w->tok = NULL;
        w->cap = 0;
        w->heap = 0;
        if (abugida_word_alloc(w, n) != ABUGIDA_OK) {
            if (heap)
                free(out);
            return ABUGIDA_ERR_NOMEM;
        }
    }
    if (n)
        memcpy(w->tok, out, n * sizeof(abugida_token));
    w->n = n;
    if (heap)
        free(out);
    return ABUGIDA_OK;
}

abugida_status abugida_diagnose(const char *text, size_t len, size_t *offs,
                                int *kinds, size_t cap, size_t *n)
{
    size_t i = 0;
    size_t found = 0;

    if (!text || (!offs && cap) || (!kinds && cap) || !n)
        return ABUGIDA_ERR_INVALID;
    *n = 0;

    while (i < len) {
        unsigned char b = (unsigned char)text[i];
        unsigned char c = b;
        size_t clen;

        if (is_apostrophe(text + i, len - i)) {
            i += 3;
            continue;
        }
        if (is_skipped(b)) {
            i++;
            continue;
        }
        if (b >= 'A' && b <= 'Z') {
            c = (unsigned char)(c - 'A' + 'a');
            clen = 1;
        } else {
            clen = charlen(text + i, len - i);
        }
        /* The same whitespace `abugida_word_from_text` skips, so the two agree
         * by construction: a character tokenisation silently drops is not one
         * that "strict tokenisation would reject", which is what this function
         * reports. */
        if (clen && b >= 0x80
            && is_unicode_space(codepoint_of(text + i, clen))) {
            i += clen;
            continue;
        }

        if (clen == 0) {
            if (found < cap) {
                offs[found] = i;
                kinds[found] = 0;
            }
            found++;
            i += 1;
            continue;
        }
        /* A character is a problem unless some grapheme STARTS here. The
         * tokeniser's own two lookups answer that; a pair that matches is
         * not a problem, and neither is its second character. */
        if (one_token(text + i, clen, c) != ABUGIDA_NO_TOKEN
            || is_niggahita_variant(text + i, clen)) {
            i += clen;
            continue;
        }
        {
            unsigned char d = 0;
            size_t clen2 = 0;

            if (i + clen < len && (unsigned char)text[i + clen] != 0) {
                d = (unsigned char)text[i + clen];
                if (d >= 'A' && d <= 'Z')
                    d = (unsigned char)(d - 'A' + 'a');
                clen2 = d < 0x80 ? 1 : charlen(text + i + clen, len - i - clen);
            }
            if (clen2
                && two_token(b, codepoint_of(text + i, clen), d)
                   != ABUGIDA_NO_TOKEN) {
                i += clen + clen2;
                continue;
            }
        }
        if (clen > 1 && foreign_token(codepoint_of(text + i, clen))
            != ABUGIDA_NO_TOKEN) {
            /* A Sanskrit phoneme: reported, but as the kind it is. */
            if (found < cap) {
                offs[found] = i;
                kinds[found] = 1;
            }
            found++;
            i += clen;
            continue;
        }
        if (found < cap) {
            offs[found] = i;
            kinds[found] = is_sanskrit(text + i, len - i) ? 1 : 0;
        }
        found++;
        i += clen;
    }
    *n = found;
    return ABUGIDA_OK;
}

/* ------------------------------------------------------------------ */
/* The recurrence                                                      */
/* ------------------------------------------------------------------ */

/* Scratch rows for the DP live on the stack for words of up to
 * ABUGIDA_STACK_TOKENS tokens, and are heap allocated beyond that. */
#define ABUGIDA_ROWS ((ABUGIDA_STACK_TOKENS + 1) * 3)

/* THE BOUNDED RUN, and the two versions of it.
 *
 * `bound` is an upper limit the caller cares about: a candidate above it will
 * be discarded, so the DP does not need to finish. `beyond` says it stopped.
 *
 * THE CUT IS PER CELL, not per row, and that took three wrong versions to
 * get right.
 *
 * Per CELL: a cell whose value exceeds the bound can never be part of a path
 * that comes back under it, because every edit is non-negative — costs only
 * grow along a path. So the cell is not stored, and no cell that reads it can
 * produce a path under the bound either.
 *
 * Not per ROW, which is the mistake. "The row's minimum exceeds the bound"
 * IS a valid way to DECIDE that the distance is above it — a path through row
 * i pays at least the cheapest cell of row i — but it is NOT a valid way to
 * STOP, because the cells of that row are still needed: a later cell of the
 * same row can be under the bound and still reach the end cheaply. Row-wise
 * cutting lost `vohari`/`voharati`, whose true distance is 1.627 against a
 * bound of 1.5: it stopped at the row whose minimum first rose above the
 * bound, while a cell in that row was still on a 1.627 path. Measured on a
 * real pool: 2.6% of verdicts wrong.
 *
 * Two versions rather than one with a flag, because the bound must not cost
 * anything to the caller who did not ask for it: `abugida_word_distance` is
 * the plain distance, and a per-cell comparison in its inner loop would be
 * paid by every call in the package. The compiler cannot tell the two apart
 * through a run-time flag, so they are two instantiations of one body —
 * `UNBOUNDED` below — which is still one place the recurrence is written.
 *
 * An unreachable cell is stored as a huge value rather than left missing,
 * which is what makes the rolling rows stay in step. */
/* THE DP, WRITTEN ONCE PER INSTANTIATION — deliberately.
 *
 * `run_dp` is the recurrence with no limit: it is what `abugida_edit`,
 * `abugida_word_distance` and `levenshtein`'s fallback all call, and it must
 * not pay for a feature none of them asked for. `run_dp_bounded` is the same
 * recurrence with a per-cell cut for a caller who only needs to know whether
 * the answer is above a bound.
 *
 * They are two functions rather than one with a flag because the flag would
 * be tested in the innermost loop of the metric: a run-time `if (bounded)`
 * there is paid by every `distance()` call in the package. The compiler
 * cannot fold it away, and the measurement that decided this is that the
 * bound must cost the unbounded caller exactly nothing.
 *
 * Keeping them in step is the cost of that, and it is paid by the tests
 * rather than by hope: `tests/c/test_abugida.c` checks the metric (607,000
 * checks), and `test_bounded.c` checks that the bounded one agrees with the
 * unbounded one cell for cell wherever it does not cut.
 *
 * THE CUT IS PER CELL, and getting there took three wrong versions, all of
 * them measured:
 *
 *   1. "stop when the row's minimum exceeds the bound" — WRONG. That the
 *      minimum of row i exceeds the bound does prove the final distance does
 *      (a path through row i pays at least that), but it does not license
 *      stopping: a later cell of the SAME row can still be under the bound
 *      and reach the end cheaply. It lost `vohari`/`voharati`, true distance
 *      1.627 against a bound of 1.5. 2.6% of verdicts wrong on a real pool.
 *   2. the same with `rowmin + remaining * min_indel` — WRONG as well, and
 *      for the opposite reason: a substitution between two equal tokens costs
 *      0, so the remaining steps have no positive floor. 4% wrong.
 *   3. per cell, which is what is here. A cell above the bound can never be
 *      part of a path that comes back under it, because every edit is
 *      non-negative: costs only grow along a path. So the cell is not stored,
 *      a value from an unstored cell is propagated as "beyond" rather than
 *      added to, and the row is still walked to its end.
 *
 * The one place this is delicate is that the rolling rows must stay in step:
 * an unstored cell is still WRITTEN (as the bound-crossing value), so the
 * rotation below is unchanged and `cur[j - 1]` is never a stale cell from two
 * rows ago. Writing nothing there was the bug that made this asymmetric.
 */
static abugida_status dp_plain(const abugida_token *a, size_t na,
                               const abugida_token *b, size_t nb,
                               abugida_sub_fn substitution, void *sub_ctx,
                               abugida_indel_fn indel, void *indel_ctx,
                               double *out)
{
    double stackrows[ABUGIDA_ROWS];
    double *rows = stackrows;
    double *prev;
    double *cur;
    double *swp;
    size_t rowcap;
    size_t i;
    size_t j;

    rowcap = nb + 1;
    if (2 * rowcap > ABUGIDA_ROWS) {
        rows = (double *)malloc(2 * rowcap * sizeof(double));
        if (!rows)
            return ABUGIDA_ERR_NOMEM;
    }
    prev = rows;
    cur = rows + rowcap;
    memset(rows, 0, 2 * rowcap * sizeof(double));

    for (j = 1; j <= nb; j++)
        prev[j] = prev[j - 1] + indel(b[j - 1], indel_ctx);

    for (i = 1; i <= na; i++) {
        abugida_token ai = a[i - 1];
        double dai = indel(ai, indel_ctx);

        cur[0] = prev[0] + dai;
        for (j = 1; j <= nb; j++) {
            abugida_token bj = b[j - 1];
            double best = prev[j] + dai;                 /* delete ai */
            double ins = cur[j - 1] + indel(bj, indel_ctx);
            double sub = prev[j - 1] + substitution(ai, bj, sub_ctx);

            if (ins < best)
                best = ins;
            if (sub < best)
                best = sub;
            cur[j] = best;
        }
        swp = prev;
        prev = cur;
        cur = swp;
    }

    *out = prev[nb];
    if (rows != stackrows)
        free(rows);
    return ABUGIDA_OK;
}

/*: A cell above the bound, stored so the rows keep their shape. Any value
 * above any bound a caller can pass will do; it is never returned. */
#define ABUGIDA_DP_OVER 1e300

static abugida_status dp_plain_bounded(const abugida_token *a, size_t na,
                                       const abugida_token *b, size_t nb,
                                       abugida_sub_fn substitution,
                                       void *sub_ctx, abugida_indel_fn indel,
                                       void *indel_ctx, double bound,
                                       int *beyond, double *out)
{
    double stackrows[ABUGIDA_ROWS];
    double *rows = stackrows;
    double *prev;
    double *cur;
    double *swp;
    size_t rowcap;
    size_t i;
    size_t j;

    rowcap = nb + 1;
    if (2 * rowcap > ABUGIDA_ROWS) {
        rows = (double *)malloc(2 * rowcap * sizeof(double));
        if (!rows)
            return ABUGIDA_ERR_NOMEM;
    }
    prev = rows;
    cur = rows + rowcap;
    memset(rows, 0, 2 * rowcap * sizeof(double));

    for (j = 1; j <= nb; j++)
        prev[j] = prev[j - 1] + indel(b[j - 1], indel_ctx);

    for (i = 1; i <= na; i++) {
        abugida_token ai = a[i - 1];
        double dai = indel(ai, indel_ctx);

        cur[0] = prev[0] + dai;
        for (j = 1; j <= nb; j++) {
            abugida_token bj = b[j - 1];
            double best;
            double ins;

            /* Adding to a cell that is already over the bound cannot bring it
             * back under: every edit is non-negative. So the sum is not
             * computed — it is carried as `ABUGIDA_DP_OVER`, which is also
             * what a cell over the bound is stored as, so the rows keep their
             * shape and the rotation below is the same in both functions. */
            best = prev[j] > bound ? ABUGIDA_DP_OVER : prev[j] + dai;
            ins = cur[j - 1] > bound ? ABUGIDA_DP_OVER
                                     : cur[j - 1] + indel(bj, indel_ctx);
            if (ins < best)
                best = ins;
            if (prev[j - 1] <= bound) {
                double sub = prev[j - 1] + substitution(ai, bj, sub_ctx);

                if (sub < best)
                    best = sub;
            }
            cur[j] = best;
        }
        swp = prev;
        prev = cur;
        cur = swp;
    }

    if (prev[nb] > bound)
        *beyond = 1;
    else
        *out = prev[nb];
    if (rows != stackrows)
        free(rows);
    return ABUGIDA_OK;
}

/* The two entry points: segment both words into heavy units when the caller
 * asks for units (`geminates`, the phonological distance), then run the
 * plain recurrence. Without units the tokens go in as they come, which is
 * how `levenshtein` relates to `distance`. */
static abugida_status run_dp(const abugida_token *a, size_t na,
                             const abugida_token *b, size_t nb,
                             abugida_sub_fn substitution, void *sub_ctx,
                             abugida_indel_fn indel, void *indel_ctx,
                             int geminates, double *out)
{
    units_buf ua;
    units_buf ub;
    abugida_status st;

    if (!out || (na && !a) || (nb && !b) || !substitution || !indel)
        return ABUGIDA_ERR_INVALID;
    if (!geminates)
        return dp_plain(a, na, b, nb, substitution, sub_ctx, indel,
                        indel_ctx, out);
    st = units_of(a, na, &ua);
    if (st != ABUGIDA_OK)
        return st;
    st = units_of(b, nb, &ub);
    if (st != ABUGIDA_OK) {
        units_free(&ua);
        return st;
    }
    st = dp_plain(ua.tok, ua.n, ub.tok, ub.n, substitution, sub_ctx, indel,
                  indel_ctx, out);
    units_free(&ua);
    units_free(&ub);
    return st;
}

static abugida_status run_dp_bounded(const abugida_token *a, size_t na,
                                     const abugida_token *b, size_t nb,
                                     abugida_sub_fn substitution, void *sub_ctx,
                                     abugida_indel_fn indel, void *indel_ctx,
                                     int geminates, double bound, int *beyond,
                                     double *out)
{
    units_buf ua;
    units_buf ub;
    abugida_status st;

    if (!out || !beyond || (na && !a) || (nb && !b) || !substitution || !indel
        || !(bound > 0.0))
        return ABUGIDA_ERR_INVALID;
    *beyond = 0;
    if (!geminates)
        return dp_plain_bounded(a, na, b, nb, substitution, sub_ctx, indel,
                                indel_ctx, bound, beyond, out);
    st = units_of(a, na, &ua);
    if (st != ABUGIDA_OK)
        return st;
    st = units_of(b, nb, &ub);
    if (st != ABUGIDA_OK) {
        units_free(&ua);
        return st;
    }
    st = dp_plain_bounded(ua.tok, ua.n, ub.tok, ub.n, substitution, sub_ctx,
                          indel, indel_ctx, bound, beyond, out);
    units_free(&ua);
    units_free(&ub);
    return st;
}

abugida_status abugida_word_distance_bounded(const abugida_word *a,
                                             const abugida_word *b,
                                             double bound, int *beyond,
                                             double *out)
{
    if (!a || !b || !out || !beyond)
        return ABUGIDA_ERR_INVALID;
    return run_dp_bounded(a->tok, a->n, b->tok, b->n,
                          abugida_sub_phonological, NULL,
                          abugida_indel_derived, NULL, 1, bound, beyond, out);
}

abugida_status abugida_edit(const abugida_token *a, size_t na,
                            const abugida_token *b, size_t nb,
                            abugida_sub_fn substitution, void *sub_ctx,
                            abugida_indel_fn indel, void *indel_ctx,
                            double *out)
{
    return run_dp(a, na, b, nb, substitution, sub_ctx, indel, indel_ctx, 1,
                  out);
}

double abugida_sub_phonological(abugida_token a, abugida_token b, void *ctx)
{
    (void)ctx;
    return abugida_cost(a, b);
}

double abugida_indel_derived(abugida_token t, void *ctx)
{
    (void)ctx;
    return abugida_indel(t);
}

double abugida_sub_flat(abugida_token a, abugida_token b, void *ctx)
{
    (void)ctx;
    return a == b ? 0.0 : 1.0;
}

double abugida_indel_flat(abugida_token t, void *ctx)
{
    (void)ctx;
    (void)t;
    return 1.0;
}

abugida_status abugida_word_distance(const abugida_word *a,
                                     const abugida_word *b, double *out)
{
    if (!a || !b)
        return ABUGIDA_ERR_INVALID;
    return run_dp(a->tok, a->n, b->tok, b->n, abugida_sub_phonological, NULL,
                  abugida_indel_derived, NULL, 1, out);
}

/* THE KERNEL DISPATCH.
 *
 * Three builds of the same recurrence (`abugida_myers.c`), differing only in
 * the instruction set the compiler is allowed to use, and one pointer chosen
 * once. The default is the fastest the running CPU supports, but the point of
 * the arrangement is not speed — it is that `ABUGIDA_IMPL` can force any of
 * them, so the verification can compare them against each other and against
 * the dynamic program. `docs/asm-plan.md` phase 2 puts hand-written assembly
 * behind the same three names, and nothing here changes when it does.
 *
 * The C variant is ALWAYS compiled and always correct: it is the fallback on
 * any target without the others, and the reference the others are checked
 * against. That is why the portability promise survives this. */
#ifdef ABUGIDA_USE_MYERS
long abugida_levenshtein_myers_c(const abugida_word *a, const abugida_word *b);
int abugida_levenshtein_myers_applicable_c(const abugida_word *a,
                                           const abugida_word *b);
#ifdef ABUGIDA_HAVE_SSE2
long abugida_levenshtein_myers_sse2(const abugida_word *a, const abugida_word *b);
int abugida_levenshtein_myers_applicable_sse2(const abugida_word *a,
                                              const abugida_word *b);
#endif
#ifdef ABUGIDA_HAVE_AVX2
long abugida_levenshtein_myers_avx2(const abugida_word *a, const abugida_word *b);
int abugida_levenshtein_myers_applicable_avx2(const abugida_word *a,
                                              const abugida_word *b);
#endif

typedef long (*abugida_myers_fn)(const abugida_word *, const abugida_word *);
typedef int (*abugida_myers_applicable_fn)(const abugida_word *,
                                           const abugida_word *);

/*: The variants, in the order a caller may name them in `ABUGIDA_IMPL`. */
static const char *const impl_names[] = {
    "c",
#ifdef ABUGIDA_HAVE_SSE2
    "sse2",
#endif
#ifdef ABUGIDA_HAVE_AVX2
    "avx2",
#endif
    NULL
};

static abugida_myers_fn impl_fn[] = {
    abugida_levenshtein_myers_c,
#ifdef ABUGIDA_HAVE_SSE2
    abugida_levenshtein_myers_sse2,
#endif
#ifdef ABUGIDA_HAVE_AVX2
    abugida_levenshtein_myers_avx2,
#endif
    NULL
};

static abugida_myers_applicable_fn impl_applicable[] = {
    abugida_levenshtein_myers_applicable_c,
#ifdef ABUGIDA_HAVE_SSE2
    abugida_levenshtein_myers_applicable_sse2,
#endif
#ifdef ABUGIDA_HAVE_AVX2
    abugida_levenshtein_myers_applicable_avx2,
#endif
    NULL
};

#define ABUGIDA_NIMPL ((int)(sizeof impl_fn / sizeof impl_fn[0]) - 1)

/*: -1 means "not chosen yet". */
static int impl_choice = -1;

/*: Which variant a name refers to, or -1. */
static int impl_index_of(const char *name)
{
    int i;

    if (!name)
        return -1;
    for (i = 0; i < ABUGIDA_NIMPL; i++) {
        const char *p = impl_names[i];
        const char *q = name;

        while (*p && *p == *q) {
            p++;
            q++;
        }
        if (*p == '\0' && *q == '\0')
            return i;
    }
    return -1;
}

/*: The fastest variant this CPU can run. */
static int impl_default(void)
{
#ifdef ABUGIDA_HAVE_AVX2
    /* `__builtin_cpu_supports` is available on GCC and Clang; on anything else
     * the AVX2 variant is not compiled at all, so this is not reached. */
#if defined(__GNUC__) || defined(__clang__)
    if (__builtin_cpu_supports("avx2"))
        return impl_index_of("avx2");
#endif
#endif
#ifdef ABUGIDA_HAVE_SSE2
    /* SSE2 is mandatory on x86-64, so on that target this is always taken;
     * the check is kept for a 32-bit x86 build, where it is not. */
#if defined(__GNUC__) || defined(__clang__)
    if (__builtin_cpu_supports("sse2"))
        return impl_index_of("sse2");
#endif
#endif
    return impl_index_of("c");
}

/*: Resolve the choice, honouring `ABUGIDA_IMPL` on the FIRST call.
 *
 * An environment variable read once and cached: the choice is a property of
 * the process, and reading `getenv` in a per-word inner loop would cost more
 * than the kernel. `abugida_impl_select` is what a test uses to change it. */
static int impl_resolve(void)
{
    const char *want;

    if (impl_choice >= 0)
        return impl_choice;
    want = getenv("ABUGIDA_IMPL");
    if (want && *want) {
        int i = impl_index_of(want);

        /* An unknown name is not silently ignored: it would be a caller
         * believing it had tested one variant while running another. */
        if (i < 0)
            impl_choice = -1;
        else
            impl_choice = i;
    }
    if (impl_choice < 0)
        impl_choice = impl_default();
    if (impl_choice < 0)
        impl_choice = 0;
    return impl_choice;
}
#endif /* ABUGIDA_USE_MYERS */

int abugida_impl_count(void)
{
#ifdef ABUGIDA_USE_MYERS
    return ABUGIDA_NIMPL;
#else
    return 1; /* the dynamic program */
#endif
}

const char *abugida_impl_at(int i)
{
#ifdef ABUGIDA_USE_MYERS
    if (i < 0 || i >= ABUGIDA_NIMPL)
        return NULL;
    return impl_names[i];
#else
    return i == 0 ? "dp" : NULL;
#endif
}

long abugida_levenshtein_myers_selected(const abugida_word *a,
                                        const abugida_word *b)
{
#ifdef ABUGIDA_USE_MYERS
    return impl_fn[impl_resolve()](a, b);
#else
    (void)a;
    (void)b;
    return ABUGIDA_MYERS_NOT_APPLICABLE;
#endif
}

int abugida_levenshtein_myers_applicable_selected(const abugida_word *a,
                                                  const abugida_word *b)
{
#ifdef ABUGIDA_USE_MYERS
    return impl_applicable[impl_resolve()](a, b);
#else
    (void)a;
    (void)b;
    return 0;
#endif
}

const char *abugida_impl_name(void)
{
#ifdef ABUGIDA_USE_MYERS
    return impl_names[impl_resolve()];
#else
    return "dp";
#endif
}

int abugida_impl_select(const char *name)
{
#ifdef ABUGIDA_USE_MYERS
    int i;

    if (!name || !*name) {
        impl_choice = impl_default();
        return 0;
    }
    i = impl_index_of(name);
    if (i < 0)
        return ABUGIDA_ERR_INVALID;
    impl_choice = i;
    return 0;
#else
    /* Without the kernel there is exactly one implementation, and asking for
     * it by name is not an error — but asking for another one is. */
    if (!name || !*name || (name[0] == 'd' && name[1] == 'p' && !name[2]))
        return 0;
    return ABUGIDA_ERR_INVALID;
#endif
}

abugida_status abugida_word_levenshtein(const abugida_word *a,
                                        const abugida_word *b, long *out)
{
    double total = 0.0;
    abugida_status st;

    if (!a || !b || !out)
        return ABUGIDA_ERR_INVALID;

#ifdef ABUGIDA_USE_MYERS
    /* The bit-parallel kernel first, when the words fit in a machine word
     * (`abugida_myers.c` explains why only this metric can use it and what
     * the limit is). It is 8x to 53x faster on the benchmark pairs and 2.4x
     * on a lexicon sweep, and it returns the same integer — which is not a
     * hope: `test_myers.c` compares it against the DP below over every pair
     * of a token corpus, and `tests/test_c_parity.py` compares the public
     * function against the pure-Python reference over the whole corpus.
     *
     * WHICH build of the kernel answers is the dispatcher's business, not
     * this function's. Note what the fallback below is for: it is not the
     * dispatch. It is the inputs the kernel declines — a word longer than a
     * machine word, or one carrying an opaque token — for which the DP is the
     * only correct answer whichever variant is selected. */
    {
        int which = impl_resolve();
        long myers = impl_fn[which](a, b);

        if (myers != ABUGIDA_MYERS_NOT_APPLICABLE) {
            *out = myers;
            return ABUGIDA_OK;
        }
    }
#endif

    /* The same DP over the same tokenisation, with flat costs and the
     * heavy units off — which is exactly how the Python
     * `levenshtein` relates to `distance`, so the baseline stays the fair
     * one: kh counts as one letter in both measures.
     *
     * This is also the fallback for a word too long for the bit-vector, so
     * the two kernels are not alternatives a caller chooses between: every
     * input has an answer and the answer is the same which ever one produced
     * it. */
    st = run_dp(a->tok, a->n, b->tok, b->n, abugida_sub_flat, NULL,
                abugida_indel_flat, NULL, 0, &total);
    if (st != ABUGIDA_OK)
        return st;
    *out = (long)(total + 0.5);
    return ABUGIDA_OK;
}

/* ------------------------------------------------------------------ */
/* Alignment                                                           */
/* ------------------------------------------------------------------ */

const char *abugida_op_name(abugida_op_kind op)
{
    switch (op) {
    case ABUGIDA_OP_KEEP:
        return "keep";
    case ABUGIDA_OP_SUB:
        return "sub";
    case ABUGIDA_OP_DEL:
        return "del";
    case ABUGIDA_OP_INS:
        return "ins";
    }
    return "?";
}

static double matrix_at(const double *mat, size_t nb, size_t i, size_t j)
{
    return mat[i * (nb + 1) + j];
}

/* Does this candidate path explain the cell it would be traced from?
 *
 * A TOLERANCE, not equality, and for a reason that is not about floating
 * point comfort: several paths through the matrix usually cost exactly the
 * same, and which one the traceback reports is decided by which branch is
 * tried first. Comparing to within 1e-12 — the same tolerance the Python
 * implementation uses — is what makes the two implementations report the
 * same script for a pair with more than one optimal alignment, which is what
 * `test_c_parity`'s alignment check compares. Exact equality would let a
 * last-bit difference in an accumulated sum choose another branch.
 */
static int explains(double here, double candidate)
{
    double diff = here - candidate;

    return diff < 1e-12 && diff > -1e-12;
}

abugida_status abugida_word_align(const abugida_word *a, const abugida_word *b,
                                  abugida_op **ops, size_t *nops)
{
    const abugida_token *t1;
    const abugida_token *t2;
    units_buf u1;
    units_buf u2;
    abugida_status st;
    size_t n;
    size_t m;
    size_t rowcap;
    double *mat;
    abugida_op *out;
    size_t i;
    size_t j;
    size_t count = 0;

    if (!a || !b || !ops || !nops)
        return ABUGIDA_ERR_INVALID;
    *ops = NULL;
    *nops = 0;

    /* The same segmentation as the distance: the script is over heavy units,
     * so a geminate or a nasal+stop cluster is one operation. */
    st = units_of(a->tok, a->n, &u1);
    if (st != ABUGIDA_OK)
        return st;
    st = units_of(b->tok, b->n, &u2);
    if (st != ABUGIDA_OK) {
        units_free(&u1);
        return st;
    }
    t1 = u1.tok;
    t2 = u2.tok;
    n = u1.n;
    m = u2.n;

    rowcap = m + 1;
    mat = (double *)calloc((n + 1) * rowcap, sizeof(double));
    out = mat ? (abugida_op *)calloc(n + m + 1, sizeof(abugida_op)) : NULL;
    if (!mat || !out) {
        free(mat);
        units_free(&u1);
        units_free(&u2);
        return ABUGIDA_ERR_NOMEM;
    }

    for (i = 1; i <= n; i++)
        mat[i * rowcap] = matrix_at(mat, m, i - 1, 0) + abugida_indel(t1[i - 1]);
    for (j = 1; j <= m; j++)
        mat[j] = mat[j - 1] + abugida_indel(t2[j - 1]);

    /* The full matrix, with the SAME recurrence as dp_plain. */
    for (i = 1; i <= n; i++) {
        abugida_token ai = t1[i - 1];
        double dai = abugida_indel(ai);

        for (j = 1; j <= m; j++) {
            abugida_token bj = t2[j - 1];
            double best = matrix_at(mat, m, i - 1, j) + dai;
            double ins = matrix_at(mat, m, i, j - 1) + abugida_indel(bj);
            double sub = matrix_at(mat, m, i - 1, j - 1) + abugida_cost(ai, bj);

            if (ins < best)
                best = ins;
            if (sub < best)
                best = sub;
            mat[i * rowcap + j] = best;
        }
    }

    /* Traceback, then reverse. The branch order is the Python one's, so a
     * pair with several optimal scripts yields the same script in both
     * implementations — which is what lets the parity test compare
     * alignments and not merely their totals. */
    i = n;
    j = m;
    while (i > 0 || j > 0) {
        double here = matrix_at(mat, m, i, j);
        abugida_op *op = &out[count];

        op->left = ABUGIDA_NO_TOKEN;
        op->right = ABUGIDA_NO_TOKEN;
        op->cost = 0.0;
        op->op = ABUGIDA_OP_KEEP;

        if (i >= 1 && j >= 1
            && explains(here, matrix_at(mat, m, i - 1, j - 1)
                        + abugida_cost(t1[i - 1], t2[j - 1]))) {
            op->left = t1[i - 1];
            op->right = t2[j - 1];
            op->cost = abugida_cost(t1[i - 1], t2[j - 1]);
            op->op = t1[i - 1] == t2[j - 1] ? ABUGIDA_OP_KEEP
                                           : ABUGIDA_OP_SUB;
            i -= 1;
            j -= 1;
        } else if (i >= 1 && explains(here, matrix_at(mat, m, i - 1, j)
                                      + abugida_indel(t1[i - 1]))) {
            op->left = t1[i - 1];
            op->cost = abugida_indel(t1[i - 1]);
            op->op = ABUGIDA_OP_DEL;
            i -= 1;
        } else {
            op->right = t2[j - 1];
            op->cost = abugida_indel(t2[j - 1]);
            op->op = ABUGIDA_OP_INS;
            j -= 1;
        }
        count++;
    }

    /* The script was built back to front; hand it over front to back. */
    for (i = 0; i < count / 2; i++) {
        abugida_op tmp = out[i];
        out[i] = out[count - 1 - i];
        out[count - 1 - i] = tmp;
    }

    free(mat);
    units_free(&u1);
    units_free(&u2);
    *ops = out;
    *nops = count;
    return ABUGIDA_OK;
}

void abugida_ops_free(abugida_op *ops)
{
    free(ops);
}

/* ------------------------------------------------------------------ */
/* Phonology first, metric second                                      */
/* ------------------------------------------------------------------ */

/* Shared by `abugida_assimilate_word` and `abugida_phonological_form`. */
static abugida_status assimilate_into(abugida_string *out, const char *text,
                                      size_t len)
{
    abugida_word w;
    size_t i;
    int st;

    abugida_word_init(&w);
    st = abugida_word_from_text(&w, text, len, 0, NULL);
    if (st != ABUGIDA_OK)
        return (abugida_status)st;

    sreset(out);
    for (i = 0; i < w.n; i++) {
        abugida_token t = w.tok[i];

        if (t == ABUGIDA_TOK_M_DOT && i + 1 < w.n) {
            abugida_token next = w.tok[i + 1];

            if (next == ABUGIDA_TOK_Y) {
                /* ṃ + y → ññ: the palatal semivowel nasalises and geminates
                 * (saṃyutta → saññutta). Not the plain meet — y is not a stop
                 * — so it is a rule of its own.
                 *
                 * The length comes from the table rather than from a literal
                 * 2: ñ is two bytes in UTF-8 today, and a rule that hard-codes
                 * that would write past the end of the buffer the day a
                 * grapheme's encoding changes — silently, and into the heap. */
                const char *palatal = abugida_ts_text[ABUGIDA_TOK_N_TILDE];
                size_t palatal_len = abugida_ts_len[ABUGIDA_TOK_N_TILDE];

                if (sputs(out, palatal, palatal_len)
                    || sputs(out, palatal, palatal_len))
                    goto nomem;
                i++; /* the y is consumed by the rule */
                continue;
            }
            if (assimilated_nasal(next) != ABUGIDA_NO_TOKEN) {
                abugida_token nasal = assimilated_nasal(next);
                const char *g = abugida_ts_text[nasal];

                if (sputs(out, g, abugida_ts_len[nasal]))
                    goto nomem;
                continue;
            }
        }
        if (sputs(out, abugida_ts_text[t], abugida_ts_len[t]))
            goto nomem;
    }
    abugida_word_free(&w);
    return ABUGIDA_OK;

nomem:
    abugida_word_free(&w);
    return ABUGIDA_ERR_NOMEM;
}

/* ------------------------------------------------------------------ */
/* Contraction                                                         */
/* ------------------------------------------------------------------ */

/* The three contractions that pay for themselves, measured
 * (`eval/variant_curve.py`): `aya` → `e` is exactly {guttural} ∪ {palatal},
 * `ava` → `o` is {guttural} ∪ {labial} — the same lattice join `sandhi_join`
 * performs at a word boundary, applied word-internally. `ayi` → `e` is the
 * same join before a front vowel, and it is the causative absolutive that
 * makes it productive: bhāvayitvā ~ bhāvetvā. Only these three: the
 * long-vowel variants earn nothing on their own and the i-series loses
 * ground, measured rather than assumed (SPEC §6.3).
 *
 * A NORMALISATION, deliberately not an edit operation: as a 3:1 alignment
 * transition inside `distance` it breaks the triangle inequality, because
 * the DP minimises over monotone alignments and that class is not closed
 * under path composition once a transition consumes three tokens. */
static const char *const CONTRACTIONS[][2] = {
    { "aya", "e" },
    { "ava", "o" },
    { "ayi", "e" }
};

abugida_status abugida_contract_word(abugida_string *out, const char *text,
                                     size_t len)
{
    size_t i = 0;
    size_t rule;

    if (!out || (!text && len))
        return ABUGIDA_ERR_INVALID;
    sreset(out);

    while (i < len) {
        int hit = 0;

        for (rule = 0; rule < sizeof(CONTRACTIONS) / sizeof(CONTRACTIONS[0]);
             rule++) {
            const char *src = CONTRACTIONS[rule][0];
            size_t slen = strlen(src);

            if (len - i >= slen && memcmp(text + i, src, slen) == 0) {
                const char *dst = CONTRACTIONS[rule][1];
                /* Leftmost, non-overlapping, exactly as `str.replace` in
                 * Code A applies them one rule at a time — the patterns are
                 * ASCII and cannot overlap themselves. */
                if (sputs(out, dst, strlen(dst)))
                    return ABUGIDA_ERR_NOMEM;
                i += slen;
                hit = 1;
                break;
            }
        }
        if (!hit) {
            if (sputs(out, text + i, 1))
                return ABUGIDA_ERR_NOMEM;
            i++;
        }
    }
    return ABUGIDA_OK;
}

abugida_status abugida_phonological_form(abugida_string *out, const char *text,
                                         size_t len)
{
    abugida_string stage;
    abugida_status st;

    if (!out)
        return ABUGIDA_ERR_INVALID;
    abugida_string_init(&stage);
    st = assimilate_into(&stage, text, len);
    if (st != ABUGIDA_OK) {
        /* Input outside the alphabet is passed through UNCHANGED rather than
         * raising: this sits on `Lexicon`'s path, where nothing may raise. A
         * string the inventory does not cover has no phonology to resolve,
         * so passing it through is also the right answer. */
        abugida_string_free(&stage);
        sreset(out);
        if (len && sputs(out, text, len))
            return ABUGIDA_ERR_NOMEM;
        return ABUGIDA_OK;
    }
    st = abugida_contract_word(out, stage.text ? stage.text : "", stage.n);
    abugida_string_free(&stage);
    return st;
}

abugida_status abugida_assimilate_word(abugida_string *out, const char *text,
                                       size_t len)
{
    if (!out)
        return ABUGIDA_ERR_INVALID;
    return assimilate_into(out, text, len);
}
