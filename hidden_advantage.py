"""Hidden advantage vs. statistical detection: a minimal, headless simulation.

Four players play repeated rounds. Each round a player's score is the sum of two
halves of independent Gaussian noise (total variance 1, so every effect below is
in units of one standard deviation of a round score). One player, the
*intruder*, secretly receives a boost. A detector sees only the final scores of
T rounds and must name the intruder.

Intruder policies
-----------------
constant   boost `delta` every round.
adaptive   boost `delta` only in rounds where the intruder is NOT leading at
           half-time (it "sandbags" when it would win anyway).

Optional decoy: one innocent receives `decoy_ratio * delta` every round.

Everything is vectorised over Monte Carlo trials and fully seeded.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import integrate, stats

N_PLAYERS = 4
INTRUDER = 0  # by symmetry the intruder is always seat 0; detectors never use this
DECOY = 1


@dataclass(frozen=True)
class Config:
    delta: float = 0.5          # size of the boost, in round-score sigmas
    policy: str = "constant"    # "constant" or "adaptive"
    rounds: int = 10            # T, rounds observed before the accusation
    decoy_ratio: float = 0.0    # 0 = no decoy
    trials: int = 20_000
    seed: int = 1950


def simulate(cfg: Config) -> dict[str, np.ndarray]:
    """Return final scores (trials, rounds, players) and whether the boost was used."""
    if cfg.policy not in ("constant", "adaptive"):
        raise ValueError(f"unknown policy {cfg.policy!r}")
    rng = np.random.default_rng(cfg.seed)
    shape = (cfg.trials, cfg.rounds, N_PLAYERS)
    half1 = rng.normal(0.0, np.sqrt(0.5), shape)
    half2 = rng.normal(0.0, np.sqrt(0.5), shape)
    if cfg.decoy_ratio:
        # The decoy's boost is spread evenly over the round.
        half1[..., DECOY] += 0.5 * cfg.decoy_ratio * cfg.delta
        half2[..., DECOY] += 0.5 * cfg.decoy_ratio * cfg.delta
    if cfg.policy == "constant":
        used = np.ones(shape[:2], dtype=bool)
        half1[..., INTRUDER] += 0.5 * cfg.delta
        half2[..., INTRUDER] += 0.5 * cfg.delta
    else:
        # Decide at half-time, with the information a player would have.
        used = half1.argmax(axis=-1) != INTRUDER
        half2[..., INTRUDER] += np.where(used, cfg.delta, 0.0)
    return {"scores": half1 + half2, "used": used}


def win_rate(scores: np.ndarray) -> float:
    """Share of rounds won by the intruder (chance = 1 / N_PLAYERS)."""
    return float((scores.argmax(axis=-1) == INTRUDER).mean())


# --------------------------------------------------------------------------
# Detectors: each returns the accused seat for every trial.
# --------------------------------------------------------------------------

def detect_mean(scores: np.ndarray) -> np.ndarray:
    """Accuse the highest average score.

    For a constant boost this is the Bayes-optimal detector whatever `delta`
    is: the posterior of "player i is the intruder" is proportional to
    exp(delta * sum_t score_it).
    """
    return scores.sum(axis=1).argmax(axis=-1)


class LikelihoodDetector:
    """Likelihood-ratio detector that knows the intruder's policy.

    It learns the marginal density of an intruder's round score from a
    calibration simulation (histogram), then accuses the player whose T scores
    are best explained by that density rather than by the innocent N(0, 1).
    It treats players as independent, which is exact for the constant policy
    and an approximation for the adaptive one.
    """

    def __init__(self, cfg: Config, calibration_trials: int = 400_000, bins: int = 240):
        cal = Config(cfg.delta, cfg.policy, 1, 0.0, calibration_trials, cfg.seed + 7919)
        x = simulate(cal)["scores"][:, 0, INTRUDER]
        edges = np.linspace(-6.0, 6.0 + max(cfg.delta, 0.0), bins + 1)
        density, _ = np.histogram(x, bins=edges, density=True)
        self._centers = 0.5 * (edges[:-1] + edges[1:])
        self._log_ratio = np.log(np.maximum(density, 1e-12)) - stats.norm.logpdf(self._centers)

    def __call__(self, scores: np.ndarray) -> np.ndarray:
        llr = np.interp(scores, self._centers, self._log_ratio)
        return llr.sum(axis=1).argmax(axis=-1)


def accuracy(accused: np.ndarray, target: int = INTRUDER) -> float:
    return float((accused == target).mean())


# --------------------------------------------------------------------------
# Closed forms for the constant policy (used to validate the simulation).
# --------------------------------------------------------------------------

def _prob_shifted_max(shift: float, others: int = N_PLAYERS - 1) -> float:
    """P(Z + shift > max of `others` independent standard normals)."""
    def f(z: float) -> float:
        return stats.norm.pdf(z) * stats.norm.cdf(z + shift) ** others
    return float(integrate.quad(f, -10.0, 10.0)[0])


def theory_win_rate(delta: float) -> float:
    return _prob_shifted_max(delta)


def theory_detection(delta: float, rounds: int) -> float:
    """Accuracy of `detect_mean` after `rounds` rounds of a constant boost."""
    return _prob_shifted_max(delta * np.sqrt(rounds))


def rounds_needed(delta: float, target: float = 0.8, max_rounds: int = 100_000) -> int:
    """Smallest T at which `detect_mean` reaches `target` accuracy (theory)."""
    lo, hi = 1, 1
    while theory_detection(delta, hi) < target:
        hi *= 2
        if hi > max_rounds:
            return max_rounds
    while lo < hi:
        mid = (lo + hi) // 2
        if theory_detection(delta, mid) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo
