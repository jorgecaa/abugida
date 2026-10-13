/* Myers' bit-parallel algorithm for the flat (unit-cost) edit distance.
 *
 * WHY THIS EXISTS, AND WHY IT IS NOT THE WEIGHTED DISTANCE
 * -------------------------------------------------------
 * `levenshtein` counts edits, so every cell holds a small integer. That is
 * what makes it computable 64 cells at a time inside machine words: Myers'
 * observation (JACM 1999) is that the difference between adjacent cells is
 * +1, -1 or 0, so a whole row of the DP can be carried as two bit-vectors —
 * one for "the difference is positive here", one for negative — and a step
 * becomes four bit operations instead of a column of adds and mins.
 *
 * `distance` cannot use this and never will: its substitution costs are real
 * numbers from a table, so adjacent cells do not differ by ±1 and there is no
 * bit-vector to carry. That is why this file is about `levenshtein` alone,
 * and why the plan in docs/asm-plan.md spends its effort here.
 *
 * WHAT IT BUYS, MEASURED
 * ---------------------
 * `tools/myers_prototype.c` runs the same three pairs through both kernels:
 * 8x on a 5-token pair, 32x on an 11-token pair, 53x on a 35-token pair. The
 * gain grows with the word because this is O(n) steps for a word of up to 64
 * tokens where the DP is O(n*m) cells.
 *
 * At the Python API the gain is smaller and it is worth being honest about
 * which number applies: on a single call it is 1.3x-4.0x because tokenising
 * both words is a fixed cost, and on a LEXICON SWEEP — which is what actually
 * consumes `levenshtein`, as the baseline in `eval/head_to_head.py`,
 * `eval/compare_levenshtein.py` and `eval/hard_battery.py` — it is 2.7x,
 * because there the fixed cost is amortised over 500 candidates.
 *
 * THE LIMIT
 * ---------
 * One 64-bit word per row means the SECOND word must have at most 64 tokens —
 * a DP row is indexed by it — so the kernel works on the shorter side and
 * declines (`abugida_word_levenshtein` falls back to the DP) only when BOTH
 * words are longer than that. It ALSO declines a word containing an opaque
 * token, because those have negative ids and the pattern table is indexed by
 * token id; see the bounds check in the body. The longest
 * word in the parity fixture is 35 tokens, and 64 covers every realistic Pāli
 * compound — including the 35-token
 * `abhidhammapiṭakapakaraṇassaṭṭhakathāyaṃ`. The multi-word block variant
 * exists in the literature and is deliberately NOT implemented: its carry
 * propagation between words is where the bugs live, the payoff applies only
 * to words longer than any attested Pāli one, and the DP already handles them
 * correctly.
 *
 * WHAT IT MUST NOT BREAK
 * ----------------------
 * The result must be the same integer the DP returns, for every input, or
 * `tests/test_c_parity.py` and `tools/differential.py` fail. `test_myers.c`
 * checks that directly over every pair of a token corpus plus the boundary
 * cases; the two implementations are not "close", they are equal.
 */

#include "abugida.h"

#include <stdint.h>
#include <string.h>

/* COMPILED ONCE PER VARIANT.
 *
 * The same source produces `abugida_levenshtein_myers_c`,
 * `..._myers_sse2` and `..._myers_avx2` — one translation unit each, differing
 * only in the `-m` flags — and a dispatcher in `abugida.c` picks between them.
 * That is what makes the assembly of `docs/asm-plan.md` phase 2 a drop-in: an
 * assembly file defines the same three names and nothing above it moves.
 *
 * The suffix is a macro rather than a build-time rename so the names are
 * visible in the source. Defining none of them (which is what a plain
 * `cc csrc/abugida_myers.c` does) produces the unsuffixed names, so the file
 * still stands alone. */
#ifdef ABUGIDA_MYERS_SUFFIX
#define MYERS_CAT2(a, b) a##b
#define MYERS_CAT(a, b) MYERS_CAT2(a, b)
#define MYERS(name) MYERS_CAT(name, ABUGIDA_MYERS_SUFFIX)
#else
#define MYERS(name) name
#endif

/*: Returned when the pattern is longer than one machine word. */
#define ABUGIDA_MYERS_NOT_APPLICABLE (-1L)

/*: Whether every token of a word can index the pattern table. An opaque token
 * is negative by construction, and the table is indexed by token id. */
static int word_is_indexable(const abugida_word *w)
{
    size_t i;

    for (i = 0; i < w->n; i++) {
        abugida_token t = w->tok[i];

        if (t < 0 || t >= ABUGIDA_NTOKENS)
            return 0;
    }
    return 1;
}

