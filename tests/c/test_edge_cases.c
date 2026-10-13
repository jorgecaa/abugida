/* The C core under abuse: edge cases, error paths, long inputs, and leaks.
 *
 * `test_abugida.c` checks that the metric is RIGHT. This checks that the
 * library is SOUND — that it does not corrupt the heap, read out of bounds,
 * write to stderr, or leak on any of the paths a caller can reach. Those are
 * different failures, and the second kind is invisible to a correctness
 * suite: a buffer overrun that happens to land in padding passes every
 * numerical check ever written.
 *
 * The leak check is the part worth explaining, because there is no
 * valgrind or sanitizer runtime on every machine that builds this. It uses
 * the allocator instead: glibc's `mallinfo2` and `malloc_trim` report the
 * bytes still held after the work is done. Every loop below runs the same
 * operation many times; if the library leaked per call, the retained bytes
 * would grow with the iteration count. The check is therefore `after` against
 * `before` on a LOOP, not on a single call, which is what makes it sensitive:
 * one forgotten `free` in a warm-up is invisible, the same one per iteration
 * is not.
 *
 *     make -C tests/c check
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "abugida.h"

#if defined(__GLIBC__)
#include <malloc.h>
#define HAVE_MALLINFO 1
#else
#define HAVE_MALLINFO 0
#endif

static int failures;
static int checks;

#define CHECK(cond, ...)                                                   \
    do {                                                                   \
        checks++;                                                          \
        if (!(cond)) {                                                     \
            failures++;                                                    \
            printf("FAIL %s:%d: ", __FILE__, __LINE__);                    \
            printf(__VA_ARGS__);                                           \
            printf("\n");                                                  \
        }                                                                  \
    } while (0)


/* --- the empty and degenerate words ---------------------------------- */

static void test_empty_words(void)
{
    abugida_token a[ABUGIDA_STACK_TOKENS];
    abugida_token b[ABUGIDA_STACK_TOKENS];
    abugida_word wa = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
    abugida_word wb = ABUGIDA_WORD(b, ABUGIDA_STACK_TOKENS);
    double d = -1.0;
    long lev = -1;

    /* Empty input is a word of no tokens, not an error: a caller that
     * normalises and then compares must not have to special-case "". */
    CHECK(abugida_word_from_text(&wa, "", 0, 0, NULL) == ABUGIDA_OK,
          "the empty word failed");
    CHECK(wa.n == 0, "the empty word has %zu tokens", wa.n);

    /* Empty against empty is 0, and empty against a word is its cost in
     * indels. The indel weight of an empty sequence is 0 by summation. */
    CHECK(abugida_word_distance(&wa, &wa, &d) == ABUGIDA_OK && d == 0.0,
          "empty/empty = %g", d);
    CHECK(abugida_word_from_text(&wb, "kamma", 5, 0, NULL) == ABUGIDA_OK,
          "kamma failed");
    CHECK(abugida_word_distance(&wa, &wb, &d) == ABUGIDA_OK && d > 0.0,
          "empty/kamma = %g", d);
    CHECK(abugida_word_levenshtein(&wa, &wb, &lev) == ABUGIDA_OK && lev == 5,
          "levenshtein(empty, kamma) = %ld", lev);

    /* Alignment of two empty words: no operations, and no crash. */
    {
        abugida_op *ops = NULL;
        size_t nops = 999;

        CHECK(abugida_word_align(&wa, &wa, &ops, &nops) == ABUGIDA_OK,
              "aligning two empty words failed");
        CHECK(nops == 0, "empty alignment has %zu operations", nops);
        abugida_ops_free(ops);
    }

    /* A word of only skipped characters is also empty. */
    CHECK(abugida_word_from_text(&wa, "-- '' -", 7, 0, NULL) == ABUGIDA_OK,
          "a word of marks failed");
    CHECK(wa.n == 0, "a word of marks has %zu tokens", wa.n);
}

/* --- the NULL and invalid-argument contract --------------------------- */

