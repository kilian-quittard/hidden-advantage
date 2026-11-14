"""Regenerate every figure and number of the README.

    python run_experiments.py

Writes figures/*.png and results.json. Seeded: two runs give the same files.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import hidden_advantage as ha

OUT = Path(__file__).parent / "figures"
TRIALS = 20_000
T_VOTE = 10  # rounds observed before the accusation in the trade-off figures

BLUE, ORANGE, GREEN, GREY = "#2f6fb5", "#d9772b", "#3f9a5a", "#777777"


def _style(ax, xlabel: str, ylabel: str) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def detection_vs_subtlety() -> dict:
    """Figure 1: detection accuracy against the size of a constant boost."""
    deltas = np.linspace(0.0, 1.5, 16)
    fine = np.linspace(0.0, 1.5, 121)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    table = {}
    for rounds, color in ((1, GREY), (5, BLUE), (20, ORANGE), (80, GREEN)):
        sim = [ha.accuracy(ha.detect_mean(ha.simulate(
            ha.Config(delta=float(d), rounds=rounds, trials=TRIALS))["scores"])) for d in deltas]
        ax.plot(fine, [ha.theory_detection(d, rounds) for d in fine], color=color, lw=1.6)
        ax.plot(deltas, sim, "o", color=color, ms=4, label=f"{rounds} round{'s' if rounds > 1 else ''}")
        table[str(rounds)] = dict(zip([round(float(d), 2) for d in deltas], [round(s, 4) for s in sim]))
    ax.axhline(0.25, color="black", lw=0.8, ls=":")
    ax.text(0.02, 0.215, "chance", ha="left", fontsize=8)
    ax.set_ylim(0.2, 1.02)
    _style(ax, "hidden boost (standard deviations of a round score)", "intruder correctly named")
    ax.legend(title="observed", frameon=False, loc="lower right")
    ax.set_title("A subtle advantage is detectable; it just takes rounds\n(dots: simulation, lines: closed form)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "1_detection_vs_subtlety.png", dpi=160)
    plt.close(fig)
    return table


def rounds_to_detect() -> dict:
    """Figure 2: rounds needed for 80 % detection: the 1/delta^2 law."""
    deltas = np.array([0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5])
    need = np.array([ha.rounds_needed(float(d)) for d in deltas])
    k = float(np.exp(np.mean(np.log(need[:6] * deltas[:6] ** 2))))
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.loglog(deltas, k / deltas ** 2, color=GREY, lw=1.2, ls="--", label=f"{k:.1f} / boost²")
    ax.loglog(deltas, need, "o-", color=BLUE, label="rounds for 80 % detection")
    _style(ax, "hidden boost (standard deviations)", "rounds needed")
    ax.legend(frameon=False)
    ax.set_title("Halving the advantage costs the detector four times the data", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "2_rounds_needed.png", dpi=160)
    plt.close(fig)
    return {"constant_k": round(k, 2),
            "rounds": {str(float(d)): int(n) for d, n in zip(deltas, need)}}


def _frontier(policy: str, deltas, decoy_ratio: float = 0.0, aware: bool = False):
    wins, found, decoyed = [], [], []
    for d in deltas:
        cfg = ha.Config(delta=float(d), policy=policy, rounds=T_VOTE,
                        decoy_ratio=decoy_ratio, trials=TRIALS)
        scores = ha.simulate(cfg)["scores"]
        accused = ha.LikelihoodDetector(cfg)(scores) if aware else ha.detect_mean(scores)
        wins.append(ha.win_rate(scores))
        found.append(ha.accuracy(accused))
        decoyed.append(ha.accuracy(accused, ha.DECOY))
    return np.array(wins), np.array(found), np.array(decoyed)


def gain_vs_detection() -> dict:
    """Figure 3: what the intruder gains against how often it is caught."""
    d_const = np.linspace(0.0, 1.6, 17)
    d_adapt = np.linspace(0.0, 3.2, 17)
    curves = {
        "constant boost": (_frontier("constant", d_const), BLUE, "-"),
        "adaptive boost, naive detector": (_frontier("adaptive", d_adapt), ORANGE, "-"),
        "adaptive boost, policy-aware detector": (_frontier("adaptive", d_adapt, aware=True), ORANGE, "--"),
        "constant boost + half-strength decoy": (_frontier("constant", d_const, decoy_ratio=0.5), GREEN, "-"),
    }
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    out = {}
    for label, ((wins, found, decoyed), color, ls) in curves.items():
        ax.plot(wins, found, ls, color=color, lw=1.8, marker="o", ms=3, label=label)
        out[label] = {"win_rate": [round(float(w), 4) for w in wins],
                      "detection": [round(float(f), 4) for f in found],
                      "decoy_accused": [round(float(x), 4) for x in decoyed]}
    ax.axhline(0.25, color="black", lw=0.8, ls=":")
    ax.axvline(0.25, color="black", lw=0.8, ls=":")
    _style(ax, "rounds won by the intruder (chance = 25 %)",
           f"intruder correctly named after {T_VOTE} rounds")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Lower is better for the intruder: same wins, less often caught", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "3_gain_vs_detection.png", dpi=160)
    plt.close(fig)

    # Detection at a fixed gain (40 % of rounds won), by interpolation.
    target = 0.40
    out["detection_at_40pct_wins"] = {
        label: round(float(np.interp(target, np.array(v["win_rate"]), np.array(v["detection"]))), 3)
        for label, v in out.items()}
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    results = {
        "settings": {"players": ha.N_PLAYERS, "trials": TRIALS, "seed": ha.Config().seed,
                     "rounds_before_vote": T_VOTE},
        "detection_vs_subtlety": detection_vs_subtlety(),
        "rounds_to_detect": rounds_to_detect(),
        "gain_vs_detection": gain_vs_detection(),
    }
    (Path(__file__).parent / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results["rounds_to_detect"], indent=1))
    print(json.dumps(results["gain_vs_detection"]["detection_at_40pct_wins"], indent=1))


if __name__ == "__main__":
    main()