int MYERS(abugida_levenshtein_myers_applicable)(const abugida_word *a,
                                         const abugida_word *b)
{
    size_t shorter;

    if (!a || !b)
        return 0;
    /* The SHORTER side is what has to fit, because that is the one the kernel
     * carries in the bit-vector; the longer one is merely walked, a token at
     * a time, and its length costs steps rather than bits. So a 65-token word
     * against a 12-token one is well inside the range — the first version of
     * this predicate demanded both fit and declined work it could do.
     *
     * The token check is the other half, and it is not a formality: the
     * kernel indexes `peq` by token id, so a word with an opaque token cannot
     * be handed to it at all. Both halves live here, so that the predicate
     * and the kernel cannot disagree about what is applicable — they did
     * once, and this test caught it. */
    shorter = a->n < b->n ? a->n : b->n;
    return shorter <= ABUGIDA_MYERS_WORD_BITS
        && word_is_indexable(a) && word_is_indexable(b);
}

long MYERS(abugida_levenshtein_myers)(const abugida_word *a,
                                      const abugida_word *b)
{
    /* One bit per token of the SECOND word: `peq[t]` has a 1 wherever token t
     * occurs in `b`. Indexed by token id, so it is a dense array over the
     * vocabulary — no hashing, no branching. */
    uint64_t peq[ABUGIDA_NTOKENS];
    uint64_t pv;
    uint64_t mv;
    uint64_t eq;
    uint64_t xv;
    uint64_t xh;
    uint64_t ph;
    uint64_t mh;
    const uint64_t one = 1;
    uint64_t top;
    long score;
    size_t i;
    /* The two roles, named for what they do rather than for which argument
     * they came from. `bits` is the word the bit-vector describes — the
     * SECOND one, because a row of the DP is indexed by it — so it is the
     * side that has to fit in a machine word. `steps` is the word walked one
     * token at a time, and its length costs iterations, not bits.
     *
     * Getting these the wrong way round is why the first version of this file
     * returned 127 for a 65-token pair: it sized the bit-vector from the
     * pattern and then addressed it with the text's indices. */
    const abugida_token *walked;
    const abugida_token *vectored;
    size_t steps;
    size_t bits;

    if (!a || !b)
        return ABUGIDA_MYERS_NOT_APPLICABLE;

    /* The bit-vector carries the SHORTER word, so the shorter one is
     * `vectored` and the longer is walked. */
    if (a->n <= b->n) {
        vectored = a->tok;
        bits = a->n;
        walked = b->tok;
        steps = b->n;
    } else {
        vectored = b->tok;
        bits = b->n;
        walked = a->tok;
        steps = a->n;
    }
    if (bits > ABUGIDA_MYERS_WORD_BITS)
        return ABUGIDA_MYERS_NOT_APPLICABLE;

    /* Degenerate sides, before any bit trickery: an empty word costs one edit
     * per token of the other, and the DP's answer is the same. */
    if (bits == 0)
        return (long)steps;
    if (steps == 0)
        return (long)bits;

    /* `peq` is indexed by token id, so a token outside [0, ABUGIDA_NTOKENS)
     * is an out-of-bounds read — and an OPAQUE token is NEGATIVE by
     * construction (it is `ABUGIDA_NO_TOKEN - slot`, and `ABUGIDA_NO_TOKEN`
     * is -1). A word with a mistyped character therefore reached the table at
     * a negative index: usually still inside the array, so it was silently
     * wrong rather than a crash, and this file's own corpus of non-negative
     * ids never noticed. The differential harness did, on the first run.
     *
     * The kernel declines such a word and the dynamic program answers it
     * instead — the DP compares tokens by value and has no such requirement.
     * That is the right place to pay: a word with an opaque token is a
     * misspelling, and `levenshtein` exists to measure the baseline ON
     * misspellings, so being right matters more there than being fast.
     *
     * The check is `applicable`'s, not a second copy of it. */
    if (!MYERS(abugida_levenshtein_myers_applicable)(a, b))
        return ABUGIDA_MYERS_NOT_APPLICABLE;

    memset(peq, 0, sizeof peq);
    for (i = 0; i < bits; i++)
        peq[vectored[i]] |= one << i;

    pv = ~(uint64_t)0; /* the positive vertical deltas, all set to begin */
    mv = 0;            /* and the negative ones clear */
    score = (long)bits; /* the last cell of a row against nothing */
    top = one << (bits - 1);

    for (i = 0; i < steps; i++) {
        eq = peq[walked[i]];

        /* Myers' four lines. `xh` carries the borrow out of the addition, and
         * that borrow IS the "does this cell start a new run of +1" answer —
         * the whole algorithm is this one observation. */
        xv = eq | mv;
        xh = (((eq & pv) + pv) ^ pv) | eq;
        ph = mv | ~(xh | pv);
        mh = pv & xh;

        /* The score follows the top cell's delta, which is why it is read
         * before the shift discards it. */
        if (ph & top)
            score++;
        if (mh & top)
            score--;

        ph = (ph << 1) | one;
        mh = mh << 1;
        pv = mh | ~(xv | ph);
        mv = ph & xv;
    }
    return score;
}
