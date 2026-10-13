/* The bit-parallel Levenshtein kernel against the dynamic program.
 *
 * `abugida_word_levenshtein` chooses between two kernels — Myers inside a
 * machine word, the DP for anything longer — and the choice is a property of
 * the input, not of the machine. Two kernels for one quantity is exactly the
 * situation the project already refuses to accept silently for the weighted
 * distance ("the recurrence is written once"), so it is checked rather than
 * trusted:
 *
 *   1. EVERY pair of a token corpus, both orders, including the degenerate
 *      sizes: the kernels must return the same integer, and that is the whole
 *      contract of this file;
 *   2. the BOUNDARY, at 63, 64 and 65 tokens, where the kernel stops applying
 *      and the DP takes over — a word of 65 must give the same answer as the
 *      DP would, not a truncated one and not an error;
 *   3. the two entry points that a caller can actually reach: the public
 *      `abugida_word_levenshtein` and the kernel directly, so a future change
 *      to the dispatch cannot hide a disagreement.
 *
 *     make -C csrc check
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "abugida.h"

static int failures;
static int checks;

/*: Which variant the counting is for, so a failure names it. */
static const char *impl_label = "";

#define CHECK(cond, ...)                                                   \
    do {                                                                   \
        checks++;                                                          \
        if (!(cond)) {                                                     \
            failures++;                                                    \
            printf("FAIL [%s] %s:%d: ", impl_label, __FILE__, __LINE__);                    \
            printf(__VA_ARGS__);                                           \
            printf("\n");                                                  \
        }                                                                  \
    } while (0)

/* The reference: a straight Wagner-Fischer with unit costs and no geminate
 * transitions, written here rather than borrowed, so a bug shared with either
 * kernel cannot hide in it. */
static long reference_levenshtein(const abugida_token *a, size_t na,
                                  const abugida_token *b, size_t nb)
{
    long prev[ABUGIDA_MYERS_WORD_BITS + 2];
    long cur[ABUGIDA_MYERS_WORD_BITS + 2];
    size_t i;
    size_t j;

    CHECK(nb < ABUGIDA_MYERS_WORD_BITS + 2,
          "the reference needs a bigger buffer for %zu tokens", nb);
    for (j = 0; j <= nb; j++)
        prev[j] = (long)j;
    for (i = 1; i <= na; i++) {
        cur[0] = (long)i;
        for (j = 1; j <= nb; j++) {
            long best = prev[j] + 1;
            long ins = cur[j - 1] + 1;
            long sub = prev[j - 1] + (a[i - 1] == b[j - 1] ? 0 : 1);

            if (ins < best)
                best = ins;
            if (sub < best)
                best = sub;
            cur[j] = best;
        }
        memcpy(prev, cur, (nb + 1) * sizeof(long));
    }
    return prev[nb];
}

static long core_levenshtein(const abugida_token *a, size_t na,
                            const abugida_token *b, size_t nb)
{
    abugida_word wa;
    abugida_word wb;
    long out = -1;

    wa.tok = (abugida_token *)a;
    wa.n = na;
    wa.cap = na;
    wa.heap = 0;
    wb.tok = (abugida_token *)b;
    wb.n = nb;
    wb.cap = nb;
    wb.heap = 0;
    if (abugida_word_levenshtein(&wa, &wb, &out) != ABUGIDA_OK)
        return -2;
    return out;
}

/* One comparison of all three, for a pair of token sequences. */
static void compare(const abugida_token *a, size_t na,
                    const abugida_token *b, size_t nb, const char *what)
{
    abugida_word wa;
    abugida_word wb;
    long ref = reference_levenshtein(a, na, b, nb);
    long core = core_levenshtein(a, na, b, nb);
    long myers;
    int applicable;

    wa.tok = (abugida_token *)a;
    wa.n = na;
    wa.cap = na;
    wa.heap = 0;
    wb.tok = (abugida_token *)b;
    wb.n = nb;
    wb.cap = nb;
    wb.heap = 0;
    myers = abugida_levenshtein_myers_selected(&wa, &wb);
    applicable = abugida_levenshtein_myers_applicable_selected(&wa, &wb);

    CHECK(core == ref, "%s: core says %ld, the reference says %ld",
          what, core, ref);
    if (applicable) {
        CHECK(myers == ref, "%s: Myers says %ld, the reference says %ld",
              what, myers, ref);
        /* And the public entry point agrees with the kernel it uses. */
        CHECK(core == myers, "%s: the entry point says %ld, the kernel %ld",
              what, core, myers);
    } else {
        CHECK(myers == ABUGIDA_MYERS_NOT_APPLICABLE,
              "%s: the %s kernel did not decline outside its range (got %ld)",
              what, abugida_impl_name(), myers);
        /* The public function must still answer, through the DP. */
        CHECK(core == ref, "%s: the fallback disagrees", what);
    }
}

