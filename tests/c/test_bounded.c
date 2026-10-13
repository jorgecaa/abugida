/* The bounded DP against the plain one.
 *
 * `abugida_word_distance_bounded` is `abugida_word_distance` with a limit: it
 * answers "above this" or the exact distance, and it stops early on the first.
 * It exists because C consumers sweep pools where most candidates are going
 * to be discarded, and it is kept out of the Python API because there the
 * per-candidate cost of asking eats the saving (`docs/asm-plan.md` phase 3).
 *
 * THREE WRONG VERSIONS OF THE CUT ARE PINNED HERE, because each of them
 * looked reasonable and each was wrong:
 *
 *   1. "stop when the row's minimum exceeds the bound" — that the minimum of
 *      row i exceeds the bound DOES prove the final distance does (a path
 *      through row i pays at least that), but it does not license stopping: a
 *      later cell of the same row can still be under the bound. It lost
 *      `vohari`/`voharati`, true distance 1.627 against a bound of 1.5, and
 *      got 2.6% of verdicts wrong on a real pool.
 *   2. the same plus `remaining * min_indel`, on the theory that the steps
 *      left have a floor. They do not: a substitution between two equal
 *      tokens costs 0. 4% wrong.
 *   3. forgetting `cur[0]` when taking the row's minimum, which is the
 *      cheapest cell of the first row.
 *
 * So the checks below are not "does it work" but "does it agree with the
 * plain DP on every pair, at every bound, including the ones where it cuts".
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "abugida.h"

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

/* The pairs that broke a version of the cut, plus the shapes around them. */
static const char *const PAIRS[][2] = {
    { "vohari", "voharati" },      /* version 1 cut this one at 1.627 > 1.5 */
    { "vohari", "voharita" },
    { "vohari", "voharīyi" },
    { "vohari", "vohārika" },
    { "vohari", "āhariyi" },
    { "navadvāra", "gharadvāra" },
    { "navadvāra", "sabbadvāra" },
    { "navadvāra", "vajadvāra" },
    { "vohari", "vihari" },
    { "vohari", "ohari" },
    { "vohari", "vohāra" },
    { "a", "a" },
    { "a", "b" },
    { "kamma", "khamma" },
    { "kamma", "kamma" },
    { "kamma", "yoga" },
    { "saṃgha", "saṅgha" },
    { "dhammaniyāmaṃ", "dhammaniyama" },
    { "vikkhambhati", "vikhambhati" },
    { "buddhassa", "buddhasa" },
    { "ṭhāna", "ṭhānāni" },
    { "ñāṇa", "ñāṇena" },
    { "kh", "k" },
    { "tt", "ṭṭ" },
    { "abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ",
      "abhidhammapiṭakapakaranassaṭṭhakathaṃ" },
    { "", "" },
    { "", "kamma" },
};

enum { NPAIRS = (int)(sizeof PAIRS / sizeof PAIRS[0]) };

/*: The bounds to sweep. Chosen to fall either side of the real distances:
 * several of these pairs sit just under one of them, which is where a
 * too-eager cut shows up. */
static const double BOUNDS[] = { 0.1, 0.3, 0.45, 0.5, 0.53, 0.627140,
                                 0.7, 0.9, 1.0, 1.2, 1.5, 1.7, 2.0, 3.0 };
enum { NBOUNDS = (int)(sizeof BOUNDS / sizeof BOUNDS[0]) };

static abugida_status word_of(abugida_word *w, abugida_token *buf,
                              const char *word)
{
    w->tok = buf;
    w->n = 0;
    w->cap = 128;
    w->heap = 0;
    return abugida_word_from_text(w, word, strlen(word), 1, NULL);
}

static void check_pair(int k, double bound)
{
    abugida_word wa;
    abugida_word wb;
    abugida_token ba[128];
    abugida_token bb[128];
    double plain = 0.0;
    double bounded = 0.0;
    int beyond = -1;
    abugida_status st;

    if (word_of(&wa, ba, PAIRS[k][0]) != ABUGIDA_OK
        || word_of(&wb, bb, PAIRS[k][1]) != ABUGIDA_OK) {
        CHECK(0, "could not tokenise %s / %s", PAIRS[k][0], PAIRS[k][1]);
        return;
    }
    CHECK(abugida_word_distance(&wa, &wb, &plain) == ABUGIDA_OK,
          "plain distance failed for %s / %s", PAIRS[k][0], PAIRS[k][1]);

    st = abugida_word_distance_bounded(&wa, &wb, bound, &beyond, &bounded);
    CHECK(st == ABUGIDA_OK, "bounded failed for %s / %s at %.3f",
          PAIRS[k][0], PAIRS[k][1], bound);

    if (beyond) {
        /* The verdict must be TRUE: the distance really is above the bound. */
        CHECK(plain > bound,
              "%s / %s at %.3f: said beyond, but the distance is %.6f",
              PAIRS[k][0], PAIRS[k][1], bound, plain);
    } else {
        /* And when it did not cut, the value must be the same DOUBLE, not a
         * value close to it: the parity guarantee is bit-exact. */
        CHECK(plain <= bound,
              "%s / %s at %.3f: gave %.6f, which is above the bound",
              PAIRS[k][0], PAIRS[k][1], bound, plain);
        CHECK(bounded == plain,
              "%s / %s at %.3f: %.17g against %.17g",
              PAIRS[k][0], PAIRS[k][1], bound, bounded, plain);
    }
    /* Symmetry is not free here: an earlier version stored nothing in a cell
     * over the bound, which left a stale value in the rolling row and made
     * the two directions disagree. */
    beyond = -1;
    bounded = 0.0;
    CHECK(abugida_word_distance_bounded(&wb, &wa, bound, &beyond, &bounded)
              == ABUGIDA_OK, "the other direction failed");
    if (beyond)
        CHECK(plain > bound, "%s / %s reversed said beyond at %.3f",
              PAIRS[k][1], PAIRS[k][0], bound);
    else
        CHECK(bounded == plain, "%s / %s reversed: %.17g against %.17g",
              PAIRS[k][1], PAIRS[k][0], bounded, plain);
}

