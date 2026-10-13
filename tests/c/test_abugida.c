/* The C core's own test suite: the properties the Python package tests, run
 * against the C implementation directly, with no Python in the process.
 *
 * This is the point of the C version being a library rather than a binding:
 * a C or C++ program that links `abugida.c` and `abugida_tables.c` gets the
 * metric, and these are the checks that it behaves like the documented
 * metric — the balance principle, the metric axioms over the whole
 * inventory, degemination priced as consonant length, the epenthetic indel
 * weights, the sandhi pipeline, and the DP's two views agreeing.
 *
 *     make -C tests/c check        (or: python -m pytest tests/test_c_core.py)
 *
 * It deliberately carries its own expected VALUES, taken from the published
 * tables in docs/comparator.md, rather than only self-consistency checks: a
 * library that is internally consistent and externally wrong would pass the
 * latter.
 */

#include <math.h>
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

#define CLOSE(a, b, tol) (fabs((a) - (b)) <= (tol))

/* One-shot helper: tokenise a literal and score it. */
static double distance_of(const char *w1, const char *w2)
{
    abugida_token ta[ABUGIDA_STACK_TOKENS];
    abugida_token tb[ABUGIDA_STACK_TOKENS];
    abugida_word a = ABUGIDA_WORD(ta, ABUGIDA_STACK_TOKENS);
    abugida_word b = ABUGIDA_WORD(tb, ABUGIDA_STACK_TOKENS);
    double d = -1.0;

    if (abugida_word_from_text(&a, w1, strlen(w1), 0, NULL) != ABUGIDA_OK)
        return -1.0;
    if (abugida_word_from_text(&b, w2, strlen(w2), 0, NULL) != ABUGIDA_OK)
        return -1.0;
    if (abugida_word_distance(&a, &b, &d) != ABUGIDA_OK)
        return -1.0;
    return d;
}

static char *text_of(abugida_string *s, const char *word,
                     abugida_status (*fn)(abugida_string *, const char *,
                                          size_t))
{
    abugida_status st = fn(s, word, strlen(word));

    if (st != ABUGIDA_OK) {
        printf("FAIL: %s(%s) -> %s\n", "pipeline", word,
               abugida_strerror(st));
        failures++;
        return NULL;
    }
    return s->text;
}

/* --- the vocabulary and the published scale -------------------------- */

static void test_vocabulary(void)
{
    size_t i;
    size_t n = 0;
    const abugida_token *eph;

    /* 41 graphemes + 82 heavy units (42 geminates, 40 homorganic nasal+stop
     * clusters, 20 of them with ṃ) + 3 Sanskrit phonemes. The count is
     * asserted so that a vocabulary change is a deliberate edit here and not
     * a silent drift in the generated tables. */
    CHECK(ABUGIDA_NTOKENS == 126, "tokens: %d", ABUGIDA_NTOKENS);
    CHECK(ABUGIDA_NPLAIN == 41, "graphemes: %d", ABUGIDA_NPLAIN);
    for (i = 0; i < (size_t)ABUGIDA_NTOKENS; i++)
        CHECK(abugida_token_text((abugida_token)i) != NULL, "no text for %zu", i);
    CHECK(abugida_token_text(ABUGIDA_NO_TOKEN) == NULL, "no-token has text");
    CHECK(abugida_token_text(ABUGIDA_NTOKENS) == NULL, "past-the-end has text");
    CHECK(strcmp(abugida_token_text(ABUGIDA_TOK_K_H), "kh") == 0,
          "kh is %s", abugida_token_text(ABUGIDA_TOK_K_H));

    eph = abugida_epenthetic(&n);
    CHECK(n == 11, "epenthetic class has %zu members", n);
    for (i = 0; i < n; i++)
        CHECK(abugida_indel(eph[i]) == abugida_indel_weight(),
              "%s is not epenthetic", abugida_token_text(eph[i]));
    CHECK(abugida_indel(ABUGIDA_TOK_K) == 1.0, "k is epenthetic");
}

/* The scale in docs/comparator.md, one row at a time. These are the numbers
 * users read, so they are checked as values and not only as inequalities. */