static void test_invalid_arguments(void)
{
    abugida_token a[4];
    abugida_word w = ABUGIDA_WORD(a, 4);
    abugida_token out[4];
    abugida_word wout = ABUGIDA_WORD(out, 4);
    double d;
    abugida_op *ops = NULL;
    size_t nops = 0;
    abugida_string s;

    /* Every one of these must return a status, never crash. The header
     * promises it, and a binding that passes a NULL through by accident is
     * exactly the caller that finds out. */
    CHECK(abugida_word_from_text(NULL, "a", 1, 1, NULL) == ABUGIDA_ERR_INVALID,
          "NULL word accepted");
    CHECK(abugida_word_from_text(&w, NULL, 1, 1, NULL) == ABUGIDA_ERR_INVALID,
          "NULL text with a length accepted");
    CHECK(abugida_word_distance(NULL, &w, &d) == ABUGIDA_ERR_INVALID,
          "NULL word in distance");
    CHECK(abugida_word_distance(&w, &w, NULL) == ABUGIDA_ERR_INVALID,
          "NULL out in distance");
    CHECK(abugida_word_levenshtein(&w, &w, NULL) == ABUGIDA_ERR_INVALID,
          "NULL out in levenshtein");
    CHECK(abugida_word_align(&w, &w, NULL, &nops) == ABUGIDA_ERR_INVALID,
          "NULL ops out");
    CHECK(abugida_word_align(&w, &w, &ops, NULL) == ABUGIDA_ERR_INVALID,
          "NULL nops out");
    CHECK(abugida_edit(NULL, 1, NULL, 1, abugida_sub_phonological, NULL,
                       abugida_indel_derived, NULL, &d) == ABUGIDA_ERR_INVALID,
          "NULL sequences in edit");
    CHECK(abugida_edit(a, 0, a, 0, NULL, NULL, abugida_indel_derived, NULL, &d)
              == ABUGIDA_ERR_INVALID, "NULL substitution accepted");
    CHECK(abugida_edit(a, 0, a, 0, abugida_sub_phonological, NULL, NULL, NULL,
                       &d) == ABUGIDA_ERR_INVALID, "NULL indel accepted");
    CHECK(abugida_word_alloc(NULL, 4) == ABUGIDA_ERR_INVALID,
          "NULL word in alloc");
    CHECK(abugida_diagnose(NULL, 0, NULL, NULL, 0, &nops)
              == ABUGIDA_ERR_INVALID, "NULL text in diagnose");
    CHECK(abugida_diagnose("a", 1, NULL, NULL, 0, NULL)
              == ABUGIDA_ERR_INVALID, "NULL n in diagnose");

    /* Freeing things that were never allocated must be a no-op, because
     * that is what a caller error looks like from inside. */
    abugida_word_free(NULL);
    abugida_ops_free(NULL);
    abugida_string_free(NULL);
    abugida_string_init(NULL);
    abugida_word_init(NULL);
    CHECK(1, "freeing NULL crashed");

    /* A word with a zero-capacity caller buffer: the library allocates. */
    abugida_word_init(&wout);
    CHECK(abugida_word_from_text(&wout, "kamma", 5, 0, NULL) == ABUGIDA_OK,
          "tokenising into a heap word failed");
    CHECK(wout.n == 5, "heap word has %zu tokens", wout.n);
    abugida_word_free(&wout);

    /* Double free is safe by the documented contract. */
    abugida_word_free(&wout);
    abugida_word_init(&wout);
    abugida_string_init(&s);
    CHECK(abugida_string_alloc(&s, 8) == ABUGIDA_OK, "string_alloc failed");
    abugida_string_free(&s);
    abugida_string_free(&s);
    CHECK(1, "double free crashed");
}

/* --- a word longer than the stack buffer ------------------------------ */