static void test_every_pair_at_every_bound(void)
{
    int k;
    int b;

    for (k = 0; k < NPAIRS; k++)
        for (b = 0; b < NBOUNDS; b++)
            check_pair(k, BOUNDS[b]);
}

/* A pool-shaped sweep: many pairs, so a rare disagreement shows up. */
static void test_a_pool_shaped_sweep(void)
{
    static const char *const words[] = {
        "kamma", "khamma", "dhamma", "dhammā", "saṃgha", "saṅgha",
        "citta", "buddha", "ṭhāna", "ñāṇa", "vohari", "voharati",
        "vihari", "ohari", "vohāra", "navadvāra", "gharadvāra",
        "vikkhambhati", "vikhambhati", "abhidhamma", "abhidhammā",
        "sīha", "sīhassa", "paṭhama", "paṭhamā", "yoga", "gata",
    };
    enum { NW = (int)(sizeof words / sizeof words[0]) };
    abugida_word w[NW];
    abugida_token t[NW][128];
    int i;
    int j;
    int b;

    for (i = 0; i < NW; i++)
        CHECK(word_of(&w[i], t[i], words[i]) == ABUGIDA_OK,
              "could not tokenise %s", words[i]);

    for (b = 0; b < NBOUNDS; b++) {
        for (i = 0; i < NW; i++) {
            for (j = 0; j < NW; j++) {
                double plain = 0.0;
                double bounded = 0.0;
                int beyond = -1;

                abugida_word_distance(&w[i], &w[j], &plain);
                abugida_word_distance_bounded(&w[i], &w[j], BOUNDS[b],
                                              &beyond, &bounded);
                checks++;
                if (beyond ? !(plain > BOUNDS[b]) : !(bounded == plain)) {
                    failures++;
                    printf("FAIL %s/%s at %.3f: plain %.17g, beyond %d, "
                           "bounded %.17g\n", words[i], words[j], BOUNDS[b],
                           plain, beyond, bounded);
                }
            }
        }
    }
}

/* The contract of the arguments, which a C consumer will get wrong once. */
static void test_the_arguments(void)
{
    abugida_word wa;
    abugida_word wb;
    abugida_token ba[128];
    abugida_token bb[128];
    double out = 0.0;
    int beyond = 0;

    word_of(&wa, ba, "kamma");
    word_of(&wb, bb, "khamma");
    CHECK(abugida_word_distance_bounded(NULL, &wb, 1.5, &beyond, &out)
              == ABUGIDA_ERR_INVALID, "a NULL word must be refused");
    CHECK(abugida_word_distance_bounded(&wa, NULL, 1.5, &beyond, &out)
              == ABUGIDA_ERR_INVALID, "a NULL word must be refused");
    CHECK(abugida_word_distance_bounded(&wa, &wb, 1.5, NULL, &out)
              == ABUGIDA_ERR_INVALID, "a NULL flag must be refused");
    CHECK(abugida_word_distance_bounded(&wa, &wb, 1.5, &beyond, NULL)
              == ABUGIDA_ERR_INVALID, "a NULL out must be refused");
    /* A non-positive bound is not "no bound": it is a mistake, and the
     * function that means "no bound" is the plain one. */
    CHECK(abugida_word_distance_bounded(&wa, &wb, 0.0, &beyond, &out)
              == ABUGIDA_ERR_INVALID, "a zero bound must be refused");
    CHECK(abugida_word_distance_bounded(&wa, &wb, -1.0, &beyond, &out)
              == ABUGIDA_ERR_INVALID, "a negative bound must be refused");
}

int main(void)
{
    printf("abugida — the bounded DP against the plain one\n");

    test_every_pair_at_every_bound();
    test_a_pool_shaped_sweep();
    test_the_arguments();

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