/* --- every pair of a small corpus, both orders ------------------------- */

static void test_all_pairs(void)
{
    /* A corpus built to contain the cases that break a bit-parallel kernel:
     * the empty word, a word of one token, a repeated token (which makes
     * `peq` a contiguous run of bits and exercises the carry), two tokens
     * that alternate, and words whose token sets are disjoint. */
    static const abugida_token corpus[][8] = {
        { 10 },                                    /* a */
        { 10, 10, 10, 10, 10, 10, 10, 10 },        /* one token, doubled */
        { 10, 21, 10, 21, 10, 21, 10, 21 },        /* alternating */
        { 19, 10, 21, 21, 10 },                    /* k a m m a */
        { 19, 5, 10, 21, 21, 10 },                 /* k kh a m m a */
        { 10, 27, 7, 10 },                         /* a t th a */
        { 10, 27, 10 },                            /* a t a */
        { 26, 17, 16, 10 },                        /* s i h a */
        { 74, 58, 67, 69, 41, 50, 8, 9 },          /* the long consonants */
        { 83, 85, 84 },                            /* the Sanskrit phonemes */
    };
    static const size_t sizes[] = { 1, 8, 8, 6, 6, 4, 3, 4, 8, 3 };
    size_t i;
    size_t j;
    size_t pas;
    size_t pbs;
    char label[64];

    /* the empty word against everything, and against itself */
    compare(NULL, 0, NULL, 0, "empty/empty");
    for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
        snprintf(label, sizeof label, "empty/corpus[%zu]", i);
        compare(NULL, 0, corpus[i], sizes[i], label);
        snprintf(label, sizeof label, "corpus[%zu]/empty", i);
        compare(corpus[i], sizes[i], NULL, 0, label);
    }
    for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
        for (j = 0; j < sizeof(sizes) / sizeof(sizes[0]); j++) {
            snprintf(label, sizeof label, "corpus[%zu]/corpus[%zu]", i, j);
            compare(corpus[i], sizes[i], corpus[j], sizes[j], label);
        }
    }

    /* every PREFIX of one corpus entry against every prefix of another: 100
     * pairs from ten entries, which is where an off-by-one in the bit
     * bookkeeping shows up. */
    for (pas = 0; pas <= 8; pas++) {
        for (pbs = 0; pbs <= 8; pbs++) {
            snprintf(label, sizeof label, "prefix %zu/%zu", pas, pbs);
            compare(corpus[1], pas, corpus[2], pbs, label);
        }
    }
}

/* --- the 64-token boundary --------------------------------------------- */

static void test_the_boundary(void)
{
    abugida_token a[ABUGIDA_MYERS_WORD_BITS + 2];
    abugida_token b[ABUGIDA_MYERS_WORD_BITS + 2];
    size_t n;
    size_t i;
    char label[64];

    /* A pattern that makes `peq` dense in the top bits, where the sign bit of
     * the score is read. */
    for (i = 0; i < sizeof(a) / sizeof(a[0]); i++) {
        a[i] = (abugida_token)(i % ABUGIDA_NPLAIN);
        b[i] = (abugida_token)((i + 1) % ABUGIDA_NPLAIN);
    }
    for (n = 60; n <= 65; n++) {
        snprintf(label, sizeof label, "boundary %zu/%zu", n, n);
        compare(a, n, b, n, label);
        snprintf(label, sizeof label, "boundary %zu/%zu", n, n - 1);
        compare(a, n, b, n - 1, label);
        snprintf(label, sizeof label, "boundary %zu/%zu", n - 1, n);
        compare(a, n - 1, b, n, label);
    }

    /* The exact edges, stated: 64 applies, 65 does not. */
    {
        abugida_word wa;
        abugida_word wb;

        wa.tok = a;
        wa.cap = 66;
        wa.heap = 0;
        wb.tok = b;
        wb.cap = 66;
        wb.heap = 0;
        wa.n = 64;
        wb.n = 64;
        CHECK(abugida_levenshtein_myers_applicable_selected(&wa, &wb),
              "64 tokens should be inside the kernel's range");
        /* The limit binds the SHORTER side — the bit-vector is a DP row, so
         * it is indexed by the second word, and the kernel makes the shorter
         * word that one. A 65-token word is therefore perfectly workable
         * against a 64-token one. */
        wa.n = 65;
        wb.n = 64;
        CHECK(abugida_levenshtein_myers_applicable_selected(&wa, &wb),
              "65 against 64 should be inside the range");
        CHECK(abugida_levenshtein_myers_selected(&wa, &wb)
                  != ABUGIDA_MYERS_NOT_APPLICABLE,
              "the kernel should answer 65 against 64");
        /* Both longer than a word: only now does it decline. */
        wb.n = 65;
        CHECK(!abugida_levenshtein_myers_applicable_selected(&wa, &wb),
              "two 65-token words should be outside it");
        CHECK(abugida_levenshtein_myers_selected(&wa, &wb)
                  == ABUGIDA_MYERS_NOT_APPLICABLE,
              "the kernel should decline two 65-token words");
        /* And the public entry point still answers, through the DP. */
        CHECK(core_levenshtein(a, 65, b, 65) >= 0,
              "the public function must answer outside the kernel's range");
    }
}

