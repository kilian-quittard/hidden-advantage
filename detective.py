"""Part 2: a language model as the detective on simulated party-game rounds.

Each round is one mini-game played by four bots. One seat, the intruder, gets
the game's hidden advantage. The detective sees the scores and names a seat.

Three detectors are compared on the same rounds:
  top         names the highest final score
  calibrated  names the highest z-score, using each seat's usual score in that
              mini-game (learned on separate calibration rounds)
  model       a language model that reads the score timeline and the same
              calibration figures

  python detective.py --analyze                      # the two statistical detectors
  python detective.py --backend cli --per-game 20    # also ask the model (resumable)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from llm_quiz import Api, CliApi, wilson

RESULTS = Path(__file__).parent / "results"
SEATS = 4

SYSTEM = """You are the referee of a party game played by four players, P1 to P4.
In every round exactly one player, the intruder, secretly gets a small advantage from the game itself. \
The advantage helps but does not guarantee a win, and it is not always used well. \
The other three play normally. You see the scores only.
Name the player you think is the intruder. You must always name exactly one player.
Reply with one short sentence of reasoning, then a last line of the form: ANSWER: P<n>"""


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def calibrate(rounds: list[dict]) -> dict[str, dict]:
    """Per mini-game and per seat: mean and sd of the score when NOT the intruder."""
    honest: dict[str, list[list[float]]] = defaultdict(lambda: [[] for _ in range(SEATS)])
    boosted: dict[str, list[float]] = defaultdict(list)
    for r in rounds:
        for seat, s in enumerate(r["scores"]):
            (boosted[r["game"]] if seat == r["intruder"] else honest[r["game"]][seat]).append(s)
    out = {}
    for game, seats in honest.items():
        pooled = [s for seat in seats for s in seat]
        sd = statistics.pstdev(pooled) or 1.0
        out[game] = {
            "mean": [statistics.fmean(s) if s else statistics.fmean(pooled) for s in seats],
            "sd": [(statistics.pstdev(s) if len(s) > 1 else 0.0) or sd for s in seats],
            "honest_mean": statistics.fmean(pooled),
            "honest_sd": sd,
            "intruder_mean": statistics.fmean(boosted[game]) if boosted[game] else None,
        }
    return out


def credit(values: list[float], target: int) -> float:
    """1 if the target alone is the highest, 1/k on a k-way tie for first, else 0."""
    top = max(values)
    first = [i for i, v in enumerate(values) if v == top]
    return 1.0 / len(first) if target in first else 0.0


def detect_top(r: dict) -> float:
    return credit(r["scores"], r["intruder"])


def detect_calibrated(r: dict, cal: dict) -> float:
    c = cal[r["game"]]
    z = [(s - c["mean"][i]) / c["sd"][i] for i, s in enumerate(r["scores"])]
    return credit([round(v, 9) for v in z], r["intruder"])


def round_prompt(r: dict, cal: dict, samples: int = 8) -> str:
    c = cal[r["game"]]
    tl = r["timeline"]
    step = max(1, (len(tl) - 1) // samples)
    rows = [(i, tl[i]) for i in range(step, len(tl) - 1, step)] + [(len(tl) - 1, tl[-1])]
    fmt = lambda v: f"{v:g}"
    lines = [
        f"Mini-game: {r['game']}. A round lasts about {len(tl) - 1} seconds.",
        "Usual score of each seat when it is NOT the intruder (mean, standard deviation), from past rounds:",
        "  " + ", ".join(f"P{i + 1} {c['mean'][i]:.1f} ± {c['sd'][i]:.1f}" for i in range(SEATS)),
        "",
        "This round, scores over time:",
        "second | P1 | P2 | P3 | P4",
    ]
    lines += [f"{t} | " + " | ".join(fmt(v) for v in row) for t, row in rows]
    lines += ["", "Final scores: " + ", ".join(f"P{i + 1} {fmt(v)}" for i, v in enumerate(r["scores"])),
              "", "Who is the intruder?"]
    return "\n".join(lines)


def parse_seat(text: str) -> int | None:
    m = re.findall(r"ANSWER:\s*P?([1-4])", text or "", re.I)
    return int(m[-1]) - 1 if m else None


def select(test: list[dict], per_game: int) -> list[dict]:
    """Free-for-all rounds only (team games mix two players' scores), first N per mini-game."""
    seen: dict[str, int] = defaultdict(int)
    out = []
    for r in test:
        if r["team"] or seen[r["game"]] >= per_game:
            continue
        seen[r["game"]] += 1
        out.append(r)
    return out


def _rate(values: list[float]) -> dict:
    n = len(values)
    k = sum(values)
    return {"rate": round(k / n, 3) if n else None, "n": n, "ci95": wilson(round(k), n) if n else None}


def analyze(rounds: list[dict], cal: dict, verdicts: dict[str, dict]) -> dict:
    key = lambda r: f"{r['game']}:{r['round']}"
    asked = [r for r in rounds if key(r) in verdicts]
    out = {"rounds": len(rounds), "top": _rate([detect_top(r) for r in rounds]),
           "calibrated": _rate([detect_calibrated(r, cal) for r in rounds])}
    if asked:
        named = [verdicts[key(r)]["seat"] for r in asked]
        out["model"] = _rate([float(s == r["intruder"]) for r, s in zip(asked, named)])
        out["model_unreadable"] = sum(s is None for s in named)
        out["on_the_same_rounds"] = {
            "top": _rate([detect_top(r) for r in asked]),
            "calibrated": _rate([detect_calibrated(r, cal) for r in asked])}
        top_seat = lambda r: max(range(SEATS), key=lambda i: r["scores"][i])
        out["model_names_top_score"] = _rate([float(s == top_seat(r)) for r, s in zip(asked, named)])
        out["model_names_decoy"] = _rate([float(s == r["decoy"]) for r, s in zip(asked, named) if r["decoy"] >= 0])
    per_game = {}
    for game in sorted({r["game"] for r in rounds}):
        rs = [r for r in rounds if r["game"] == game]
        row = {"n": len(rs), "top": _rate([detect_top(r) for r in rs])["rate"],
               "calibrated": _rate([detect_calibrated(r, cal) for r in rs])["rate"]}
        ask = [r for r in rs if key(r) in verdicts]
        if ask:
            row["model"] = _rate([float(verdicts[key(r)]["seat"] == r["intruder"]) for r in ask])["rate"]
        per_game[game] = row
    out["per_game"] = per_game
    return out


async def ask_all(rounds: list[dict], cal: dict, api, out_path: Path, parallel: int) -> None:
    done = {f"{v['game']}:{v['round']}" for v in load(out_path)} if out_path.exists() else set()
    todo = [r for r in rounds if f"{r['game']}:{r['round']}" not in done]
    gate = asyncio.Semaphore(parallel)
    lock = asyncio.Lock()

    async def one(r: dict) -> None:
        async with gate:
            _, reply = await api.call(SYSTEM, [{"role": "user", "content": round_prompt(r, cal)}])
        async with lock:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"game": r["game"], "round": r["round"], "seat": parse_seat(reply),
                                    "reply": reply}, ensure_ascii=False) + "\n")

    await asyncio.gather(*(one(r) for r in todo))
    print(json.dumps(api.usage))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--calibration", default=str(RESULTS / "party_calibration.jsonl"))
    p.add_argument("--test", default=str(RESULTS / "party_test.jsonl"))
    p.add_argument("--out", default=str(RESULTS / "detective.jsonl"))
    p.add_argument("--per-game", type=int, default=20)
    p.add_argument("--backend", choices=["api", "cli"])
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default="medium")
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--analyze", action="store_true")
    args = p.parse_args()
    cal = calibrate([r for r in load(Path(args.calibration)) if not r["team"]])
    rounds = select(load(Path(args.test)), args.per_game)
    out_path = Path(args.out)
    if args.backend:
        api = (CliApi if args.backend == "cli" else Api)(args.model, args.effort, args.concurrency)
        asyncio.run(ask_all(rounds, cal, api, out_path, args.concurrency))
    verdicts = {f"{v['game']}:{v['round']}": v for v in load(out_path)} if out_path.exists() else {}
    print(json.dumps(analyze(rounds, cal, verdicts), indent=1))


if __name__ == "__main__":
    main()