static void test_long_words(void)
{
    /* 500 tokens: past ABUGIDA_STACK_TOKENS, so both the tokeniser and the DP
     * take their heap paths. The two must agree with the stack path, so the
     * same word is scored against a truncated copy and checked for the
     * properties that hold regardless of length. */
    /* 600 characters of `ka`, which tokenises one token per character, so
     * the token count is the character count and the heap path is reached
     * with a length the test can state exactly. A word spelled from digraphs
     * would be shorter in tokens than in characters — which is why the
     * assertion below is about tokens and the constant is named for them. */
    enum { LONG_CHARS = 600 };
    char *long_word = (char *)malloc(LONG_CHARS + 1);
    abugida_token a[ABUGIDA_STACK_TOKENS];
    abugida_word w;
    double d = -1.0;
    size_t i;
    abugida_op *ops = NULL;
    size_t nops = 0;
    double total = 0.0;

    CHECK(long_word != NULL, "out of memory in the test");
    if (!long_word)
        return;
    for (i = 0; i < LONG_CHARS; i++)
        long_word[i] = (i % 2) ? 'a' : 'k';
    long_word[LONG_CHARS] = '\0';

    abugida_word_init(&w);
    CHECK(abugida_word_from_text(&w, long_word, LONG_CHARS, 1, NULL)
              == ABUGIDA_OK, "a %d-token word failed", (int)LONG_CHARS);
    CHECK(w.n == LONG_CHARS, "expected %d tokens, got %zu",
          (int)LONG_CHARS, w.n);
    CHECK(w.heap, "a %d-token word is not on the heap", (int)LONG_CHARS);

    /* Identity, and the two views agreeing, on the heap path. */
    CHECK(abugida_word_distance(&w, &w, &d) == ABUGIDA_OK && d == 0.0,
          "the long word is not 0 from itself: %g", d);
    CHECK(abugida_word_align(&w, &w, &ops, &nops) == ABUGIDA_OK,
          "aligning the long word failed");
    CHECK(nops == LONG_CHARS, "%d keeps expected, got %zu",
          (int)LONG_CHARS, nops);
    for (i = 0; i < nops; i++)
        total += ops[i].cost;
    abugida_ops_free(ops);
    abugida_word_distance(&w, &w, &d);
    CHECK(total == d, "the long alignment sums to %g, distance %g", total, d);

    /* And against the caller's stack buffer, which is too small: the
     * library must take over rather than truncate. */
    {
        abugida_word small = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);

        CHECK(abugida_word_from_text(&small, long_word, LONG_CHARS, 1, NULL)
                  == ABUGIDA_OK, "a long word into a small buffer failed");
        CHECK(small.n == LONG_CHARS, "truncated to %zu tokens", small.n);
        CHECK(small.heap, "the library did not take ownership");
        abugida_word_free(&small);
    }
    abugida_word_free(&w);
    free(long_word);
}

/* --- truncated and invalid UTF-8 ------------------------------------- */

static void test_broken_utf8(void)
{
    abugida_token a[ABUGIDA_STACK_TOKENS];
    abugida_word w = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
    /* A lead byte with no continuation, a bare continuation, an overlong
     * sequence, and a lead byte truncated at the end of the buffer. Each is
     * fed with an explicit length, so none of them is NUL-terminated where it
     * matters: the scanner must not read past `len`. */
    static const char *const broken[] = {
        "\xe1\xb9",          /* ṭ truncated: 2 of 3 bytes */
        "\xe1",              /* a bare lead byte */
        "\xb9\xad",          /* continuation bytes with no lead */
        "\xc4",              /* ā truncated: 1 of 2 bytes */
        "\xe1\xb9\xad\xe1",  /* a good grapheme then a truncated one */
    };
    size_t i;
    size_t off;
    abugida_status st;

    for (i = 0; i < sizeof(broken) / sizeof(broken[0]); i++) {
        size_t len = strlen(broken[i]);

        st = abugida_word_from_text(&w, broken[i], len, 0, &off);
        CHECK(st == ABUGIDA_ERR_NOT_PALI || st == ABUGIDA_ERR_SANSKRIT,
              "broken UTF-8 %zu was accepted (status %d)", i, (int)st);
        CHECK(off <= len, "offset %zu past the %zu-byte input", off, len);
        /* Lenient must absorb it: every byte of a character the inventory
         * does not know becomes one opaque token, and every character it DOES
         * know stays a grapheme. So the token count is the number of bytes
         * minus whatever the valid characters saved — never zero, never more
         * than the byte count. */
        st = abugida_word_from_text(&w, broken[i], len, 1, NULL);
        CHECK(st == ABUGIDA_OK, "lenient rejected broken UTF-8 %zu", i);
        CHECK(w.n > 0 && w.n <= len,
              "lenient gave %zu tokens for %zu bytes", w.n, len);
    }

    /* A NUL inside the text is a character like any other, not a terminator:
     * `len` is authoritative. */
    {
        static const char with_nul[] = { 'k', 'a', '\0', 'm', 'a' };

        st = abugida_word_from_text(&w, with_nul, sizeof(with_nul), 1, NULL);
        CHECK(st == ABUGIDA_OK, "a NUL inside the word failed");
        CHECK(w.n == 5, "a NUL split the word into %zu tokens", w.n);
    }
}