static void test_published_scale(void)
{
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_A, ABUGIDA_TOK_AA), 0.333, 1e-3),
          "a-aa: %.4f", abugida_cost(ABUGIDA_TOK_A, ABUGIDA_TOK_AA));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_K_H), 0.470, 1e-3),
          "k-kh: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_K_H));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G), 0.470, 1e-3),
          "k-g: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G_H), 0.631, 1e-3),
          "k-gh: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G_H));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_T_DOT), 0.601, 1e-3),
          "t-ṭ: %.4f", abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_T_DOT));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_C), 0.601, 1e-3),
          "k-c: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_C));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_N, ABUGIDA_TOK_N_DOT_BELOW), 0.437,
                1e-3),
          "n-ṇ: %.4f", abugida_cost(ABUGIDA_TOK_N, ABUGIDA_TOK_N_DOT_BELOW));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_L, ABUGIDA_TOK_L_DOT), 0.322, 1e-3),
          "l-ḷ: %.4f", abugida_cost(ABUGIDA_TOK_L, ABUGIDA_TOK_L_DOT));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_N_DOT, ABUGIDA_TOK_M_DOT), 0.740,
                1e-3),
          "ṅ-ṃ: %.4f", abugida_cost(ABUGIDA_TOK_N_DOT, ABUGIDA_TOK_M_DOT));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_P), 0.889, 1e-3),
          "k-p: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_P));
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_Y), 0.831, 1e-3),
          "k-y: %.4f", abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_Y));
    CHECK(abugida_cost(ABUGIDA_TOK_B, ABUGIDA_TOK_S) == 1.0,
          "b-s: %.4f", abugida_cost(ABUGIDA_TOK_B, ABUGIDA_TOK_S));
    CHECK(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_K) == 0.0, "k-k is not 0");
}

/* --- the algebra's link to the geometry ------------------------------ */

static void test_balance_principle(void)
{
    /* The derived weight makes the two elementary moves cost the same. This
     * is the single most load-bearing property of the calibration: if it
     * fails, rho* is wrong. */
    double aspirating = abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_K_H);
    double voicing = abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G);

    CHECK(CLOSE(aspirating, voicing, 1e-15),
          "balance: aspiration %.17g against voicing %.17g", aspirating,
          voicing);
    CHECK(CLOSE(abugida_neutral_modifier_weight(), 0.458, 1e-3),
          "rho*: %.6f", abugida_neutral_modifier_weight());
    CHECK(CLOSE(abugida_indel_weight(), 0.627, 1e-3),
          "indel weight: %.6f", abugida_indel_weight());
    CHECK(abugida_one_move() >= abugida_indel_weight(),
          "ONE_MOVE below the epenthetic indel");
}

static void test_within_series_gradients(void)
{
    CHECK(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G)
          < abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G_H), "k-g < k-gh");
    CHECK(abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G_H)
          < abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_P), "k-gh < k-p");
    /* Bridge ordering, and the labial that bridges to nothing. */
    CHECK(abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_T_DOT)
          < abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_P), "t-ṭ < k-p");
    CHECK(abugida_cost(ABUGIDA_TOK_N, ABUGIDA_TOK_N_DOT_BELOW)
          < abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_T_DOT), "n-ṇ < t-ṭ");
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_P, ABUGIDA_TOK_K),
                abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_P), 0.0),
          "p-k differs from k-p");
    /* Every series behaves the same: the √½/√½ split keeps unit norm. */
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_D),
                abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G), 1e-15),
          "t-d differs from k-g");
    CHECK(CLOSE(abugida_cost(ABUGIDA_TOK_P, ABUGIDA_TOK_B),
                abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_G), 1e-15),
          "p-b differs from k-g");
}

/* --- the metric guarantee, exhaustively over the inventory ----------- */

