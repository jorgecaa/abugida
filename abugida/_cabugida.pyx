# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""The Cython binding: the C core, as the Python package's own modules.

This module is a BINDING, not the implementation. Everything the metric is —
the grapheme inventory, the substitution table, the dynamic program, the
alignment traceback, the sandhi pipeline — lives in `csrc/abugida.c` and is
reached through the declarations below. What happens here is marshalling:
Python bytes in, C arrays and doubles out, and the reverse for the answers.

Four things are worth knowing before reading it.

1. `iast.normalize` stays in Python. NFC composition and case folding need
   the Unicode character database, and the C core's contract is that it
   receives NFC-normalised lowercase IAST. `normalize` here calls
   `unicodedata` and hands the result to the C tokeniser, so the Python API's
   behaviour is unchanged bit for bit while the metric itself needs no
   Unicode tables. The core still folds ASCII uppercase and accepts the ṁ
   spelling, so a caller that skips normalisation is not silently wrong.

2. Token ids, not grapheme strings. A word crosses into C as an `int16`
   array of token ids and comes back the same way. This is what makes the
   binding thin: no string building in either direction inside a loop.

3. `_edit` exists for one reason: `distance.weighted_distance`, the
   experimental L1 variant, needs a substitution cost the C core does not
   know about. So the DP is exported in a form that takes Python callables,
   and the two costs the core DOES know — the phonological table and the flat
   one — are passed as C function pointers instead. Both go through the same
   recurrence, in C; there is no second implementation to keep in step.

4. Exceptions are raised here, from status codes. The C core never longjmps
   and never prints: it returns `abugida_status`, and the message a user sees
   is assembled on this side.