/* --- diagnose --------------------------------------------------------- */

static void test_diagnose_contract(void)
{
    size_t offs[8];
    int kinds[8];
    size_t n = 999;
    size_t i;
    abugida_status st;

    /* Fewer slots than problems: the count is the number FOUND, not the
     * number stored, and nothing is written past `cap`. The arrays are
     * poisoned first, because "nothing was written" is only observable
     * against a known value. */
    for (i = 0; i < 8; i++) {
        offs[i] = (size_t)-1;
        kinds[i] = -1;
    }
    /* Five, not six: the scanner offers the pair ("r","x") to the grapheme
     * table first, that fails, and then reports `r` and `x` separately — so
     * every character of "qrx*?!" is one problem and the count is its
     * length. (A pair that DID match would be one character and save a
     * report; "kh" below is that case.) */
    st = abugida_diagnose("qrx*?!", 6, offs, kinds, 2, &n);
    CHECK(st == ABUGIDA_OK, "diagnose failed");
    CHECK(n == 5, "found %zu problems, expected 5", n);
    for (i = 0; i < 8; i++)
        CHECK(i < 2 || (offs[i] == (size_t)-1 && kinds[i] == -1),
              "diagnose wrote past cap at %zu (offset %zu, kind %d)", i,
              offs[i], kinds[i]);
    /* The offsets are 0 and 2, not 0 and 1, and the gap is a real property
     * of the reported set: the reference implementation offers the PAIR
     * ("r","x") to the grapheme table, that fails, reports the character at
     * the SECOND position of the pair, and skips past both. So `r` — a
     * perfectly good grapheme — goes unreported between two problems. The C
     * core reproduces it because `tests/test_c_parity.py` compares `diagnose`
     * against an independent re-implementation of the rule; whether the rule
     * is what a user wants is a separate question, and not one a port gets to
     * answer. */
    CHECK(offs[0] == 0 && offs[1] == 2, "the first two offsets are %zu, %zu",
          offs[0], offs[1]);

    /* A clean word reports nothing, and every grapheme is walked whole: a
     * two-byte grapheme is one character, not two problems. */
    st = abugida_diagnose("aṭṭha", strlen("aṭṭha"), offs, kinds, 8, &n);
    CHECK(st == ABUGIDA_OK && n == 0, "aṭṭha reported %zu problems", n);
    st = abugida_diagnose("kh", 2, offs, kinds, 8, &n);
    CHECK(st == ABUGIDA_OK && n == 0, "the digraph kh reported %zu problems",
          n);
    /* …and a digraph whose second character is the problem reports only that
     * one. */
    st = abugida_diagnose("kq", 2, offs, kinds, 8, &n);
    CHECK(st == ABUGIDA_OK && n == 1 && offs[0] == 1,
          "kq reported %zu problems at %zu", n, n ? offs[0] : 0);
    /* The Sanskrit phonemes, and the vocalic ṝ. */
    st = abugida_diagnose("kṛṣṇa", strlen("kṛṣṇa"), offs, kinds, 8, &n);
    CHECK(st == ABUGIDA_OK && n == 2, "kṛṣṇa reported %zu problems", n);
    if (n == 2)
        CHECK(kinds[0] == 1 && kinds[1] == 1, "kṛṣṇa kinds are %d/%d",
              kinds[0], kinds[1]);
}