static void test_cost_is_a_metric(void)
{
    int x;
    int y;
    int z;

    for (x = 0; x < ABUGIDA_NTOKENS; x++) {
        CHECK(abugida_cost((abugida_token)x, (abugida_token)x) == 0.0,
              "identity fails at %s", abugida_token_text((abugida_token)x));
        for (y = 0; y < ABUGIDA_NTOKENS; y++) {
            double xy = abugida_cost((abugida_token)x, (abugida_token)y);
            double yx = abugida_cost((abugida_token)y, (abugida_token)x);

            CHECK(xy == yx, "symmetry fails for %s/%s",
                  abugida_token_text((abugida_token)x),
                  abugida_token_text((abugida_token)y));
            CHECK(xy >= 0.0 && xy <= 1.0, "cost out of range: %g", xy);
            for (z = 0; z < ABUGIDA_NTOKENS; z++) {
                double xz = abugida_cost((abugida_token)x, (abugida_token)z);
                double zy = abugida_cost((abugida_token)z, (abugida_token)y);

                CHECK(xy <= xz + zy + 1e-12,
                      "triangle fails: %s/%s/%s (%g > %g)",
                      abugida_token_text((abugida_token)x),
                      abugida_token_text((abugida_token)y),
                      abugida_token_text((abugida_token)z), xy, xz + zy);
            }
        }
    }
}

/* The indel triangle conditions of `test_metric_conditions_on_extended_
 * alphabet`: |indel(x) - indel(y)| <= cost(x, y) <= indel(x) + indel(y). */
static void test_indel_conditions(void)
{
    int x;
    int y;

    for (x = 0; x < ABUGIDA_NPLAIN; x++) {
        for (y = 0; y < ABUGIDA_NPLAIN; y++) {
            double c = abugida_cost((abugida_token)x, (abugida_token)y);
            double ix = abugida_indel((abugida_token)x);
            double iy = abugida_indel((abugida_token)y);

            CHECK(fabs(ix - iy) <= c + 1e-12 || x == y,
                  "|indel| bound fails for %s/%s",
                  abugida_token_text((abugida_token)x),
                  abugida_token_text((abugida_token)y));
            CHECK(c <= ix + iy + 1e-12, "indel sum bound fails for %s/%s",
                  abugida_token_text((abugida_token)x),
                  abugida_token_text((abugida_token)y));
        }
    }
}

/* --- the distance over words ----------------------------------------- */

static const char *const WORDS[] = {
    "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
    "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
    "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha"
};
#define NWORDS ((int)(sizeof(WORDS) / sizeof(WORDS[0])))

static void test_word_distance_properties(void)
{
    int i;
    int j;
    int k;

    for (i = 0; i < NWORDS; i++)
        CHECK(distance_of(WORDS[i], WORDS[i]) == 0.0, "%s is not 0 from itself",
              WORDS[i]);
    for (i = 0; i < NWORDS; i++) {
        for (j = 0; j < NWORDS; j++) {
            double dij = distance_of(WORDS[i], WORDS[j]);
            double dji = distance_of(WORDS[j], WORDS[i]);

            CHECK(CLOSE(dij, dji, 1e-15), "asymmetry %s/%s: %g against %g",
                  WORDS[i], WORDS[j], dij, dji);
            for (k = 0; k < NWORDS; k++) {
                double dik = distance_of(WORDS[i], WORDS[k]);
                double dkj = distance_of(WORDS[k], WORDS[j]);

                CHECK(dij <= dik + dkj + 1e-12,
                      "word triangle %s/%s/%s: %g > %g", WORDS[i], WORDS[j],
                      WORDS[k], dij, dik + dkj);
            }
        }
    }
}

static void test_documented_examples(void)
{
    /* The two lines the README opens with. */
    CHECK(CLOSE(distance_of("kamma", "khamma"), 0.470, 1e-3),
          "kamma/khamma: %.4f", distance_of("kamma", "khamma"));
    CHECK(CLOSE(distance_of("kamma", "gamma"), 0.470, 1e-3),
          "kamma/gamma: %.4f", distance_of("kamma", "gamma"));
    CHECK(distance_of("kamma", "samma") == 1.0, "kamma/samma: %.4f",
          distance_of("kamma", "samma"));
    CHECK(CLOSE(distance_of("attha", "atha"), 0.470, 1e-3),
          "attha/atha: %.4f", distance_of("attha", "atha"));
    CHECK(distance_of("kamma", "khamma") <= abugida_one_move(),
          "one aspiration move is above ONE_MOVE");
    CHECK(distance_of("kamma", "khamma") < distance_of("kamma", "samma"),
          "aspiration did not beat unrelated");
}

