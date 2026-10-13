"""Reading a threshold as a probability: the noisy-channel calibration.

WHAT PROBLEM THIS SOLVES. `ONE_MOVE` is derived structurally — the costliest
elementary move — and that says what it *is* without saying what it *buys*.
An integrator choosing θ has had no way to know whether 0.627 admits mostly
variants or mostly noise. This module answers that in the currency they care
about: expected precision.

THE MODEL, AND WHY IT IS THE RIGHT ONE. `distance` is a noisy channel: a word
is corrupted by independent operations, the cost of one is −log P(operation),
and a path's cost is the corruption's negative log-likelihood (SPEC §9.2).
That reading implies confusability decays exponentially in the distance,

    P(true variant | d)  =  exp(−(c + λd))

and it was verified rather than assumed: over the operating range the fit is
excellent and beats the log-distance alternative at every cut through d=2.5
(`eval/noisy_channel.py`). Inverting it gives the threshold for a target
precision.

NO CONSTANTS ARE SHIPPED. λ and c are properties of a CORPUS, not of Pāli
phonology, so baking in the values measured on DPD would put a fitted number
inside a package whose whole discipline is that its constants are derived.
You supply observations from your own lexicon; this module supplies the
model. For reference, DPD's full lexicon (75k lemmas, `normalise=True`,
`var_phonetic` as the reference) gives λ = 4.68, c = −0.84 at R² = 0.982.
"Precision" there is the share of candidates DPD's `var_phonetic` also lists
— agreement with DPD, whose field its own rules compute, not a ground truth
(README, "Agreement with DPD is not accuracy"):

    θ = 0.327 → 50% precision      θ = 0.470 → 26% (one algebra move)
    θ = 0.476 → 25% precision      θ = 0.601 → 14% (a karaṇa bridge)
    θ = 0.672 → 10% precision      θ = 0.627 → 12% (`ONE_MOVE`)
    θ = 0.820 →  5% precision      θ = 1.000 →  2%

Two of those line up without having been made to. One move in the algebra
(0.470) sits within half a percent of the 25%-precision threshold (0.476),
and `ONE_MOVE` (0.627) is close to the 10% one (0.672). The structural
anchors and the decision-theoretic ones were derived from unrelated
arguments; nothing was tuned to make them agree, which is what makes the
agreement worth something.

ALWAYS CHECK `r_squared` BEFORE TRUSTING A FIT. If the channel model does not
describe your corpus, the inverted threshold is meaningless, and this module
will tell you rather than guess.
"""

from __future__ import annotations

import math
from typing import Dict, Hashable, Iterable, List, NamedTuple, Tuple

#: Bin width in distance units for estimating P(d). Narrow enough to see the
#: curve, wide enough that each bin holds a usable count.
BIN = 0.25

#: Bins with fewer observations than this are dropped: a proportion from a
#: handful of samples is noise, and one noisy bin in a 5-point regression
#: does real damage.
MIN_COUNT = 30

#: Observations beyond this distance are excluded from the fit, and the bound
#: is part of the model rather than a convenience.
#:
#: The exponential channel describes the OPERATING RANGE. Past it, P falls to
#: ~1e-4 — a handful of true pairs among tens of thousands of candidates —
#: and the estimate is noise that a least-squares line will happily chase.
#: Fitting the full tail on DPD gives λ=2.20 with R²=0.78 and, inverted, a
#: NEGATIVE threshold for 50% precision: a fit so bad it leaves the domain.
#: Restricted to the operating range the same data gives R²>0.96 and
#: thresholds that mean something. No usable θ reaches the tail anyway —
#: θ=1.5 already costs 10.6 candidates per lemma — so nothing is lost by
#: declining to model it. See `eval/noisy_channel.py` for the sweep.
OPERATING_RANGE = 1.5

#: Bins whose observed P reaches this are dropped: the model is saturated
#: against the probability ceiling there and stops being log-linear.
#:
#: `exp(−(c + λd))` exceeds 1 whenever `c + λd < 0`, which the fit cannot
#: express, so a bin sitting at P≈0.99 contributes −log P ≈ 0.01 where the
#: line wants a negative value. One such bin at d=0 is enough to bend the
#: whole regression: on a synthetic channel with λ=4.0 it pulled the estimate
#: to 3.71 and the offset from −0.40 to −0.20. Dropping it recovers both.
MAX_RATE = 0.9


