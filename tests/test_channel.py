"""The noisy-channel calibration: turning a threshold into a precision.

No corpus is needed — the tests generate observations from a known channel
and check that the fit recovers it, which also pins the failure modes that
matter (a bad fit must be visible, and the tail must not be modelled).
"""

import math
import random

import pytest

from abugida.channel import OPERATING_RANGE, Channel, fit_channel as fit


def synthetic(decay, offset, n=200000, seed=20260801, span=2.0):
    """Observations drawn from an exact exponential channel."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        d = rng.uniform(0.0, span)
        p = math.exp(-(offset + decay * d))
        out.append((d, rng.random() < min(1.0, p)))
    return out


def test_fit_recovers_a_known_channel():
    ch = fit(synthetic(decay=4.0, offset=-0.4))
    assert ch.decay == pytest.approx(4.0, abs=0.3)
    assert ch.offset == pytest.approx(-0.4, abs=0.2)
    assert ch.r_squared > 0.95


def test_precision_and_theta_are_inverses():
    ch = Channel(decay=4.283, offset=-0.412, r_squared=0.97, bins=7)
    for p in (0.5, 0.25, 0.1, 0.05):
        assert ch.precision_at(ch.theta_for(p)) == pytest.approx(p)


def test_the_dpd_reference_numbers_hold():
    """The figures quoted in the module docstring, so they cannot drift
    silently away from the code that produces them."""
    ch = Channel(decay=4.675, offset=-0.837, r_squared=0.9822, bins=6)
    assert ch.theta_for(0.50) == pytest.approx(0.327, abs=0.005)
    assert ch.theta_for(0.25) == pytest.approx(0.476, abs=0.005)
    assert ch.theta_for(0.10) == pytest.approx(0.672, abs=0.005)
    assert 100 * ch.precision_at(0.627) == pytest.approx(12.3, abs=0.3)


def test_the_structural_and_decision_anchors_agree():
    """One algebra move lands on the 25%-precision threshold and ONE_MOVE
    near the 10% one, from unrelated derivations. Pinned because it is the
    claim the module makes for itself."""
    from abugida import ONE_MOVE
    from abugida.distance import cost

    ch = Channel(decay=4.675, offset=-0.837, r_squared=0.9822, bins=6)
    assert abs(ch.theta_for(0.25) - cost("k", "kh")) < 0.01
    assert abs(ch.theta_for(0.10) - ONE_MOVE) < 0.05


def test_precision_is_clamped_to_a_probability():
    """Extrapolated below zero the model exceeds 1; a probability may not."""
    ch = Channel(decay=4.0, offset=-0.4, r_squared=0.97, bins=7)
    assert ch.precision_at(-5.0) == 1.0
    assert 0.0 <= ch.precision_at(50.0) <= 1.0


def test_theta_for_rejects_impossible_targets():
    ch = Channel(decay=4.0, offset=-0.4, r_squared=0.97, bins=7)
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            ch.theta_for(bad)


def test_too_few_bins_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="usable bins"):
        fit([(0.3, True), (0.3, False), (0.35, True)])


def test_the_tail_is_excluded_by_default():
    """OPERATING_RANGE is part of the model. Observations past it are noise,
    and fitting them wrecks the estimate — on DPD it drove R² to 0.78 and
    produced a negative threshold for 50% precision."""
    obs = synthetic(decay=4.0, offset=-0.4, span=1.0)
    junk = [(3.0 + i * 0.25, False) for i in range(4) for _ in range(200)]
    junk += [(3.0, True)] * 3
    assert fit(obs + junk).decay == pytest.approx(fit(obs).decay, abs=1e-9)
    assert OPERATING_RANGE == 1.5


def test_a_bad_fit_is_visible():
    """If the channel model does not describe the data, r_squared says so
    rather than the caller finding out from a nonsense threshold."""
    rng = random.Random(1)
    noise = [(rng.uniform(0, 1.4), rng.random() < 0.3) for _ in range(40000)]
    assert fit(noise).r_squared < 0.5


# --- strata: signal the distance does not contain --------------------------


def stratified(seed=20260801, n=60000):
    """Two populations with genuinely different decay, as a shared word
    family does in DPD (87.9% vs 3.4% inside one distance band)."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        near = rng.random() < 0.5
        d = rng.uniform(0.0, 1.4)
        offset, decay = (-0.4, 3.0) if near else (1.6, 5.0)
        p = math.exp(-(offset + decay * d))
        out.append((d, rng.random() < min(1.0, p), near))
    return out


def test_strata_separate_what_pooling_hides():
    from abugida.channel import fit_strata

    s = fit_strata(stratified())
    assert s.precision_at(0.4, True) > 3 * s.precision_at(0.4, False)
    # the pooled estimate sits between them, which is exactly the loss
    assert (s.precision_at(0.4, False) < s.pooled.precision_at(0.4)
            < s.precision_at(0.4, True))


def test_each_stratum_stays_inspectable():
    """The reason for strata over a regression: every fit keeps its own λ and
    R² and can be checked by eye."""
    from abugida.channel import fit_strata

    s = fit_strata(stratified())
    assert set(s.channels) == {True, False}
    assert all(ch.r_squared > 0.9 for ch in s.channels.values())
    assert "POOLED" in s.report()


def test_a_thin_stratum_falls_back_rather_than_failing():
    """Too little data means abstain: use the uninformed estimate, never lose
    coverage — adding a signal cannot cost you candidates."""
    from abugida.channel import fit_strata

    obs = stratified() + [(0.3, True, "rare"), (0.4, False, "rare")]
    s = fit_strata(obs)
    assert "rare" not in s.channels
    assert s.precision_at(0.4, "rare") == s.pooled.precision_at(0.4)
    assert s.precision_at(0.4, "never seen") == s.pooled.precision_at(0.4)


def test_a_large_all_negative_stratum_is_not_treated_as_silence():
    """REGRESSION, and the distinction the first version got wrong.

    16,758 observations with 3 positives is not absence of evidence, it is
    loud evidence of absence. Sending it to the pooled channel answered 25.2%
    where the stratum's own rate is 0.018% — a ~1,400-fold overestimate, and
    circular besides, since the pooled fit is dominated by the OTHER
    stratum's positives. Reported by a dpd-db integration."""
    from abugida.channel import fit_strata

    rng = random.Random(7)
    obs = stratified(n=9000)
    obs += [(rng.uniform(0, 1.4), False, "loud") for _ in range(16755)]
    obs += [(0.31, True, "loud"), (0.33, True, "loud"), (0.29, True, "loud")]
    s = fit_strata(obs)

    ch = s.channel_for("loud")
    assert ch.basis == "rate"
    assert ch.precision_at(0.2) == pytest.approx(3 / 16758, rel=1e-6)
    assert s.precision_at(0.2, "loud") < 0.01 * s.pooled.precision_at(0.2)


def test_zero_positives_uses_the_rule_of_three_not_zero():
    """Claiming certainty from absence is wrong: with 0 of n positive the
    honest answer is the 95% ceiling, 3/n."""
    from abugida.channel import fit_strata

    rng = random.Random(3)
    obs = stratified(n=9000)
    obs += [(rng.uniform(0, 1.4), False, "empty") for _ in range(6000)]
    s = fit_strata(obs)

    ch = s.channel_for("empty")
    assert ch.basis == "rate"
    assert ch.precision_at(0.5) == pytest.approx(3 / 6000, rel=1e-6)
    assert ch.precision_at(0.5) > 0


def test_strata_needs_observations():
    from abugida.channel import fit_strata

    with pytest.raises(ValueError, match="no observations"):
        fit_strata([])