/* --- the alignment's shape ------------------------------------------- */

static void test_alignment_invariants(void)
{
    /* Every operation must consume at least one token from one side and at
     * most two, and the script must account for exactly both words. A
     * traceback that walked off the end would show up as a token count that
     * does not add up, which is a much better check than "it did not crash". */
    static const char *const pairs[][2] = {
        { "attha", "atha" },        /* unit against single */
        { "attha", "atthā" },       /* plus vowel length */
        { "magga", "makka" },       /* unit against unit */
        { "gacchati", "gacchanti" },/* single against cluster */
        { "kamma", "khamma" },      /* substitution */
        { "a", "ā" },
        { "a", "kamma" },
        { "kamma", "a" },
        { "saṅgha", "saṃsāra" },
        { "aṭṭha", "aṭha" },
    };
    size_t p;

    for (p = 0; p < sizeof(pairs) / sizeof(pairs[0]); p++) {
        abugida_word a;
        abugida_word b;
        abugida_op *ops = NULL;
        size_t nops = 0;
        size_t i;
        size_t ate = 0;
        size_t bte = 0;
        double total = 0.0;
        double d = 0.0;

        abugida_word_init(&a);
        abugida_word_init(&b);
        if (abugida_word_from_text(&a, pairs[p][0], strlen(pairs[p][0]), 0,
                                   NULL) != ABUGIDA_OK)
            continue;
        if (abugida_word_from_text(&b, pairs[p][1], strlen(pairs[p][1]), 0,
                                   NULL) != ABUGIDA_OK)
            continue;
        CHECK(abugida_word_align(&a, &b, &ops, &nops) == ABUGIDA_OK,
              "%s/%s align failed", pairs[p][0], pairs[p][1]);
        for (i = 0; i < nops; i++) {
            size_t left = ops[i].left == ABUGIDA_NO_TOKEN ? 0 : 1;
            size_t right = ops[i].right == ABUGIDA_NO_TOKEN ? 0 : 1;

            /* A long token on either side is TWO tokens of the word. */
            if (left && ops[i].left >= ABUGIDA_NPLAIN)
                left = 2;
            if (right && ops[i].right >= ABUGIDA_NPLAIN)
                right = 2;
            CHECK(left + right > 0, "%s/%s: an operation consumed nothing",
                  pairs[p][0], pairs[p][1]);
            ate += left;
            bte += right;
            total += ops[i].cost;
        }
        abugida_word_distance(&a, &b, &d);
        CHECK(ate == a.n, "%s/%s: the script consumed %zu of %zu tokens",
              pairs[p][0], pairs[p][1], ate, a.n);
        CHECK(bte == b.n, "%s/%s: the script consumed %zu of %zu tokens",
              pairs[p][0], pairs[p][1], bte, b.n);
        CHECK(total == d, "%s/%s: script sums to %g, distance %g",
              pairs[p][0], pairs[p][1], total, d);
        abugida_ops_free(ops);
        abugida_word_free(&a);
        abugida_word_free(&b);
    }
}

/* --- leaks ------------------------------------------------------------ */

#if HAVE_MALLINFO
static size_t retained_bytes(void)
{
    struct mallinfo2 info = mallinfo2();

    return info.uordblks;
}