class Channel(NamedTuple):
    """A fitted channel: P(true variant | d) = exp(−(c + λd))."""

    decay: float  # λ — how fast confusability falls with distance
    offset: float  # c — the intercept in log space
    r_squared: float
    bins: int
    #: How this channel was arrived at. "fitted" is a real regression;
    #: "rate" is a flat estimate for a stratum with plenty of observations
    #: and almost no positives, where there is no curve to fit but the base
    #: rate is itself the answer; "pooled" means the stratum was too thin to
    #: say anything and borrowed the overall fit.
    basis: str = "fitted"

    def precision_at(self, theta: float) -> float:
        """Expected fraction of candidates at distance `theta` that are true
        variants. Clamped to [0, 1]; the model is not constrained to it."""
        return min(1.0, max(0.0, math.exp(-(self.offset + self.decay * theta))))

    def theta_for(self, precision: float) -> float:
        """The threshold whose candidates are `precision` likely to be true
        variants. The inverse of `precision_at`.

        Note this is precision AT the threshold, not averaged below it — the
        candidates a sweep returns are dominated by the outermost band, so
        this is the conservative reading.
        """
        if not 0.0 < precision < 1.0:
            raise ValueError("precision must be strictly between 0 and 1")
        return (-math.log(precision) - self.offset) / self.decay


def fit_channel(observations: Iterable[Tuple[float, bool]],
        bin_width: float = BIN,
        min_count: int = MIN_COUNT,
        max_distance: float = OPERATING_RANGE,
        max_rate: float = MAX_RATE) -> Channel:
    """Fit the channel to (distance, is_true_variant) observations.

    Feed it real search candidates — everything a `Lexicon.search` returns for
    a sample of queries, labelled against whatever ground truth you have.
    Feeding it only true pairs estimates nothing: P needs both classes.

    Bins with no positives are dropped rather than clamped; log 0 is not a
    number and inventing a floor for it would fabricate the tail, which is
    exactly where this model is weakest.

    Observations beyond `max_distance` are excluded — see `OPERATING_RANGE`.
    Including the tail is not a harmless extra: on DPD it drags R² to 0.78
    and yields a negative threshold for 50% precision. Saturated bins are
    dropped at the other end for the mirror reason — see `MAX_RATE`.
    """
    counts = {}
    for d, is_variant in observations:
        if d > max_distance:
            continue  # see OPERATING_RANGE: the tail is noise, not signal
        key = round(d / bin_width) * bin_width
        hit, total = counts.get(key, (0, 0))
        counts[key] = (hit + bool(is_variant), total + 1)

    points: List[Tuple[float, float]] = [
        (key, -math.log(hit / total))
        for key, (hit, total) in sorted(counts.items())
        if total >= min_count and 0 < hit / total < max_rate
    ]
    if len(points) < 3:
        raise ValueError(
            f"only {len(points)} usable bins: need at least 3. Supply more "
            "observations, or widen bin_width."
        )

    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    intercept = my - slope * mx
    resid = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    total_ss = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - resid / total_ss if total_ss else 1.0
    return Channel(decay=slope, offset=intercept, r_squared=r2,
                   bins=len(points))


# --- more signal than distance --------------------------------------------