"""

from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_GET_SIZE
from libc.stdlib cimport free, malloc
from libc.string cimport memset

import unicodedata

from abugida.phonology import BY_GRAPHEME, INVENTORY, PLACES

cdef extern from "abugida.h":
    # --- status and the vocabulary -------------------------------------
    ctypedef enum abugida_status:
        ABUGIDA_OK
        ABUGIDA_ERR_NOT_PALI
        ABUGIDA_ERR_SANSKRIT
        ABUGIDA_ERR_NOMEM
        ABUGIDA_ERR_CAPACITY
        ABUGIDA_ERR_INVALID

    const char *abugida_strerror(abugida_status st)
    const char *abugida_token_text_len(short t, size_t *len)

    int ABUGIDA_NTOKENS
    int ABUGIDA_NPLAIN
    int ABUGIDA_TABLES_ABI_VERSION

    short ABUGIDA_NO_TOKEN
    short ABUGIDA_TOK_K
    short ABUGIDA_TOK_K_H
    short ABUGIDA_TOK_G
    short ABUGIDA_TOK_T_T
    short ABUGIDA_TOK_T
    short ABUGIDA_TOK_A
    short ABUGIDA_TOK_AA
    short ABUGIDA_TOK_M_DOT

    double abugida_cost(short a, short b)
    double abugida_indel(short t)
    double abugida_neutral_modifier_weight()
    double abugida_indel_weight()
    double abugida_one_move()

    # --- words ---------------------------------------------------------
    ctypedef struct abugida_word:
        short *tok
        size_t n
        size_t cap
        int heap

    ctypedef struct abugida_string:
        char *text
        size_t n
        size_t cap
        int heap

    void abugida_word_init(abugida_word *w)
    void abugida_word_free(abugida_word *w)
    abugida_status abugida_word_alloc(abugida_word *w, size_t capacity)
    abugida_status abugida_word_from_text(abugida_word *w, const char *text,
                                          size_t len, int lenient,
                                          size_t *err_off)
    short abugida_token_from_text(const char *text, size_t len)
    short abugida_foreign_token(unsigned long codepoint)
    abugida_status abugida_diagnose(const char *text, size_t len, size_t *offs,
                                    int *kinds, size_t cap, size_t *n)

    # --- the metric ----------------------------------------------------
    ctypedef double (*abugida_sub_fn)(short a, short b, void *ctx)
    ctypedef double (*abugida_indel_fn)(short t, void *ctx)

    double abugida_sub_phonological(short a, short b, void *ctx)
    double abugida_indel_derived(short t, void *ctx)
    double abugida_sub_flat(short a, short b, void *ctx)
    double abugida_indel_flat(short t, void *ctx)

    abugida_status abugida_edit(const short *a, size_t na,
                                const short *b, size_t nb,
                                abugida_sub_fn substitution, void *sub_ctx,
                                abugida_indel_fn indel, void *indel_ctx,
                                double *out)
    abugida_status abugida_word_distance(const abugida_word *a,
                                         const abugida_word *b, double *out)
    abugida_status abugida_word_distance_bounded(const abugida_word *a,
                                                 const abugida_word *b,
                                                 double bound, int *beyond,
                                                 double *out)
    abugida_status abugida_word_levenshtein(const abugida_word *a,
                                            const abugida_word *b, long *out)
    int abugida_impl_select(const char *name)
    const char *abugida_impl_name()
    int abugida_impl_count()
    const char *abugida_impl_at(int i)

    ctypedef enum abugida_op_kind:
        ABUGIDA_OP_KEEP
        ABUGIDA_OP_SUB
        ABUGIDA_OP_DEL
        ABUGIDA_OP_INS

    ctypedef struct abugida_op:
        abugida_op_kind op
        short left
        short right
        double cost

    abugida_status abugida_word_align(const abugida_word *a,
                                      const abugida_word *b,
                                      abugida_op **ops, size_t *nops)
    const char *abugida_op_name(abugida_op_kind op)
    void abugida_ops_free(abugida_op *ops)

    # --- the pipeline --------------------------------------------------
    abugida_status abugida_assimilate_word(abugida_string *out,
                                           const char *text, size_t len)
    abugida_status abugida_contract_word(abugida_string *out,
                                         const char *text, size_t len)
    abugida_status abugida_phonological_form(abugida_string *out,
                                             const char *text, size_t len)
    void abugida_string_init(abugida_string *s)
    void abugida_string_free(abugida_string *s)


#: The Python names for the operations, in the order the Python API has
#: always returned them.
_OP_NAMES = ("keep", "sub", "del", "ins")


# --- raising, from status codes ------------------------------------------

cdef object _error(abugida_status st, bytes word, size_t off):
    """The exception a failed call raises, with the message the pure-Python
    implementation would have used."""
    cdef bytes tail
    cdef str char
    cdef str text
    cdef Py_ssize_t length = len(word)

    if st == ABUGIDA_ERR_NOMEM:
        return MemoryError("abugida: out of memory")
    # `off` is a BYTE offset into the input — that is what the C core counts,
    # because that is what it scans. Slicing the decoded string with it would
    # cut in the middle of a character and report an empty string: the
    # message a caller sees must name the character that failed, so the slice
    # is taken in bytes and only then decoded.
    tail = word[off:] if off < <size_t>length else b""
    char = ""
    if tail:
        # The length comes from the lead byte, exactly as the core's decoder
        # reads it: guessing by trying 2, then 3, then 4 would cut "qamma" at
        # "qa" — the ASCII first byte is a valid one-byte character, so the
        # message would name a character the tokeniser never rejected.
        lead = <unsigned char>tail[0]
        if lead < 0x80:
            size = 1
        elif lead & 0xE0 == 0xC0:
            size = 2
        elif lead & 0xF0 == 0xE0:
            size = 3
        elif lead & 0xF8 == 0xF0:
            size = 4
        else:
            size = 1
        char = tail[:size].decode("utf-8", "replace")
    text = word.decode("utf-8", "replace")
    if st == ABUGIDA_ERR_SANSKRIT:
        return ValueError(f"{char!r} in {text!r} is Sanskrit IAST, not Pāli")
    return ValueError(f"{char!r} in {text!r} is not a Pāli grapheme")


cdef inline str _canonical(str word):
    """NFC, lowercase, the ṁ spelling folded — but only when it would change
    anything.

    All three operations are idempotent, and a word that is already canonical
    is what a lexicon holds and what a caller passes on the second call, so
    the common case must not pay for them. The check is the same one
    `iast.normalize` does minus the copy: `str.islower()` is False the moment
    a single cased character is not lowercase, and NFC is verified by
    comparing against the composed form. When both hold, the word is returned
    as it came, which is also what makes `distance` cost what it did before
    this existed.
    """
    cdef str lowered

    # An ASCII word is already NFC, and `islower` is the only question left.
    # Pāli words are mostly ASCII, so this is the branch that runs.
    if word.isascii():
        return word if word.islower() else word.lower()
    if "\u1e41" not in word and word.islower() \
            and unicodedata.is_normalized("NFC", word):
        return word
    lowered = word.lower().replace("\u1e41", "\u1e43")
    return unicodedata.normalize("NFC", lowered)


cdef inline bytes _utf8(str word):
    """The C core's input. Encoded here rather than through a `char*` so that
    a string with a surrogate raises Python's own UnicodeEncodeError instead
    of producing bytes the core would silently misread."""
    return word.encode("utf-8")


# --- words ----------------------------------------------------------------

cdef class Tokens:
    """A token sequence: the C core's `abugida_word`, owned by Python.

    Exposed as a class rather than a bare capsule so the buffer is freed
    deterministically when the last reference goes, and so `distance` and
    `alignment` can share one tokenisation when a caller does both.
    """

    cdef abugida_word _w

    def __cinit__(self):
        abugida_word_init(&self._w)

    def __dealloc__(self):
        abugida_word_free(&self._w)

    @classmethod
    def from_text(cls, str word, bint lenient=False):
        """Tokenise a word. Raises ValueError for input outside the Pāli
        alphabet unless `lenient`, exactly as `iast.tokenize` does.

        The word is NORMALISED here, and this is the only place tokens enter
        the binding, so every function built on it inherits the guarantee:
        NFC, lowercase, the ṁ spelling folded. That matters because the C
        core's contract (`csrc/abugida.h`) is to receive normalised IAST — it
        folds ASCII case only. Without this, `distance("Bh", "bh")` returned
        1.34 where the reference returns 0.0, and `alignment` split `Bh` into
        `b` + `h`: the same function, two answers, decided by which layer a
        caller happened to reach.

        The cost is one `unicodedata.normalize` plus a lower() per word —
        about 1.4 us against a DP that costs 2 us for a short pair, and it is
        the price of the two implementations being the same function rather
        than two functions that agree on lowercase input.
        """
        cdef Tokens self = cls()
        cdef bytes raw

        word = _canonical(word)
        raw = _utf8(word)
        cdef const char *data = PyBytes_AS_STRING(raw)
        cdef size_t off = 0
        cdef abugida_status st = abugida_word_from_text(
            &self._w, data, PyBytes_GET_SIZE(raw), 1 if lenient else 0, &off)
        if st != ABUGIDA_OK:
            raise _error(st, raw, off)
        return self

    @classmethod
    def from_ids(cls, ids):
        """Wrap a sequence of token ids — for callers that already have
        them, and for the tests that compare tokenisations."""
        cdef Tokens self = cls()
        cdef Py_ssize_t i, n = len(ids)
        cdef long value
        if abugida_word_alloc(&self._w, <size_t>(n if n else 1)) != ABUGIDA_OK:
            raise MemoryError("abugida: out of memory")
        for i in range(n):
            value = ids[i]
            self._w.tok[i] = <short>value
        self._w.n = <size_t>n
        return self

    def __len__(self):
        return self._w.n

    def ids(self):
        """The token ids, as a list of ints."""
        return [self._w.tok[i] for i in range(self._w.n)]

    def texts(self):
        """The graphemes, as a list of strings. An opaque token decodes back
        to the character it stands for, so a lenient tokenisation round-trips
        the input instead of reporting None for the parts it absorbed."""
        return [text_of(self._w.tok[i]) for i in range(self._w.n)]

    def __repr__(self):
        return f"Tokens({' '.join(self.texts())!r})"


cdef inline Tokens _as_tokens(word, bint lenient):
    """Accept a string or an already-tokenised word."""
    if isinstance(word, Tokens):
        return <Tokens>word
    return Tokens.from_text(word, lenient)


def tokenize(word, bint lenient=False):
    """Split an IAST word into its graphemes, as a list of strings.

    The C tokeniser: longest match, so `kh` is one letter; strict unless
    `lenient`, in which case a character outside the alphabet is kept as its
    own opaque token. The word must already be NFC-normalised and lowercase —
    `iast.normalize` is what does that, and `distance` and its friends
    normalise before they get here.
    """
    return Tokens.from_text(word, lenient).texts()


def diagnose(word):
    """The characters strict tokenisation would reject, as
    (index, character, kind) with kind in {"sanskrit", "unknown"} over the
    NORMALISED text. Never raises: an empty list means the word tokenises
    strictly. `index` is a PYTHON character index, not a byte offset — the
    binding translates, so a caller can slice the string it passed in."""
    cdef bytes raw = _utf8(word)
    cdef size_t cap = 64
    cdef size_t *offs = <size_t *>malloc(cap * sizeof(size_t))
    cdef int *kinds = <int *>malloc(cap * sizeof(int))
    cdef size_t n = 0
    cdef abugida_status st
    cdef size_t i
    cdef list out = []

    if offs == NULL or kinds == NULL:
        if offs != NULL:
            free(offs)
        if kinds != NULL:
            free(kinds)
        raise MemoryError("abugida: out of memory")
    try:
        st = abugida_diagnose(PyBytes_AS_STRING(raw), PyBytes_GET_SIZE(raw),
                              offs, kinds, cap, &n)
        if st != ABUGIDA_OK:
            raise _error(st, raw, 0)
        text = word
        for i in range(n if n < cap else cap):
            # Byte offset to character index: the caller slices a string.
            out.append((len(raw[:offs[i]].decode("utf-8")),
                        text[len(raw[:offs[i]].decode("utf-8"))],
                        "sanskrit" if kinds[i] == 1 else "unknown"))
    finally:
        free(offs)
        free(kinds)
    return out


# --- cost -----------------------------------------------------------------

def cost(g1, g2):
    """Cost of substituting grapheme `g1` with `g2`, in [0, 1].

    The table itself lives in C, generated from `distance.cost`; characters
    outside the inventory (a typo, in lenient mode) are opaque and cost 1
    against everything and 0 against themselves.
    """
    cdef bytes b1 = _utf8(g1)
    cdef bytes b2 = _utf8(g2)
    if b1 == b2:
        return 0.0
    cdef short t1 = _token_of(b1)
    cdef short t2 = _token_of(b2)
    if t1 == ABUGIDA_NO_TOKEN or t2 == ABUGIDA_NO_TOKEN:
        return 1.0
    return abugida_cost(t1, t2)


cdef short _token_of(bytes text):
    """The token a grapheme or Sanskrit phoneme stands for, or
    ABUGIDA_NO_TOKEN.

    The C lookup covers the inventory and the long consonants. The Sanskrit
    phonemes are tokens but not graphemes, so they are looked up here — which
    is why `cost('ṣ','s')` prices the coronal bridge instead of returning the
    opaque 1.0.

    The whole of `text` must be ONE character for that second lookup, because
    that is what the reference does: `FOREIGN.get(g)` is keyed by the whole
    string. Decoding just the first character would be more helpful — it would
    make `cost("a", "śānti")` answer with the cost of ś — and it would also be
    a difference from the reference, which returns 1.0 there. A port that
    improves on its reference is a port that disagrees with it.
    """
    cdef short t = abugida_token_from_text(PyBytes_AS_STRING(text),
                                           PyBytes_GET_SIZE(text))
    cdef Py_ssize_t n = PyBytes_GET_SIZE(text)
    cdef const char *p = PyBytes_AS_STRING(text)
    cdef unsigned long cp
    cdef unsigned char lead
    cdef int need
    cdef Py_ssize_t k

    if t != ABUGIDA_NO_TOKEN:
        return t
    if n == 0:
        return ABUGIDA_NO_TOKEN
    cp = _decode_utf8(text)
    if cp == 0:
        return ABUGIDA_NO_TOKEN
    # Exactly one character? (`_decode_utf8` consumes the whole buffer for a
    # single character, and only reports the first otherwise.)
    # `p[0]` is a `char`, which is SIGNED on this target: compared against
    # 0x80 directly it is always less (a negative byte is too), so the first
    # branch would swallow every lead byte and the three after it would be
    # dead. It is cast to unsigned once, which is also what the core's
    # decoder does.
    lead = <unsigned char>p[0]
    if lead < 0x80:
        need = 1
    elif lead & 0xE0 == 0xC0:
        need = 2
    elif lead & 0xF0 == 0xE0:
        need = 3
    elif lead & 0xF8 == 0xF0:
        need = 4
    else:
        return ABUGIDA_NO_TOKEN
    if n != need:
        return ABUGIDA_NO_TOKEN
    for k in range(1, need):
        if (p[k] & 0xC0) != 0x80:
            return ABUGIDA_NO_TOKEN
    return abugida_foreign_token(cp)


cdef unsigned long _decode_utf8(bytes text):
    """Decode one UTF-8 character from the front of `text`; 0 on anything the
    decoder does not accept. Used only for the three Sanskrit phonemes, so it
    does not need to be a general-purpose decoder."""
    cdef const unsigned char *p = <const unsigned char *>PyBytes_AS_STRING(text)
    cdef Py_ssize_t n = PyBytes_GET_SIZE(text)
    cdef unsigned long cp
    cdef int need
    cdef int k

    if n == 0:
        return 0
    if p[0] < 0x80:
        return p[0]
    if p[0] & 0xE0 == 0xC0:
        need, cp = 2, p[0] & 0x1F
    elif p[0] & 0xF0 == 0xE0:
        need, cp = 3, p[0] & 0x0F
    elif p[0] & 0xF8 == 0xF0:
        need, cp = 4, p[0] & 0x07
    else:
        return 0
    if n < need:
        return 0
    for k in range(1, need):
        if p[k] & 0xC0 != 0x80:
            return 0
        cp = (cp << 6) | (p[k] & 0x3F)
    return cp


def algebraic_cost(x, y):
    """Generator moves of ⊗ between two values of A: 0, 1 or 2.

    Arithmetic on the two coordinates, not a metric of the embedding — it
    lives here because it is the algebra the costs are built from.
    """
    return int(x.base != y.base) + int(x.mod != y.mod)


def indel(g):
    """The insertion/deletion cost of a grapheme: the derived epenthetic
    weight for the class whose loss is ordinary transmission variation, 1.0
    for everything else."""
    cdef bytes b = _utf8(g)
    cdef short t = abugida_token_from_text(PyBytes_AS_STRING(b),
                                           PyBytes_GET_SIZE(b))
    return abugida_indel(t)


# --- the metric -----------------------------------------------------------

def distance(word1, word2, bint lenient=False):
    """Phonological distance between two IAST words."""
    cdef Tokens a = _as_tokens(word1, lenient)
    cdef Tokens b = _as_tokens(word2, lenient)
    cdef double out = 0.0
    cdef abugida_status st = abugida_word_distance(&a._w, &b._w, &out)
    if st != ABUGIDA_OK:
        raise _error(st, b"", 0)
    return out


def impl_name():
    """The kernel variant that answers `levenshtein`: "c", "sse2" or "avx2" —
    or "dp" in a build without the bit-parallel kernel, where the dynamic
    program answers everything.

    There is one source for the kernel (`csrc/abugida_myers.c`) compiled once
    per instruction set, and the choice is made once per process. It is the
    same arrangement `distance.USING_C` reports the outer half of."""
    return (<bytes>abugida_impl_name()).decode()


def impl_names():
    """Every variant this build contains, in the order the dispatcher prefers
    them. A test walks this rather than assuming a machine's set: a variant
    that is only exercised on the CPU of whoever wrote it is a variant nobody
    has checked."""
    cdef int i
    cdef int n = abugida_impl_count()

    return [(<bytes>abugida_impl_at(i)).decode() for i in range(n)]


def impl_select(name=None):
    """Force a variant by name, or `None` for the fastest this CPU supports.

    This is what makes the variants testable in one process, and what a bug
    report should carry: "which kernel answered" is not answerable from a
    number. An unknown name raises ValueError rather than being ignored —
    silently running a different variant than the one asked for would make a
    test that believes it verified `sse2` verify nothing."""
    cdef bytes raw
    cdef int st

    if name is None:
        raw = b""
    else:
        raw = _utf8(name)
    st = abugida_impl_select(<const char *>raw if raw else NULL)
    if st != ABUGIDA_OK:
        raise ValueError(f"{name!r} is not a kernel variant this build has: "
                         f"{impl_names()}")


def distance_bounded(word1, word2, bound, bint lenient=False):
    """The distance between two words, or `(None, True)` when it is ABOVE
    `bound`.

    Returns `(distance, False)` when the distance is at most `bound` — the
    same double `distance` gives, bit for bit — and `(None, True)` when it is
    provably above it. Not a sentinel value: a caller who wants a number
    cannot accidentally receive one, because it has to unpack the flag to get
    at the value at all.

    Why this exists: a candidate whose distance is above `bound` is going to
    be discarded, so the dynamic program does not need to finish. It stops
    once a whole row's minimum exceeds the bound — a path cost is
    non-negative, so that row's minimum is already a lower bound on every
    extension of every path through it. The bound is the row's own minimum,
    so no per-token weight has to be assumed: `bound = 1.5` is measured 3.4x
    fewer rows on a real search pool.

    `bound` must be positive; `distance` is the function for a plain
    distance."""
    cdef Tokens a = _as_tokens(word1, lenient)
    cdef Tokens b = _as_tokens(word2, lenient)
    cdef double out = 0.0
    cdef int beyond = 0
    cdef abugida_status st

    if not (bound > 0.0):
        raise ValueError("bound must be positive; use distance() instead")
    st = abugida_word_distance_bounded(&a._w, &b._w, bound, &beyond, &out)
    if st != ABUGIDA_OK:
        raise _error(st, b"", 0)
    if beyond:
        return (None, True)
    return (out, False)


def levenshtein(word1, word2, bint lenient=False):
    """Classic Levenshtein over the SAME tokens (kh = one letter)."""
    cdef Tokens a = _as_tokens(word1, lenient)
    cdef Tokens b = _as_tokens(word2, lenient)
    cdef long out = 0
    cdef abugida_status st = abugida_word_levenshtein(&a._w, &b._w, &out)
    if st != ABUGIDA_OK:
        raise _error(st, b"", 0)
    return out


# --- the DP with caller-supplied costs ------------------------------------

# The two callables the DP can be given when it is not running one of the
# costs the C core implements natively. They live in module globals rather
# than in a context struct because a C struct cannot hold a Python object;
# `edit` is not reentrant (it runs one DP to completion under the GIL and
# clears them afterwards), which is what makes this safe, and the `finally`
# in `edit` is what keeps a raising callable from leaving them behind.
cdef object _SUB_CALLBACK = None
cdef object _INDEL_CALLBACK = None


cdef double _sub_py(short a, short b, void *ctx) noexcept with gil:
    """The substitution callable the DP calls when it is not one of the two
    costs the C core knows."""
    return <double>_SUB_CALLBACK(a, b)


cdef double _indel_py(short t, void *ctx) noexcept with gil:
    return <double>_INDEL_CALLBACK(t)

def substitution_phonological(a, b):
    """The phonological substitution cost, as a plain Python callable.

    Hand this to `edit` and the DP runs it natively in C: `edit` recognises
    this function by identity, so no Python frame is created per cell. It
    exists to be named, not to be fast on its own.
    """
    return abugida_cost(a, b)


def indel_derived(t):
    """The derived insertion/deletion weight, as a plain Python callable.
    Recognised by `edit` the same way `substitution_phonological` is."""
    return abugida_indel(t)


def substitution_flat(a, b):
    """Every substitution costs 1 unless the tokens are equal: the flat cost
    of `levenshtein`, exposed for `edit`."""
    return 0.0 if a == b else 1.0


def indel_flat(t):
    """Every insertion or deletion costs 1."""
    return 1.0


def edit(object tokens1, object tokens2, substitution, indel_cost):
    """The weighted edit distance over two token sequences, with the given
    substitution and insertion/deletion costs.

    `tokens1` and `tokens2` are `Tokens` objects or sequences of token ids;
    the costs are callables taking token ids. This is the extension point for
    a different geometry (`distance.weighted_distance` uses it); the
    phonological and flat costs are recognised and run natively.
    """
    cdef Tokens a = tokens1 if isinstance(tokens1, Tokens) else \
        Tokens.from_ids(tokens1)
    cdef Tokens b = tokens2 if isinstance(tokens2, Tokens) else \
        Tokens.from_ids(tokens2)
    cdef double out = 0.0
    cdef abugida_status st
    cdef abugida_sub_fn sub_fn
    cdef abugida_indel_fn ind_fn
    global _SUB_CALLBACK, _INDEL_CALLBACK

    if not callable(substitution):
        raise TypeError("substitution must be callable")
    if not callable(indel_cost):
        raise TypeError("indel must be callable")
    # Identity, not equality: naming these functions is the documented way to
    # ask for a cost the core computes natively, and an equal-but-different
    # callable takes the general (slower) path, which is the safe direction.
    if substitution is substitution_phonological:
        sub_fn = abugida_sub_phonological
    elif substitution is substitution_flat:
        sub_fn = abugida_sub_flat
    else:
        _SUB_CALLBACK = substitution
        sub_fn = _sub_py
    if indel_cost is indel_derived:
        ind_fn = abugida_indel_derived
    elif indel_cost is indel_flat:
        ind_fn = abugida_indel_flat
    else:
        _INDEL_CALLBACK = indel_cost
        ind_fn = _indel_py

    try:
        st = abugida_edit(a._w.tok, a._w.n, b._w.tok, b._w.n, sub_fn, NULL,
                          ind_fn, NULL, &out)
    finally:
        _SUB_CALLBACK = None
        _INDEL_CALLBACK = None
    if st != ABUGIDA_OK:
        raise _error(st, b"", 0)
    return out


#: The two costs `edit` recognises, so a caller can ask for a cost the core
#: computes natively instead of shipping a Python callable per cell:
#: `edit(t1, t2, substitution_phonological, indel_derived)` is `distance`
#: without the argument checking, and the `_flat` pair is `levenshtein`.
PHONOLOGICAL = substitution_phonological
FLAT = substitution_flat


# --- alignment ------------------------------------------------------------

def alignment(word1, word2, bint lenient=False):
    """The optimal edit script: (op, from, to, cost) per operation, with op
    in {"keep", "sub", "del", "ins"}. The costs sum exactly to `distance`."""
    cdef Tokens a = _as_tokens(word1, lenient)
    cdef Tokens b = _as_tokens(word2, lenient)
    cdef abugida_op *ops = NULL
    cdef size_t nops = 0
    cdef size_t i
    cdef abugida_status st

    st = abugida_word_align(&a._w, &b._w, &ops, &nops)
    if st != ABUGIDA_OK:
        raise _error(st, b"", 0)
    out = []
    try:
        for i in range(nops):
            # `text_of` rather than the raw C lookup, so an opaque token
            # reports the character it stands for: a lenient alignment of
            # "qamma" against "kamma" says sub q→k, not sub None→k.
            out.append((
                _OP_NAMES[<int>ops[i].op - 1],
                text_of(ops[i].left) if ops[i].left != ABUGIDA_NO_TOKEN
                else None,
                text_of(ops[i].right) if ops[i].right != ABUGIDA_NO_TOKEN
                else None,
                ops[i].cost,
            ))
    finally:
        abugida_ops_free(ops)
    return out


# --- the pipeline ---------------------------------------------------------

cdef inline object _pipeline(str word, abugida_status (*fn)(
        abugida_string *, const char *, size_t), bint normalise=True):
    """Run one of the core's text pipelines.

    The word is normalised here even though `iast.normalize` is Python: it is
    a dictionary lookup plus NFC, it happens ONCE per call rather than per
    cell, and the alternative is a binding that silently behaves differently
    from the pure-Python reference on NFD input, on the ṁ spelling and on
    uppercase — all inputs `docs/comparator.md` promises to accept. The
    metric's own path (`distance`, `levenshtein`, `alignment`) is untouched:
    it receives already-normalised input from `abugida.distance`.
    """
    cdef abugida_string s
    cdef bytes raw
    if normalise:
        word = _canonical(word)
    raw = _utf8(word)
    cdef abugida_status st
    abugida_string_init(&s)
    st = fn(&s, PyBytes_AS_STRING(raw), PyBytes_GET_SIZE(raw))
    if st != ABUGIDA_OK:
        abugida_string_free(&s)
        raise _error(st, raw, 0)
    out = (<bytes>s.text[:s.n]).decode("utf-8") if s.text != NULL else ""
    abugida_string_free(&s)
    return out


def assimilate_word(word):
    """Resolve every niggahīta in the word against what follows it."""
    return _pipeline(word, abugida_assimilate_word)


def contract_word(word):
    """Contract `aya` → `e`, `ava` → `o`, `ayi` → `e` throughout a word."""
    return _pipeline(word, abugida_contract_word)


def phonological_form(word):
    """Sandhi resolved, then vowel contraction: the word as the metric should
    see it.

    `normalise=False`, alone among the pipeline functions, and deliberately:
    the reference `lexicon.phonological_form` lets the ValueError from
    `assimilate_word` escape its `try` WITHOUT normalising, so a string the
    inventory cannot tokenise comes back byte for byte. Passing raw input here
    is what makes the two the same function; normalising first would return
    "zh" where the reference returns "ZH". A word that DOES tokenise is
    normalised by the core's own strict tokeniser, in both.
    """
    return _pipeline(word, abugida_phonological_form, normalise=False)


# --- the derived constants ------------------------------------------------

#: The balance weight ρ* of the embedding, read from the generated table.
NEUTRAL_MODIFIER_WEIGHT = abugida_neutral_modifier_weight()

#: The extremal epenthetic indel weight, and the costliest elementary move.
INDEL_WEIGHT = abugida_indel_weight()
ONE_MOVE = abugida_one_move()

#: The ABI of the generated tables this extension was compiled against.
TABLES_ABI_VERSION = ABUGIDA_TABLES_ABI_VERSION
NTOKENS = ABUGIDA_NTOKENS
NPLAIN = ABUGIDA_NPLAIN
NO_TOKEN = ABUGIDA_NO_TOKEN


#: The token vocabulary as Python strings, in id order, so the adapter
#: helpers below are dict lookups rather than scans.
_VOCAB = tuple(
    (<bytes>abugida_token_text_len(<short>i, &_length))[:0].decode("utf-8")
    if False else None
    for i in range(0)
)


def _build_vocab():
    cdef list out = []
    cdef short i
    cdef size_t length
    cdef const char *p
    for i in range(ABUGIDA_NTOKENS):
        p = abugida_token_text_len(i, &length)
        out.append((<bytes>p[:length]).decode("utf-8"))
    return tuple(out)


_VOCAB = _build_vocab()
_VOCAB_OF = {g: i for i, g in enumerate(_VOCAB)}


#: An unknown character's token: `ABUGIDA_NO_TOKEN` minus a slot, which is the
#: encoding `opaque_token` in `csrc/abugida.c` produces. The two high bits of
#: the slot are the character's UTF-8 length, so characters of different
#: lengths can never collide — a Latin letter is never confused with a
#: Cyrillic one, nor either with a CJK ideograph. One- and two-byte characters
#: (U+0000 to U+07FF: Latin, Latin-1, Greek, Cyrillic, the combining marks)
#: are EXACT; three- and four-byte characters fold within their own band. The
#: two implementations must stay in step: the core tokenises and this decodes.
_OPAQUE_CAT_BYTES = 8192
_OPAQUE_MAX_CODEPOINT = 0x10FFFF


def ids_of(graphemes):
    """Graphemes to token ids: the inverse of `text_of`, and the adapter
    `distance._edit` uses so callers can keep passing token strings.

    A grapheme outside the vocabulary becomes the opaque encoding of its
    CODEPOINT — not of its first byte — which is what the tokeniser itself
    produces for an unknown character in lenient mode. Byte encoding would
    spend two tokens on a two-byte letter and four on an emoji where the
    reference spends one, and the two implementations would answer differently
    on any input with a typo outside ASCII.
    """
    return [_VOCAB_OF[g] if g in _VOCAB_OF else _opaque_id(g)
            for g in graphemes]


cdef short _opaque_id(object g):
    cdef bytes b = _utf8(g)
    cdef unsigned long cp

    if not b:
        raise ValueError("an empty grapheme is not a token")
    cp = ord(g[0])
    if cp <= 0x7F:
        return <short>(ABUGIDA_NO_TOKEN - <short>cp)
    if cp <= 0x7FF:
        return <short>(ABUGIDA_NO_TOKEN - 0x80 - <short>(cp - 0x80))
    if cp <= 0xFFFF:
        return <short>(ABUGIDA_NO_TOKEN - 0x800
                       - <short>((cp - 0x800) % _OPAQUE_CAT_BYTES))
    if cp > _OPAQUE_MAX_CODEPOINT:
        raise ValueError("not a Unicode scalar value")
    return <short>(ABUGIDA_NO_TOKEN - 0x4000
                   - <short>((cp - 0x10000) % _OPAQUE_CAT_BYTES))





def text_of(token):
    """A token id back to its grapheme. Ids outside the vocabulary are
    opaque and decode to the character they encode."""
    cdef short t = <short>token
    cdef size_t length
    cdef const char *p
    if 0 <= t < ABUGIDA_NTOKENS:
        p = abugida_token_text_len(t, &length)
        return (<bytes>p[:length]).decode("utf-8")
    if t <= ABUGIDA_NO_TOKEN:
        # An opaque token: ABUGIDA_NO_TOKEN minus its slot, inverted the same
        # way `_opaque_id` produced it. Exact for one- and two-byte
        # characters; for three and four the slot names a BAND member, so what
        # comes back is the band's first element rather than the character.
        slot = ABUGIDA_NO_TOKEN - t
        if slot < 0x80:
            return chr(slot)
        if slot < 0x800:
            return chr(0x80 + (slot - 0x80))
        if slot < 0x4000:
            return chr(0x800 + (slot - 0x800))
        return chr(0x10000 + (slot - 0x4000))
    return None


def token_ids(text):
    """The token ids of a tokenised string, as a list — the vocabulary check
    the parity tests compare against `iast.tokenize`."""
    return Tokens.from_text(text).ids()


def token_texts(ids):
    """The reverse: token ids back to graphemes."""
    return Tokens.from_ids(ids).texts()
