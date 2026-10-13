/* Measure one kernel variant, in its own process.
 *
 * The dispatcher's choice should be justified by a number, not by a flag name:
 * a variant that is not faster has no reason to exist, and the only way to
 * know is to time it. One variant per process, because interleaving them lets
 * the first one's cache misses and the CPU's frequency scaling land on
 * whichever ran second — the first version of this file did that and reported
 * the C kernel as three times faster than itself.
 *
 * TWO NUMBERS, and they are not the same number. `kernel` is the recurrence
 * alone, which is what the `-m` flags change. `entry` goes through
 * `abugida_word_levenshtein`, which is what a caller actually pays: the
 * dispatch, the fallback check for inputs the kernel declines, and the
 * plumbing. The second is the honest one for "is this worth having".
 *
 *     make -C csrc bench            # runs every variant in turn
 *     ./build/c/bench_impl c        # or one of them
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <string.h>
#include <time.h>

#include "abugida.h"

static volatile long sink;

static double now_ns(void)
{
    struct timespec t;

    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec * 1e9 + (double)t.tv_nsec;
}

enum { NW = 5, REP = 20000, ROUNDS = 15 };

static const char *const words[NW][2] = {
    { "kamma", "khamma" },
    { "dhammaniyama", "dhammaniyāma" },
    { "abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ",
      "abhidhammapiṭakapakaranassaṭṭhakathaṃ" },
    { "vikkhambhati", "vikhambhati" },
    { "cittuppāda", "cittupada" },
};

int main(int argc, char **argv)
{
    abugida_word wa[NW];
    abugida_word wb[NW];
    abugida_token ta[NW][64];
    abugida_token tb[NW][64];
    double t0;
    double t1;
    double kernel;
    double entry;
    int k;
    int r;
    int i;

    if (argc > 1 && strcmp(argv[1], "--list") == 0) {
        for (k = 0; k < abugida_impl_count(); k++)
            printf("%s\n", abugida_impl_at(k));
        return 0;
    }
    if (argc > 1) {
        if (abugida_impl_select(argv[1]) != ABUGIDA_OK) {
            fprintf(stderr, "no such variant: %s (have:", argv[1]);
            for (k = 0; k < abugida_impl_count(); k++)
                fprintf(stderr, " %s", abugida_impl_at(k));
            fprintf(stderr, ")\n");
            return 2;
        }
    }
    for (i = 0; i < NW; i++) {
        wa[i].tok = ta[i];
        wa[i].n = 0;
        wa[i].cap = 64;
        wa[i].heap = 0;
        wb[i].tok = tb[i];
        wb[i].n = 0;
        wb[i].cap = 64;
        wb[i].heap = 0;
        if (abugida_word_from_text(&wa[i], words[i][0], strlen(words[i][0]), 0, NULL)
                != ABUGIDA_OK
            || abugida_word_from_text(&wb[i], words[i][1], strlen(words[i][1]),
                                      0, NULL) != ABUGIDA_OK) {
            printf("tokenisation failed for %s\n", words[i][0]);
            return 1;
        }
    }

    /* Warm up both paths, so neither is charged for the cold cache. */
    for (r = 0; r < 20000; r++)
        for (i = 0; i < NW; i++) {
            long out = 0;

            sink += abugida_levenshtein_myers_selected(&wa[i], &wb[i]);
            abugida_word_levenshtein(&wa[i], &wb[i], &out);
            sink += out;
        }

    /* INTERLEAVED ROUNDS, and the BEST round of each is reported. One round
     * of each in one order is not a measurement: the kernel loop ran first
     * and the entry loop second, so the second was charged with a warmer
     * cache and a higher clock, and the entry point came out FASTER than the
     * kernel it calls — which is not a thing that can happen. The minimum is
     * the statistic that survives a noisy machine: the fastest round is the
     * one least disturbed by a scheduler that does not know it is being
     * measured. */
    kernel = 1e18;
    entry = 1e18;
    for (k = 0; k < ROUNDS; k++) {
        t0 = now_ns();
        for (r = 0; r < REP; r++)
            for (i = 0; i < NW; i++)
                sink += abugida_levenshtein_myers_selected(&wa[i], &wb[i]);
        t1 = now_ns();
        if ((t1 - t0) / (double)(REP * NW) < kernel)
            kernel = (t1 - t0) / (double)(REP * NW);

        t0 = now_ns();
        for (r = 0; r < REP; r++)
            for (i = 0; i < NW; i++) {
                long out = 0;

                abugida_word_levenshtein(&wa[i], &wb[i], &out);
                sink += out;
            }
        t1 = now_ns();
        if ((t1 - t0) / (double)(REP * NW) < entry)
            entry = (t1 - t0) / (double)(REP * NW);
    }

    printf("%-5s kernel %7.1f ns/pair   entry %7.1f ns/pair   (sink %ld)\n",
           abugida_impl_name(), kernel, entry, (long)sink);
    return 0;
}