/* Levenshtein over the same tokenisation: kh is one letter in both. */
static void test_levenshtein_baseline(void)
{
    abugida_token ta[ABUGIDA_STACK_TOKENS];
    abugida_token tb[ABUGIDA_STACK_TOKENS];
    abugida_word a = ABUGIDA_WORD(ta, ABUGIDA_STACK_TOKENS);
    abugida_word b = ABUGIDA_WORD(tb, ABUGIDA_STACK_TOKENS);
    long lev = -1;

    abugida_word_from_text(&a, "kamma", strlen("kamma"), 0, NULL);
    abugida_word_from_text(&b, "khamma", strlen("khamma"), 0, NULL);
    abugida_word_levenshtein(&a, &b, &lev);
    CHECK(lev == 1, "levenshtein(kamma, khamma) = %ld", lev);
    CHECK(distance_of("kamma", "khamma") < (double)lev,
          "the metric is not below Levenshtein");
}

/* --- geminates: consonant length, priced as heavy units -------------- */

static void test_geminates(void)
{
    CHECK(CLOSE(distance_of("attha", "atha"), 0.470, 1e-3),
          "degemination: %.4f", distance_of("attha", "atha"));
    CHECK(distance_of("attha", "atha") <= abugida_one_move(),
          "degemination above ONE_MOVE");
    CHECK(distance_of("kamma", "kama") < 0.5, "kamma/kama: %.4f",
          distance_of("kamma", "kama"));
    CHECK(CLOSE(distance_of("magga", "makka"),
                abugida_cost(ABUGIDA_TOK_G_G, ABUGIDA_TOK_K_K), 1e-12),
          "geminate against geminate: %.4f", distance_of("magga", "makka"));
    /* A geminate against a nasal+stop cluster: the half that differs. */
    CHECK(CLOSE(distance_of("citta", "cinta"),
                abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_N), 1e-12),
          "citta/cinta: %.4f", distance_of("citta", "cinta"));
    CHECK(CLOSE(distance_of("puñña", "puñja"),
                abugida_cost(ABUGIDA_TOK_N_TILDE, ABUGIDA_TOK_J), 1e-12),
          "puñña/puñja: %.4f", distance_of("puñña", "puñja"));
    CHECK(distance_of("citta", "cinta") < distance_of("citta", "cimta"),
          "cluster alignment broke");
}

/* The aspirated geminate is ONE long aspirated consonant, not a long plain
 * one plus h: 'kkh' aligns as a single token against a single token. */
static void test_aspirated_geminate(void)
{
    double d = distance_of("vikkhambhati", "vikhambhati");

    CHECK(d > 0.0 && d < 1.0, "vikkhambhati/vikhambhati: %.4f", d);
    CHECK(d < 1.0, "the doubled aspirate was priced as two indels: %.4f", d);
}

/* --- the epenthetic class, from Geiger ------------------------------- */

static void test_epenthetic_doublets(void)
{
    const char *pairs[][2] = {
        { "sve", "suve" },
        { "idāni", "dāni" },
        { "uṭṭhita", "vuṭṭhita" },
        { "sakiṃ", "saki" }
    };
    size_t i;

    for (i = 0; i < sizeof(pairs) / sizeof(pairs[0]); i++) {
        double d = distance_of(pairs[i][0], pairs[i][1]);

        CHECK(CLOSE(d, abugida_indel_weight(), 1e-12),
              "%s/%s: %.4f, not the epenthetic weight %.4f", pairs[i][0],
              pairs[i][1], d, abugida_indel_weight());
    }
}

/* --- the two views: the scalar and the receipt ----------------------- */