static void test_no_leaks(void)
{
    /* Each block runs its operation enough times that a per-call leak is
     * unmistakable, and trims first so the measurement is of what the
     * library holds and not of the allocator's arenas. */
    static const int ITERATIONS = 2000;
    size_t before;
    size_t after;
    int i;

    /* Warm-up: the first call allocates the scratch the free store keeps. */
    for (i = 0; i < 64; i++) {
        abugida_token a[64];
        abugida_word w = ABUGIDA_WORD(a, 64);

        abugida_word_from_text(&w, "saṃghassa", 9, 1, NULL);
    }
    malloc_trim(0);
    before = retained_bytes();

    for (i = 0; i < ITERATIONS; i++) {
        abugida_token a[ABUGIDA_STACK_TOKENS];
        abugida_word wa = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
        abugida_op *ops = NULL;
        size_t nops = 0;
        double d;

        /* Tokenisation into a caller buffer. */
        abugida_word_from_text(&wa, "saṃghassa", 9, 0, NULL);
        /* Tokenisation that GROWS the buffer (a long word into a small one). */
        {
            abugida_token small[2];
            abugida_word sw = ABUGIDA_WORD(small, 2);

            abugida_word_from_text(&sw, "abhidhammapiṭaka", 16, 0, NULL);
            abugida_word_free(&sw);
        }
        /* A failed tokenisation must free whatever it allocated on the way. */
        abugida_word_from_text(&wa, "kṛṣṇakṛṣṇa", 10, 0, NULL);
        /* The DP, and the alignment. */
        {
            abugida_token b[ABUGIDA_STACK_TOKENS];
            abugida_word wb = ABUGIDA_WORD(b, ABUGIDA_STACK_TOKENS);

            abugida_word_from_text(&wb, "saṅghassa", 9, 0, NULL);
            abugida_word_distance(&wa, &wb, &d);
            abugida_word_levenshtein(&wa, &wb, (long *)&nops);
            abugida_word_align(&wa, &wb, &ops, &nops);
            abugida_ops_free(ops);
        }
        /* diagnose, with and without room for the answers. */
        {
            size_t offs[2];
            int kinds[2];
            size_t found;

            abugida_diagnose("kṛṣṇaq*", 10, offs, kinds, 2, &found);
        }
        abugida_word_free(&wa);
    }

    malloc_trim(0);
    after = retained_bytes();
    /* A leak of one malloc per iteration would show as at least
     * ITERATIONS * 16 bytes. Allow a small slack for allocator bookkeeping
     * that `malloc_trim` cannot return, but nothing proportional to the
     * loop. */
    CHECK(after <= before + 4096,
          "%d iterations retained %zu bytes (before %zu, after %zu)",
          ITERATIONS, after > before ? after - before : 0, before, after);
}
#else
static void test_no_leaks(void)
{
    printf("  (no mallinfo2 on this platform: leak check skipped)\n");
}
#endif

/* --- the pipeline, under abuse --------------------------------------- */

static void test_pipeline_edge_cases(void)
{
    abugida_string s;
    abugida_status st;

    abugida_string_init(&s);
    /* A string the inventory does not cover passes through unchanged rather
     * than failing, because this runs on Lexicon's path. */
    st = abugida_phonological_form(&s, "kṛṣṇa", 9);
    CHECK(st == ABUGIDA_OK, "phonological_form refused Sanskrit");
    CHECK(s.n == 9 && memcmp(s.text, "kṛṣṇa", 9) == 0,
          "phonological_form altered it to %.*s", (int)s.n, s.text);

    /* Empty in, empty out — no allocation failure, no stale bytes. */
    st = abugida_assimilate_word(&s, "", 0);
    CHECK(st == ABUGIDA_OK && s.n == 0, "assimilate of nothing: %zu", s.n);
    st = abugida_contract_word(&s, "", 0);
    CHECK(st == ABUGIDA_OK && s.n == 0, "contract of nothing: %zu", s.n);

    /* Reuse of the same output across calls must not accumulate. */
    abugida_assimilate_word(&s, "saṃgha", 8);
    CHECK(s.n == 8 && strcmp(s.text, "saṅgha") == 0, "assimilate: %s", s.text);
    abugida_assimilate_word(&s, "sakiṃ", 7);
    CHECK(s.n == 7 && strcmp(s.text, "sakiṃ") == 0,
          "the second call did not reset: %s", s.text);

    /* A niggahita at the very end, and a run of them. */
    abugida_assimilate_word(&s, "saṃ", 5);
    CHECK(strcmp(s.text, "saṃ") == 0, "trailing ṃ: %s", s.text);
    /* ṃ followed by ṃ: the first stays (there is no stop after it to select
     * a place), and the second resolves against the gh. The pure-Python
     * reference returns the same string — this is the rule, not a slip. */
    abugida_assimilate_word(&s, "saṃṃgha", strlen("saṃṃgha"));
    CHECK(strcmp(s.text, "saṃṅgha") == 0, "double ṃ: %s", s.text);

    /* Contraction at the boundaries of the word. */
    abugida_contract_word(&s, "aya", 3);
    CHECK(strcmp(s.text, "e") == 0, "leading aya: %s", s.text);
    abugida_contract_word(&s, "ava", 3);
    CHECK(strcmp(s.text, "o") == 0, "leading ava: %s", s.text);
    abugida_contract_word(&s, "ayi", 3);
    CHECK(strcmp(s.text, "e") == 0, "leading ayi: %s", s.text);
    abugida_contract_word(&s, "kaya", 4);
    CHECK(strcmp(s.text, "ke") == 0, "kaya: %s", s.text);

    abugida_string_free(&s);
}

