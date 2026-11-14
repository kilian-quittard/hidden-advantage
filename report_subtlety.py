"""Figure and numbers of the subtlety curve (README, "How precise must the tip be...").

    python report_subtlety.py    # reads results/subtlety.jsonl, results/referee_v2.jsonl

Writes figures/6_subtlety.png and results_subtlety.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import llm_quiz as q
import referee as r

ROOT = Path(__file__).parent
BLUE, ORANGE, GREEN, GREY, PURPLE = "#2f6fb5", "#d9772b", "#3f9a5a", "#777777", "#7b5ea7"
LEVELS = ("S60", "S30", "S15", "S05")


def main() -> None:
    verdicts = {v["key"]: v for v in q.load(r.RESULTS / "referee_v2.jsonl")}
    res = r.analyze2(r.subtlety_games(), verdicts)
    (ROOT / "results_subtlety.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="")
    sds = [q.SUBTLETY[c] for c in LEVELS]
    xs = list(range(len(LEVELS)))
    labels = [f"{round(sd * 100)} %" for sd in sds]
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1.5]})

    best_w = [(1 / sd ** 2) / (1 / sd ** 2 + 1 / q.LOOK_SD ** 2) for sd in sds]
    a0.plot(xs, best_w, color=GREY, ls="--", lw=1, marker="o", ms=3)
    a0.text(xs[0] + 0.05, best_w[0] - 0.07, "best possible use", color=GREY, fontsize=8)
    used = [res[c]["tip_weight"] for c in LEVELS]
    a0.plot(xs, used, color=BLUE, marker="o", lw=2)
    for x, v in zip(xs, used):
        a0.text(x, v + 0.04, f"{v:.2f}", ha="center", color=BLUE, fontsize=9)
    a0.set_ylabel("weight of the tip in the answers")
    a0.set_title("The helped player uses the tip more as it gets sharper", fontsize=10, loc="left")

    series = (
        ("referee reading scores", ORANGE, lambda w: w["scores"]["named"], "-"),
        ("lead-of-the-winner rule, same false alarms", GREY, lambda w: w["margin_rule"]["named"], "--"),
        ("referee reading working notes", GREEN, lambda w: w["notes"]["named"], "-"),
        ("asked outside the game", PURPLE, lambda w: w["asked_outside_the_game"]["named"], "-"),
    )
    for k, (name, color, get, ls) in enumerate(series):
        rates = [get(res[c]) for c in LEVELS]
        vals = [x["rate"] for x in rates]
        lo = [v - x["ci95"][0] for v, x in zip(vals, rates)]
        hi = [x["ci95"][1] - v for v, x in zip(vals, rates)]
        off = [x + (k - 1.5) * 0.04 for x in xs]
        a1.errorbar(off, vals, yerr=[lo, hi], color=color, marker="o", lw=2, ls=ls, capsize=3, label=name)
    fa_s = res["S60"]["scores"]["false_alarm_on_control"]
    fa_n = res["S60"]["notes"]["false_alarm_on_control"]
    a1.text(0.0, -0.36,
            f"False alarms on 30 games with no helped player: scores {fa_s['k']}/{fa_s['n']}, "
            f"notes {fa_n['k']}/{fa_n['n']}, asked 0/90 innocent players",
            transform=a1.transAxes, fontsize=8, color="#333333")
    a1.set_ylabel("games where the helped player is named")
    a1.set_title("Detection by channel (30 games per level, 95 % intervals)", fontsize=10, loc="left")
    a1.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0.0, -0.16), ncol=2)
    for ax in (a0, a1):
        ax.set_xticks(xs, labels)
        ax.set_xlabel("typical error of the tip (the player's own look: 25 %)")
        ax.set_ylim(-0.03, 1.08)
        ax.grid(axis="y", alpha=0.25)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "6_subtlety.png", dpi=150, bbox_inches="tight")
    print("figures/6_subtlety.png")


if __name__ == "__main__":
    main()