static void test_alignment_conserves_the_distance(void)
{
    int i;
    int j;

    for (i = 0; i < NWORDS; i++) {
        for (j = 0; j < NWORDS; j++) {
            abugida_token ta[ABUGIDA_STACK_TOKENS];
            abugida_token tb[ABUGIDA_STACK_TOKENS];
            abugida_word a = ABUGIDA_WORD(ta, ABUGIDA_STACK_TOKENS);
            abugida_word b = ABUGIDA_WORD(tb, ABUGIDA_STACK_TOKENS);
            abugida_op *ops = NULL;
            size_t nops = 0;
            double total = 0.0;
            double d = 0.0;
            size_t k;
            abugida_status st;

            abugida_word_from_text(&a, WORDS[i], strlen(WORDS[i]), 0, NULL);
            abugida_word_from_text(&b, WORDS[j], strlen(WORDS[j]), 0, NULL);
            st = abugida_word_align(&a, &b, &ops, &nops);
            CHECK(st == ABUGIDA_OK, "align failed: %s", abugida_strerror(st));
            if (st != ABUGIDA_OK)
                continue;
            abugida_word_distance(&a, &b, &d);
            for (k = 0; k < nops; k++)
                total += ops[k].cost;
            CHECK(CLOSE(total, d, 1e-12),
                  "alignment of %s/%s sums to %.17g, distance is %.17g",
                  WORDS[i], WORDS[j], total, d);
            abugida_ops_free(ops);
        }
    }
}

static void test_alignment_reports_the_edit(void)
{
    abugida_token ta[ABUGIDA_STACK_TOKENS];
    abugida_token tb[ABUGIDA_STACK_TOKENS];
    abugida_word a = ABUGIDA_WORD(ta, ABUGIDA_STACK_TOKENS);
    abugida_word b = ABUGIDA_WORD(tb, ABUGIDA_STACK_TOKENS);
    abugida_op *ops = NULL;
    size_t nops = 0;
    size_t k;
    int edits = 0;

    abugida_word_from_text(&a, "kamma", strlen("kamma"), 0, NULL);
    abugida_word_from_text(&b, "khamma", strlen("khamma"), 0, NULL);
    abugida_word_align(&a, &b, &ops, &nops);
    for (k = 0; k < nops; k++) {
        if (ops[k].op == ABUGIDA_OP_KEEP) {
            CHECK(ops[k].cost == 0.0, "a keep costs %g", ops[k].cost);
            continue;
        }
        edits++;
        CHECK(ops[k].op == ABUGIDA_OP_SUB, "unexpected op %s",
              abugida_op_name(ops[k].op));
        CHECK(strcmp(abugida_token_text(ops[k].left), "k") == 0,
              "substituted from %s", abugida_token_text(ops[k].left));
        CHECK(strcmp(abugida_token_text(ops[k].right), "kh") == 0,
              "substituted to %s", abugida_token_text(ops[k].right));
        CHECK(CLOSE(ops[k].cost, abugida_cost(ABUGIDA_TOK_K, ABUGIDA_TOK_K_H),
                    0.0), "substitution cost %g", ops[k].cost);
    }
    CHECK(edits == 1, "kamma/khamma has %d edits", edits);
    abugida_ops_free(ops);
}

static void test_deletion_and_insertion_reports(void)
{
    abugida_token ta[ABUGIDA_STACK_TOKENS];
    abugida_token tb[ABUGIDA_STACK_TOKENS];
    abugida_word a = ABUGIDA_WORD(ta, ABUGIDA_STACK_TOKENS);
    abugida_word b = ABUGIDA_WORD(tb, ABUGIDA_STACK_TOKENS);
    abugida_op *ops = NULL;
    size_t nops = 0;
    size_t k;
    int insertions = 0;

    abugida_word_from_text(&a, "gacchati", strlen("gacchati"), 0, NULL);
    abugida_word_from_text(&b, "gacchanti", strlen("gacchanti"), 0, NULL);
    /* The n before the stop is the first half of the heavy unit nt, so the
     * script is ONE substitution t -> nt priced as the half that differs
     * (t~n), not an insertion of n at full price. */
    abugida_word_align(&a, &b, &ops, &nops);
    for (k = 0; k < nops; k++) {
        if (ops[k].op == ABUGIDA_OP_INS || ops[k].op == ABUGIDA_OP_DEL)
            insertions++;
        if (ops[k].op != ABUGIDA_OP_SUB)
            continue;
        CHECK(strcmp(abugida_token_text(ops[k].left), "t") == 0
              && strcmp(abugida_token_text(ops[k].right), "nt") == 0,
              "substituted %s -> %s", abugida_token_text(ops[k].left),
              abugida_token_text(ops[k].right));
        CHECK(CLOSE(ops[k].cost, abugida_cost(ABUGIDA_TOK_T, ABUGIDA_TOK_N),
                    1e-12), "t -> nt costs %g", ops[k].cost);
    }
    CHECK(insertions == 0, "gacchati/gacchanti inserts %d times", insertions);
    abugida_ops_free(ops);
}