/* --- scoring is symmetric and bounded, on the awkward words ----------- */

static void test_properties_on_awkward_words(void)
{
    static const char *const words[] = {
        "", "a", "ā", "ṃ", "kamma", "khamma", "attha", "atha", "saṃgha",
        "aṭṭha", "vikkhambhati", "abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ",
        "--", "a-ṭ-ṭha",
    };
    size_t i;
    size_t j;

    for (i = 0; i < sizeof(words) / sizeof(words[0]); i++) {
        abugida_token a[ABUGIDA_STACK_TOKENS];
        abugida_word wa = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
        double d = -1.0;

        CHECK(abugida_word_from_text(&wa, words[i], strlen(words[i]), 1, NULL)
                  == ABUGIDA_OK, "lenient refused %s", words[i]);
        /* Identity holds for every input, including the empty one. */
        CHECK(abugida_word_distance(&wa, &wa, &d) == ABUGIDA_OK && d == 0.0,
              "%s is %g from itself", words[i], d);
        /* Symmetry holds for every input too. */
        for (j = 0; j < sizeof(words) / sizeof(words[0]); j++) {
            abugida_token b[ABUGIDA_STACK_TOKENS];
            abugida_word wb = ABUGIDA_WORD(b, ABUGIDA_STACK_TOKENS);
            double dij = -1.0;
            double dji = -1.0;

            abugida_word_from_text(&wb, words[j], strlen(words[j]), 1, NULL);
            abugida_word_distance(&wa, &wb, &dij);
            abugida_word_distance(&wb, &wa, &dji);
            CHECK(dij == dji, "%s/%s asymmetric: %g against %g", words[i],
                  words[j], dij, dji);
        }
    }
}

/* The triangle inequality, over words WITH heavy units.
 *
 * Until the heavy units it did not hold, and this file pinned the failure:
 * the DP let each comparison decide whether a doubled pair was one long
 * consonant or two letters, and a middle word read both ways made the detour
 * cheaper than the direct path —
 *
 *     d("makka", "saṅgha") = 2.262374
 *       > d("makka", "magga") + d("magga", "saṅgha") = 2.064786
 *
 * Now every word is segmented ONCE (geminates and homorganic nasal+stop
 * clusters are single tokens) and the DP is plain substitution and indel, so
 * the inequality follows from three token-level conditions the Python suite
 * verifies exhaustively (the cost's triangle over every token, and the two
 * cost/indel conditions over every pair). The words below are chosen to
 * exercise exactly what used to break: geminates, clusters, a geminate
 * against a cluster, degemination, and the empty word.
 */