class Strata:
    """One channel per stratum, for signals the distance does not contain.

    WHY THIS EXISTS. Integrators have evidence the metric cannot see. In
    dpd-db, whether two lemmas share a word family splits the d ≤ 0.35 band
    into 87.9% against 3.4% — inside a single distance band, so it is not
    the distance restated. Ordering by distance alone throws that away.

    WHY STRATA AND NOT A REGRESSION. Fitting a logistic model over
    [distance, signal₁, signal₂] would also work and would be the obvious
    move. It is declined for two reasons: it introduces a second model with
    its own assumptions into a package whose whole discipline is that one
    principle explains the cost (SPEC §9.2), and it produces coefficients nobody
    can check by eye. Stratifying keeps the noisy-channel reading intact —
    each stratum is the same exponential decay, fitted separately — and each
    fit remains inspectable, with its own λ, c and R².

    The cost is that strata multiply: two binary signals give four, and each
    needs enough observations to fit. What happens to the ones that cannot be
    fitted is where the care goes, and the distinction that matters is NOT
    fittable/unfittable — it is "too little data" against "plenty of data and
    almost no positives":

    - **Thin** (below `min_for_rate` observations): nothing is known, so the
      pooled channel answers. Abstention.
    - **Plenty of data, few positives**: a stratum with 16,758 observations
      and 3 positives is not silence, it is a loud negative. Handing that to
      the pooled fit was the first version's bug — it answered 25.2% where
      the stratum's own rate is 0.018%, overestimating ~1,400-fold, and the
      pooled fit is dominated by the OTHER stratum's positives, so the answer
      was circular too. Such strata now get a flat channel at their own
      observed rate (`basis="rate"`), with the rule of three as the ceiling
      when there are no positives at all.

    Abstain when you do not know; not when you know there is nothing there.

        obs = [(d, is_variant, (shares_family, same_pos)) for …]
        s = fit_strata(obs)
        s.precision_at(0.4, (True, True))    # → the informed estimate
        s.precision_at(0.4, (False, False))
        s.report()                           # per-stratum fits, n and R²
    """

    def __init__(self, channels: Dict[Hashable, Channel], pooled: Channel,
                 counts: Dict[Hashable, int]):
        #: Fitted channel per stratum. Strata with too little data are absent.
        self.channels = channels
        #: The all-observations fit, used wherever a stratum could not be.
        self.pooled = pooled
        self.counts = counts

    def channel_for(self, stratum: Hashable) -> Channel:
        return self.channels.get(stratum, self.pooled)

    def precision_at(self, theta: float, stratum: Hashable) -> float:
        return self.channel_for(stratum).precision_at(theta)

    def theta_for(self, precision: float, stratum: Hashable) -> float:
        return self.channel_for(stratum).theta_for(precision)

    def report(self) -> str:
        lines = [f"{'stratum':<28} {'n':>7} {'λ':>8} {'R²':>7} {'bins':>5}"]
        for key in sorted(self.counts, key=lambda k: -self.counts[k]):
            ch = self.channels.get(key)
            if ch is None:
                fitted = f"{'(pooled)':>22}"
            elif ch.basis == "rate":
                fitted = f"{'(rate ' + f'{100 * ch.precision_at(0):.3f}%)':>22}"
            else:
                fitted = (f"{ch.decay:>8.3f} {ch.r_squared:>7.3f} "
                          f"{ch.bins:>5}")
            lines.append(f"{str(key):<28} {self.counts[key]:>7} {fitted}")
        lines.append(f"{'POOLED':<28} {sum(self.counts.values()):>7} "
                     f"{self.pooled.decay:>8.3f} {self.pooled.r_squared:>7.3f} "
                     f"{self.pooled.bins:>5}")
        return "\n".join(lines)


#: Above this many observations, a stratum that will not fit is treated as
#: informative rather than silent — see `fit_strata`.
MIN_FOR_RATE = 500


def flat_channel(hits: int, total: int) -> Channel:
    """A channel with no decay, sitting at the observed rate.

    For a stratum with plenty of observations and almost no positives there
    is no curve to fit, but the base rate IS the answer. With zero positives
    the rate is not 0 — that would claim certainty from absence — so the rule
    of three gives the 95% ceiling, 3/n.
    """
    rate = hits / total if hits else 3.0 / total
    return Channel(decay=0.0, offset=-math.log(rate), r_squared=0.0,
                   bins=0, basis="rate")


def fit_strata(observations: Iterable[Tuple[float, bool, Hashable]],
               min_for_rate: int = MIN_FOR_RATE,
               **kwargs) -> Strata:
    """Fit one channel per stratum from (distance, is_variant, stratum).

    `kwargs` go to `fit_channel`. Strata that will not fit are handled by
    size, not lumped together — see the `Strata` docstring for why that
    distinction is the whole point:

    - fewer than `min_for_rate` observations → the pooled channel (abstain)
    - at least that many → a flat channel at the stratum's own rate, since
      "16,758 observations, 3 positives" is information, not silence
    """
    grouped: Dict[Hashable, List[Tuple[float, bool]]] = {}
    every: List[Tuple[float, bool]] = []
    for distance_, is_variant, stratum in observations:
        grouped.setdefault(stratum, []).append((distance_, is_variant))
        every.append((distance_, is_variant))
    if not every:
        raise ValueError("no observations")
    pooled = fit_channel(every, **kwargs)
    channels = {}
    for key, rows in grouped.items():
        try:
            channels[key] = fit_channel(rows, **kwargs)
        except ValueError:
            if len(rows) >= min_for_rate:
                channels[key] = flat_channel(sum(1 for _, v in rows if v),
                                             len(rows))
    return Strata(channels, pooled, {k: len(v) for k, v in grouped.items()})