/* --- tokenisation ---------------------------------------------------- */

static void test_tokenisation(void)
{
    abugida_token t[ABUGIDA_STACK_TOKENS];
    abugida_word w = ABUGIDA_WORD(t, ABUGIDA_STACK_TOKENS);
    size_t i;
    size_t off = 0;

    /* Digraphs are ONE letter: saṅgha is 5 tokens (s a ṅ gh a), not 6. The
     * ṅ stays its own character because Pāli has no ṅgh grapheme — the
     * digraph that follows it is gh. */
    CHECK(abugida_word_from_text(&w, "saṅgha", strlen("saṅgha"), 0, NULL) == ABUGIDA_OK,
          "saṅgha failed");
    CHECK(w.n == 5, "saṅgha is %zu tokens", w.n);
    CHECK(strcmp(abugida_token_text(w.tok[2]), "ṅ") == 0, "saṅgha[2] = %s",
          abugida_token_text(w.tok[2]));
    CHECK(strcmp(abugida_token_text(w.tok[3]), "gh") == 0, "saṅgha[3] = %s",
          abugida_token_text(w.tok[3]));

    /* The ṁ variant of the niggahita is accepted. */
    CHECK(abugida_word_from_text(&w, "saṁgha", strlen("saṁgha"), 0, NULL) == ABUGIDA_OK,
          "saṁgha failed");
    CHECK(w.n == 5 && w.tok[2] == ABUGIDA_TOK_M_DOT, "saṁgha[2] is not ṃ");

    /* Editorial marks are dropped: the compound hyphen and the apostrophe.
     * The uppercase letters are folded here because the C core accepts
     * un-normalised ASCII; NFC and non-ASCII folding are the caller's. */
    CHECK(abugida_word_from_text(&w, "Saṁyutta-Nikāya", strlen("Saṁyutta-Nikāya"), 0, NULL)
              == ABUGIDA_OK, "editorial marks failed");
    CHECK(w.n == 14, "Saṁyutta-Nikāya is %zu tokens", w.n);
    for (i = 0; i < w.n; i++) {
        const char *g = abugida_token_text(w.tok[i]);

        CHECK(g && strcmp(g, "-") != 0 && strcmp(g, "'") != 0,
              "an editorial mark survived at %zu", i);
    }

    /* The Sanskrit phonemes: refused strictly, PRICED leniently. This is the
     * difference between supporting Sanskrit input and absorbing typos — ṣ
     * keeps its coronal bridge to s instead of degrading to an opaque
     * character, which is what makes cross-system comparison possible. */
    CHECK(abugida_cost(ABUGIDA_TOK_S_DOT_BELOW, ABUGIDA_TOK_S) < 1.0,
          "ṣ against s: %.4f",
          abugida_cost(ABUGIDA_TOK_S_DOT_BELOW, ABUGIDA_TOK_S));
    CHECK(abugida_cost(ABUGIDA_TOK_S_ACUTE, ABUGIDA_TOK_S) < 1.0,
          "ś against s: %.4f",
          abugida_cost(ABUGIDA_TOK_S_ACUTE, ABUGIDA_TOK_S));
    CHECK(abugida_cost(ABUGIDA_TOK_S_DOT_BELOW, ABUGIDA_TOK_S)
              < abugida_cost(ABUGIDA_TOK_S_ACUTE, ABUGIDA_TOK_S),
          "ṣ→s should be cheaper than ś→s (shared tongue tip)");
    CHECK(abugida_word_from_text(&w, "kṛṣṇa", strlen("kṛṣṇa"), 1, NULL)
              == ABUGIDA_OK, "kṛṣṇa failed leniently");
    {
        size_t k;
        int foreign = 0;

        for (k = 0; k < w.n; k++)
            if (w.tok[k] >= ABUGIDA_NPLAIN)
                foreign++;
        CHECK(foreign == 2, "kṛṣṇa has %d foreign tokens, not 2", foreign);
    }

    /* Strict rejects, lenient absorbs — and reports where. */
    CHECK(abugida_word_from_text(&w, "qamma", strlen("qamma"), 0, &off)
              == ABUGIDA_ERR_NOT_PALI, "qamma was accepted strictly");
    CHECK(off == 0, "the offending offset is %zu", off);
    CHECK(abugida_word_from_text(&w, "kṛṣṇa", strlen("kṛṣṇa"), 0, &off)
              == ABUGIDA_ERR_SANSKRIT, "kṛṣṇa was not reported as Sanskrit");
    CHECK(abugida_word_from_text(&w, "qamma", strlen("qamma"), 1, NULL) == ABUGIDA_OK,
          "qamma failed leniently");
    CHECK(w.n == 5, "lenient qamma is %zu tokens", w.n);
    CHECK(abugida_cost(w.tok[0], ABUGIDA_TOK_K) == 1.0,
          "an opaque token is not maximally distant");
    CHECK(abugida_cost(w.tok[0], w.tok[0]) == 0.0,
          "an opaque token is not 0 from itself");

    /* A long word exercises the heap path and must agree with the stack. */
    {
        static const char *long_word =
            "abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ";
        abugida_word big;

        abugida_word_init(&big);
        CHECK(abugida_word_from_text(&big, long_word, strlen(long_word), 0,
                                     NULL) == ABUGIDA_OK, "long word failed");
        /* 39 characters, 35 tokens: the doubled consonants and the digraphs
         * collapse. The point of this case is the heap path (more than
         * ABUGIDA_STACK_TOKENS bytes of input) and that freeing a word this
         * library allocated leaves nothing behind. */
        CHECK(big.n == 35, "long word is %zu tokens", big.n);
        abugida_word_free(&big);
        CHECK(big.tok == NULL && big.n == 0, "free left the word dirty");
    }
}