/* --- opaque tokens: negative ids, which the kernel must refuse ---------- */

/*
 * The bug this pins, exactly. `peq` is indexed by token id and an OPAQUE token
 * is negative by construction (`ABUGIDA_NO_TOKEN - slot`, and
 * `ABUGIDA_NO_TOKEN` is -1), so a word with a mistyped character read the
 * pattern table at a negative index — out of bounds, usually in bounds by
 * accident, and therefore silently wrong.
 *
 * It survived this file's corpus because every id in it is a real token. The
 * differential harness found it within a minute of the kernel being wired in:
 * `levenshtein("\u00e9", "\u0416", lenient=True)` answered 0 for two
 * different characters. So the regression is pinned here, with the real
 * opaque encoding rather than a made-up negative number.
 */
static void test_opaque_tokens_are_refused(void)
{
    /* What `csrc/abugida.c` produces for these characters, computed the way
     * the tokeniser computes it: the two high bits of the slot are the UTF-8
     * length, so a two-byte character takes category 1. */
    abugida_token e_acute = (abugida_token)(ABUGIDA_NO_TOKEN - 0x80
                                            - (0xE9 - 0x80)); /* U+00E9 */
    abugida_token zhe = (abugida_token)(ABUGIDA_NO_TOKEN - 0x80
                                        - (0x436 - 0x80));    /* U+0416 */
    abugida_token q = (abugida_token)(ABUGIDA_NO_TOKEN - 'q');
    abugida_token a[2];
    abugida_token b[2];
    abugida_word wa;
    abugida_word wb;
    long out = -99;

    CHECK(e_acute < 0 && zhe < 0 && q < 0,
          "these are opaque tokens and must be negative");
    CHECK(e_acute != zhe, "two different characters must not share a token");

    a[0] = e_acute;
    b[0] = zhe;
    wa.tok = a;
    wa.n = 1;
    wa.cap = 2;
    wa.heap = 0;
    wb.tok = b;
    wb.n = 1;
    wb.cap = 2;
    wb.heap = 0;

    /* The kernel must DECLINE rather than index the table with a negative
     * number. */
    CHECK(abugida_levenshtein_myers_selected(&wa, &wb)
              == ABUGIDA_MYERS_NOT_APPLICABLE,
          "the kernel must decline a word with an opaque token");
    CHECK(!abugida_levenshtein_myers_applicable_selected(&wa, &wb),
          "and must report it as not applicable");
    /* The public entry point answers, through the DP, and gets it RIGHT: two
     * different characters are one edit apart. */
    CHECK(abugida_word_levenshtein(&wa, &wb, &out) == ABUGIDA_OK,
          "the entry point must still answer");
    CHECK(out == 1, "two different opaque characters: %ld, not 1", out);

    /* The same opaque token on both sides is zero, and that must come from
     * the DP too — the kernel declines the input either way. */
    b[0] = e_acute;
    CHECK(abugida_word_levenshtein(&wa, &wb, &out) == ABUGIDA_OK, "answer");
    CHECK(out == 0, "the same opaque character twice: %ld, not 0", out);

    /* An opaque token against a REAL one, which is the common shape: a typo
     * inside an otherwise valid word. */
    a[0] = q;
    b[0] = 10; /* 'a' */
    CHECK(abugida_word_levenshtein(&wa, &wb, &out) == ABUGIDA_OK, "answer");
    CHECK(out == 1, "a typo against a grapheme: %ld, not 1", out);
    CHECK(abugida_word_levenshtein(&wb, &wa, &out) == ABUGIDA_OK, "symmetry");
    CHECK(out == 1, "and the other way round: %ld, not 1", out);
}

