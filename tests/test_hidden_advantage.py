import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hidden_advantage as ha


def test_no_boost_is_pure_chance():
    cfg = ha.Config(delta=0.0, trials=40_000, rounds=5)
    scores = ha.simulate(cfg)["scores"]
    assert ha.win_rate(scores) == pytest.approx(0.25, abs=0.01)
    assert ha.accuracy(ha.detect_mean(scores)) == pytest.approx(0.25, abs=0.01)


@pytest.mark.parametrize("delta", [0.2, 0.5, 1.0])
def test_simulation_matches_closed_form(delta):
    cfg = ha.Config(delta=delta, trials=40_000, rounds=8)
    scores = ha.simulate(cfg)["scores"]
    assert ha.win_rate(scores) == pytest.approx(ha.theory_win_rate(delta), abs=0.01)
    assert ha.accuracy(ha.detect_mean(scores)) == pytest.approx(
        ha.theory_detection(delta, 8), abs=0.012)


def test_round_scores_have_unit_variance():
    scores = ha.simulate(ha.Config(delta=0.7, trials=40_000, rounds=4))["scores"]
    assert scores[..., 2].std() == pytest.approx(1.0, abs=0.01)
    assert scores[..., ha.INTRUDER].mean() == pytest.approx(0.7, abs=0.01)


def test_adaptive_intruder_skips_the_boost_when_leading():
    out = ha.simulate(ha.Config(delta=1.0, policy="adaptive", trials=40_000, rounds=4))
    # Without a boost in the first half, the intruder leads a quarter of the time.
    assert out["used"].mean() == pytest.approx(0.75, abs=0.01)


def test_same_seed_same_result():
    a = ha.simulate(ha.Config(seed=3))["scores"]
    b = ha.simulate(ha.Config(seed=3))["scores"]
    assert np.array_equal(a, b)


def test_likelihood_detector_equals_mean_detector_on_constant_boost():
    cfg = ha.Config(delta=0.6, trials=20_000, rounds=10)
    scores = ha.simulate(cfg)["scores"]
    lik = ha.accuracy(ha.LikelihoodDetector(cfg)(scores))
    assert lik == pytest.approx(ha.accuracy(ha.detect_mean(scores)), abs=0.01)


def test_rounds_needed_scales_as_inverse_square():
    assert ha.rounds_needed(0.25) / ha.rounds_needed(0.5) == pytest.approx(4.0, rel=0.15)
