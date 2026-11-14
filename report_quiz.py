"""Figures and numbers of the Bean Jar experiment (README, part 2 and 3).

    python report_quiz.py            # reads results/main.jsonl, results/detective.jsonl

Writes figures/4_bean_jar.png, figures/5_detective.png and results_llm.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import detective
import llm_quiz

ROOT = Path(__file__).parent
FIG = ROOT / "figures"
BLUE, ORANGE, GREEN, GREY = "#2f6fb5", "#d9772b", "#3f9a5a", "#777777"
NAMES = {"A": "A\ncontrol", "B": "B\ntold to cheat", "C": "C\nadvantaged"}


def _bars(ax, labels, series, title, chance=None, ylabel="share of games"):
    width = 0.8 / len(series)
    for k, (name, color, rates) in enumerate(series):
        xs = [i + (k - (len(series) - 1) / 2) * width for i in range(len(labels))]
        vals = [r["rate"] or 0.0 for r in rates]
        lo = [max(0.0, v - r["ci95"][0]) for v, r in zip(vals, rates)]
        hi = [max(0.0, r["ci95"][1] - v) for v, r in zip(vals, rates)]
        ax.bar(xs, vals, width * 0.92, color=color, label=name, yerr=[lo, hi],
               error_kw={"ecolor": "#333333", "capsize": 3, "lw": 1})
        for x, v in zip(xs, vals):
            ax.text(x, 1.02, f"{v:.0%}", ha="center", va="bottom", fontsize=8, color=color)
    if chance is not None:
        ax.axhline(chance, color=GREY, ls="--", lw=1)
        ax.text(-0.48, chance + 0.015, "chance", ha="left", color=GREY, fontsize=8)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(axis="y", alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=len(series))


def bean_jar(path: Path) -> dict:
    res = llm_quiz.analyze(llm_quiz.load(path))
    conds = [c for c in "ABC" if c in res]
    labels = [NAMES[c] for c in conds]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))
    axes[0].bar(range(len(conds)), [res[c]["tip_weight"] or 0.0 for c in conds], 0.5, color=[GREY, ORANGE, BLUE])
    axes[0].axhline(0.77, color=GREY, ls="--", lw=1)
    axes[0].text(len(conds) - 0.5, 0.785, "a player using the tip fully", ha="right", color=GREY, fontsize=8)
    for i, c in enumerate(conds):
        axes[0].text(i, (res[c]["tip_weight"] or 0.0) + 0.02, f"{res[c]['tip_weight']:.2f}", ha="center", fontsize=9)
    axes[0].set_xticks(range(len(conds)), labels)
    axes[0].set_ylim(0, 1.0)
    axes[0].set_ylabel("weight given to the tip (0 ignores it, 1 copies it)")
    axes[0].set_title("How much the special seat uses its tip", fontsize=10, loc="left")
    axes[0].grid(axis="y", alpha=0.25)
    for side in ("top", "right"):
        axes[0].spines[side].set_visible(False)
    _bars(axes[1], labels, [("special seat says YES", ORANGE, [res[c]["special_says_yes"] for c in conds]),
                            ("an innocent says YES", GREY, [res[c]["others_say_yes"] for c in conds])],
          "Asked afterwards: did you get outside information?", ylabel="share")
    _bars(axes[2], labels, [("by scores (best total)", BLUE, [res[c]["special_has_best_total"] for c in conds]),
                            ("by statements (only one YES)", ORANGE, [res[c]["named_by_statements_alone"] for c in conds]),
                            ("both", GREEN, [res[c]["named_by_statements_then_scores"] for c in conds])],
          "Special seat correctly named", chance=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "4_bean_jar.png", dpi=150)
    plt.close(fig)
    return res


def detective_figure() -> dict | None:
    test = RESULTS / "party_test.jsonl"
    cal_path = RESULTS / "party_calibration.jsonl"
    out = RESULTS / "detective.jsonl"
    if not (test.exists() and cal_path.exists() and out.exists()):
        return None
    cal = detective.calibrate([r for r in detective.load(cal_path) if not r["team"]])
    verdicts = {f"{v['game']}:{v['round']}": v for v in detective.load(out)}
    rounds = [r for r in detective.select(detective.load(test), 10 ** 9) if f"{r['game']}:{r['round']}" in verdicts]
    res = detective.analyze(rounds, cal, verdicts)
    games = sorted(res["per_game"], key=lambda g: res["per_game"][g]["calibrated"])
    fig, ax = plt.subplots(figsize=(9.5, 0.36 * len(games) + 1.8))
    ys = range(len(games))
    for key, color, marker, label in (("top", GREY, "o", "highest score"), ("calibrated", BLUE, "s", "calibrated z-score"),
                                      ("model", ORANGE, "D", "language model")):
        ax.scatter([res["per_game"][g].get(key) for g in games], ys, color=color, marker=marker, s=34, label=label, zorder=3)
    for y, g in zip(ys, games):
        vals = [res["per_game"][g].get(k) for k in ("top", "calibrated", "model")]
        ax.plot([min(vals), max(vals)], [y, y], color="#cccccc", lw=1, zorder=1)
    ax.axvline(0.25, color=GREY, ls="--", lw=1)
    ax.set_yticks(ys, games)
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of rounds where the intruder is named (chance 25 %)")
    total = f"all rounds: highest score {res['top']['rate']:.0%}, calibrated {res['calibrated']['rate']:.0%}, model {res['model']['rate']:.0%}"
    ax.set_title("Naming the intruder from the scores of one round\n" + total, fontsize=10, loc="left")
    ax.grid(axis="x", alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "5_detective.png", dpi=150)
    plt.close(fig)
    return res


RESULTS = ROOT / "results"

if __name__ == "__main__":
    out = {"bean_jar": bean_jar(RESULTS / "main.jsonl"), "detective": detective_figure()}
    (ROOT / "results_llm.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    b = out["bean_jar"]
    for c in b:
        print(c, b[c]["games"], "games | score", b[c]["mean_score_special"], "vs", b[c]["mean_score_others"],
              "| tip", b[c]["tip_weight"], "| best total", b[c]["special_has_best_total"]["rate"],
              "| yes", b[c]["special_says_yes"]["rate"], "| innocents yes", b[c]["others_say_yes"]["rate"],
              "| by statements", b[c]["named_by_statements_alone"]["rate"],
              "| both", b[c]["named_by_statements_then_scores"]["rate"], "| unreadable", b[c]["unreadable_answers"])
    if out["detective"]:
        d = out["detective"]
        print("detective", {k: d[k] for k in d if k != "per_game"})