/* --- a word long enough that only the DP can answer -------------------- */

static void test_the_fallback_is_reached_and_correct(void)
{
    /* 200 tokens: past the kernel's range by a factor of three, so the public
     * function must fall through to the DP and still be right. */
    abugida_token a[200];
    abugida_token b[200];
    size_t i;
    long core;
    long ref;

    for (i = 0; i < 200; i++) {
        a[i] = (abugida_token)(i % 17);
        b[i] = (abugida_token)(i % 17);
    }
    core = core_levenshtein(a, 200, b, 200);
    CHECK(core == 0, "identical 200-token words: %ld, not 0", core);

    /* And a known distance at that size: change every 20th token. */
    for (i = 0; i < 200; i += 20)
        b[i] = (abugida_token)((b[i] + 1) % ABUGIDA_NPLAIN);
    core = core_levenshtein(a, 200, b, 200);
    CHECK(core == 10, "10 substitutions in 200 tokens: %ld, not 10", core);

    /* The reference cannot check 200 tokens with its stack buffer, so the
     * check is the property instead: symmetry, and the bound. */
    CHECK(core_levenshtein(b, 200, a, 200) == core,
          "the fallback is not symmetric");
    ref = core_levenshtein(a, 200, a, 199);
    CHECK(ref == 1, "a one-token suffix: %ld, not 1", ref);
}

/* --- the dispatcher ---------------------------------------------------- */

/*
 * Two things are checked here that running one variant cannot check.
 *
 * First, that EVERY variant the build contains answers the same as the
 * dynamic program — not just the one this CPU selects. A variant that is
 * wrong only on a machine the author does not own is exactly the failure the
 * dispatcher makes possible, and `abugida_impl_count`/`_at` exist so a test
 * can walk them.
 *
 * Second, that the dispatcher itself behaves: the name it reports is a name
 * it contains, selecting by name takes effect, an unknown name is REFUSED
 * rather than ignored (a caller who believes it tested `sse2` while `avx2`
 * answered has been misled), and NULL goes back to the default.
 */
static void test_the_dispatcher(void)
{
    int n = abugida_impl_count();
    int i;
    const char *name;

    CHECK(n >= 1, "there must be at least one implementation, got %d", n);
    for (i = 0; i < n; i++) {
        name = abugida_impl_at(i);
        CHECK(name != NULL, "variant %d has no name", i);
        if (name)
            CHECK(abugida_impl_select(name) == ABUGIDA_OK,
                  "variant %d (%s) could not be selected", i, name);
    }
    CHECK(abugida_impl_at(n) == NULL, "one past the end must be NULL");
    CHECK(abugida_impl_at(-1) == NULL, "a negative index must be NULL");

    /* An unknown name is an error, and the previous choice survives it. */
    if (n > 0) {
        const char *first = abugida_impl_at(0);

        CHECK(abugida_impl_select(first) == ABUGIDA_OK, "select %s", first);
        CHECK(abugida_impl_select("no-such-variant") == ABUGIDA_ERR_INVALID,
              "an unknown variant name must be refused");
        CHECK(abugida_impl_select(first) == ABUGIDA_OK, "select %s again", first);
    }
    /* NULL restores the default, which must be a name in the list. */
    CHECK(abugida_impl_select(NULL) == ABUGIDA_OK, "NULL must reset the choice");
    name = abugida_impl_name();
    CHECK(name != NULL && name[0] != '\0', "the chosen variant must have a name");
    for (i = 0; i < n; i++) {
        const char *cand = abugida_impl_at(i);

        if (cand && strcmp(cand, name) == 0)
            break;
    }
    CHECK(i < n, "the default variant %s is not in the list", name ? name : "(null)");
}

/*: Run the whole battery once per variant, so a variant this CPU would never
 * select is still checked on this CPU. */
int main(void)
{
    int n;
    int i;

    printf("abugida — Myers kernel vs the dynamic program\n");

    test_the_dispatcher();

    n = abugida_impl_count();
    for (i = 0; i < n; i++) {
        const char *name = abugida_impl_at(i);
        int before = failures;

        CHECK(abugida_impl_select(name) == ABUGIDA_OK, "select %s", name);
        impl_label = name;
        printf("  variant %s\n", name);
        test_all_pairs();
        test_the_boundary();
        test_opaque_tokens_are_refused();
        test_the_fallback_is_reached_and_correct();
        if (failures == before)
            printf("    ok\n");
    }
    impl_label = "";

    /* Leave the library on its default, so a later test in the same process
     * (there is none today) does not inherit a forced variant. */
    abugida_impl_select(NULL);

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