static void test_triangle_with_units(void)
{
    static const char *const words[] = {
        "", "makka", "magga", "saṅgha", "saṃgha", "citta", "cinta",
        "attha", "atha", "gacchati", "gacchanti", "kamma", "khandha",
        "kāma", "kata", "gata", "tatra", "yoga", "chanda", "puñña",
    };
    size_t nw = sizeof(words) / sizeof(words[0]);
    size_t i;
    size_t j;
    size_t k;

    for (i = 0; i < nw; i++) {
        for (j = 0; j < nw; j++) {
            abugida_token a[ABUGIDA_STACK_TOKENS];
            abugida_token b[ABUGIDA_STACK_TOKENS];
            abugida_word wa = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
            abugida_word wb = ABUGIDA_WORD(b, ABUGIDA_STACK_TOKENS);
            double dij;
            double dji;

            abugida_word_from_text(&wa, words[i], strlen(words[i]), 0, NULL);
            abugida_word_from_text(&wb, words[j], strlen(words[j]), 0, NULL);
            abugida_word_distance(&wa, &wb, &dij);
            abugida_word_distance(&wb, &wa, &dji);
            CHECK(dij == dji, "%s/%s asymmetric: %g against %g", words[i],
                  words[j], dij, dji);

            for (k = 0; k < nw; k++) {
                abugida_token c[ABUGIDA_STACK_TOKENS];
                abugida_word wc = ABUGIDA_WORD(c, ABUGIDA_STACK_TOKENS);
                double dik;
                double dkj;

                abugida_word_from_text(&wc, words[k], strlen(words[k]), 0,
                                       NULL);
                abugida_word_distance(&wa, &wc, &dik);
                abugida_word_distance(&wc, &wb, &dkj);
                CHECK(dij <= dik + dkj + 1e-12,
                      "triangle %s/%s/%s: %g > %g", words[i], words[j],
                      words[k], dij, dik + dkj);
            }
        }
    }
}

/* The old counterexample, now satisfied, with its legs pinned to the
 * pure-Python values (`repr()` of each; the parity test requires the C core
 * to reproduce them bit for bit, while a sum of two doubles is not something
 * to assert to the last bit). */
static void test_the_old_counterexample(void)
{
    abugida_token a[ABUGIDA_STACK_TOKENS];
    abugida_token b[ABUGIDA_STACK_TOKENS];
    abugida_token c[ABUGIDA_STACK_TOKENS];
    abugida_word wa = ABUGIDA_WORD(a, ABUGIDA_STACK_TOKENS);
    abugida_word wb = ABUGIDA_WORD(b, ABUGIDA_STACK_TOKENS);
    abugida_word wc = ABUGIDA_WORD(c, ABUGIDA_STACK_TOKENS);
    double direct;
    double leg1;
    double leg2;

    abugida_word_from_text(&wa, "makka", 5, 0, NULL);
    abugida_word_from_text(&wb, "saṅgha", strlen("saṅgha"), 0, NULL);
    abugida_word_from_text(&wc, "magga", 5, 0, NULL);
    abugida_word_distance(&wa, &wb, &direct);
    abugida_word_distance(&wa, &wc, &leg1);
    abugida_word_distance(&wc, &wb, &leg2);
    CHECK(leg1 == 0.46973812807925769,
          "d(makka, magga) = %.17g, expected the pinned value", leg1);
    CHECK(leg2 == 1.3438980705772967,
          "d(magga, saṅgha) = %.17g, expected the pinned value", leg2);
    CHECK(direct == 1.6311868552439219,
          "d(makka, saṅgha) = %.17g, expected the pinned value", direct);
    CHECK(direct <= leg1 + leg2 + 1e-12,
          "the old counterexample violates again: %g > %g", direct,
          leg1 + leg2);
}

int main(void)
{
    printf("abugida C core — abuse suite (ABI %d)\n",
           ABUGIDA_TABLES_ABI_VERSION);

    test_empty_words();
    test_invalid_arguments();
    test_long_words();
    test_broken_utf8();
    test_diagnose_contract();
    test_alignment_invariants();
    test_pipeline_edge_cases();
    test_properties_on_awkward_words();
    test_triangle_with_units();
    test_the_old_counterexample();
    test_no_leaks();

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