/* --- the pipeline: phonology first, metric second -------------------- */

static void test_pipeline(void)
{
    abugida_string s;
    char *out;

    abugida_string_init(&s);
    out = text_of(&s, "saṃgha", abugida_assimilate_word);
    CHECK(out && strcmp(out, "saṅgha") == 0, "assimilate: %s", out ? out : "?");
    out = text_of(&s, "saṃyutta", abugida_assimilate_word);
    CHECK(out && strcmp(out, "saññutta") == 0, "saṃyutta: %s", out ? out : "?");
    out = text_of(&s, "sakiṃ", abugida_assimilate_word);
    CHECK(out && strcmp(out, "sakiṃ") == 0, "final ṃ: %s", out ? out : "?");
    out = text_of(&s, "abhibhavati", abugida_contract_word);
    CHECK(out && strcmp(out, "abhibhoti") == 0, "contract: %s",
          out ? out : "?");
    out = text_of(&s, "anavakāsa", abugida_contract_word);
    CHECK(out && strcmp(out, "anokāsa") == 0, "anavakāsa: %s",
          out ? out : "?");
    out = text_of(&s, "bhāvayitvā", abugida_contract_word);
    CHECK(out && strcmp(out, "bhāvetvā") == 0, "bhāvayitvā: %s",
          out ? out : "?");
    out = text_of(&s, "saṃghassa", abugida_phonological_form);
    CHECK(out && strcmp(out, "saṅghassa") == 0, "phonological_form: %s",
          out ? out : "?");
    /* Input outside the alphabet passes through unchanged: this is on
     * Lexicon's path, where nothing may fail. */
    out = text_of(&s, "kṛṣṇa", abugida_phonological_form);
    CHECK(out && strcmp(out, "kṛṣṇa") == 0, "kṛṣṇa altered: %s",
          out ? out : "?");
    abugida_string_free(&s);
}

/* The pair the pipeline exists for: raw, saṅgha/saṃgha sits at 0.740 (the
 * units ṅgh and ṃgh differ in their nasal half); after assimilation, at 0. */
static void test_pipeline_moves_the_pair(void)
{
    abugida_string a;
    abugida_string b;
    double raw = distance_of("saṅgha", "saṃgha");
    double resolved;

    abugida_string_init(&a);
    abugida_string_init(&b);
    abugida_assimilate_word(&a, "saṅgha", 8);
    abugida_assimilate_word(&b, "saṃgha", 8);
    resolved = distance_of(a.text, b.text);
    CHECK(CLOSE(raw, 0.740, 1e-3), "raw saṅgha/saṃgha: %.4f", raw);
    CHECK(resolved == 0.0, "assimilated saṅgha/saṃgha: %.4f", resolved);
    abugida_string_free(&a);
    abugida_string_free(&b);
}

/* --- parity with the Python implementation --------------------------- */

/* `pairs.txt` is written by tools/generate_c_tables.py from the PYTHON
 * implementation: each line is two words and the distance between them, and
 * its `indel_weight` header line is the derived constant. Comparing against
 * it is what makes this suite more than self-consistency — the C core is
 * checked against the reference implementation's numbers, over pairs chosen
 * to cover the whole alphabet, both digraph lengths, the heavy units and
 * the epenthetic classes.
 *
 * The path is a parameter so the test can be run from anywhere; `make check`
 * passes it. */
static void test_parity_with_python(const char *path)
{
    FILE *f = fopen(path, "r");
    char line[512];
    int pairs = 0;
    double want_indel = -1.0;
    double want_one_move = -1.0;

    if (!f) {
        /* The fixture is generated, so a missing one is a build step that did
         * not run — reported as a failure rather than silently skipped. */
        printf("FAIL: cannot open %s (run python tools/generate_c_tables.py)\n",
               path);
        failures++;
        checks++;
        return;
    }
    while (fgets(line, sizeof(line), f)) {
        char w1[128];
        char w2[128];
        double want;
        double got;

        if (line[0] == '#')
            continue;
        if (sscanf(line, "const indel_weight %lf", &want) == 1) {
            want_indel = want;
            continue;
        }
        if (sscanf(line, "const one_move %lf", &want) == 1) {
            want_one_move = want;
            continue;
        }
        if (sscanf(line, "%127s %127s %lf", w1, w2, &want) != 3)
            continue;
        got = distance_of(w1, w2);
        CHECK(CLOSE(got, want, 1e-12), "%s/%s: C says %.17g, Python %.17g",
              w1, w2, got, want);
        pairs++;
    }
    fclose(f);
    CHECK(pairs >= 100, "only %d pairs in the fixture", pairs);
    if (want_indel > 0.0)
        CHECK(CLOSE(abugida_indel_weight(), want_indel, 1e-15),
              "INDEL_WEIGHT: C %.17g, Python %.17g", abugida_indel_weight(),
              want_indel);
    if (want_one_move > 0.0)
        CHECK(CLOSE(abugida_one_move(), want_one_move, 1e-15),
              "ONE_MOVE: C %.17g, Python %.17g", abugida_one_move(),
              want_one_move);
}

int main(int argc, char **argv)
{
    const char *pairs = argc > 1 ? argv[1] : "pairs.txt";

    printf("abugida C core — ABI %d, %d tokens, %d graphemes\n",
           ABUGIDA_TABLES_ABI_VERSION, ABUGIDA_NTOKENS, ABUGIDA_NPLAIN);

    test_vocabulary();
    test_published_scale();
    test_balance_principle();
    test_within_series_gradients();
    test_cost_is_a_metric();
    test_indel_conditions();
    test_word_distance_properties();
    test_documented_examples();
    test_levenshtein_baseline();
    test_geminates();
    test_aspirated_geminate();
    test_epenthetic_doublets();
    test_alignment_conserves_the_distance();
    test_alignment_reports_the_edit();
    test_deletion_and_insertion_reports();
    test_tokenisation();
    test_pipeline();
    test_pipeline_moves_the_pair();
    test_parity_with_python(pairs);

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
