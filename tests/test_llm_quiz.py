import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import llm_quiz as q


def play(n, condition):
    return [asyncio.run(q.play_game(g, condition, None)) for g in range(n)]


def test_world_is_the_same_in_every_condition():
    a, b = q.make_world(7), q.make_world(7)
    assert a == b
    assert q.make_world(8) != a


def test_only_the_special_seat_sees_a_tip_and_never_in_control():
    w = next(w for w in map(q.make_world, range(50)) if w.tips[0])
    other = (w.special + 1) % q.N_PLAYERS
    assert "accomplice" in q.round_prompt(w, "B", w.special, 0)
    assert "passer-by" in q.round_prompt(w, "C", w.special, 0)
    for condition in q.CONDITIONS:
        assert q.round_prompt(w, condition, other, 0) == q.round_prompt(w, "A", other, 0)
    assert "about" not in q.round_prompt(w, "A", w.special, 0).split("beans.")[-1]


def test_only_the_cheater_gets_a_different_system_prompt():
    w = q.make_world(0)
    other = (w.special + 1) % q.N_PLAYERS
    plain = q.ClaudePlayer(None, "A", other, False, 10).system
    for c in q.CONDITIONS:
        assert q.ClaudePlayer(None, c, other, False, 10).system == plain
    advantaged = q.ClaudePlayer(None, "C", w.special, True, 10).system
    assert advantaged == q.ClaudePlayer(None, "A", w.special, False, 10).system
    assert "accomplice" in q.ClaudePlayer(None, "B", w.special, True, 10).system
    assert "accomplice" not in plain + advantaged


def test_parsers():
    assert q.parse_answer("I think 900.\nANSWER: 1,250") == 1250
    assert q.parse_answer("ANSWER: **830**") == 830
    assert q.parse_answer("no idea") is None
    assert q.parse_yes_no("YES, someone told me.") is True
    assert q.parse_yes_no("No.") is False
    assert q.parse_yes_no("I would rather not say") is None
    assert q.referee_seat("...\nVERDICT: P3") == 2
    assert q.referee_seat("VERDICT: NONE") is None


def test_mock_run_shows_the_three_conditions():
    res = q.analyze(play(150, "A") + play(150, "B") + play(150, "C"))
    # Control: the special seat is an ordinary player.
    assert abs(res["A"]["special_has_best_total"]["rate"] - 0.25) < 0.1
    assert res["A"]["tip_weight"] in (None, 0.0) or abs(res["A"]["tip_weight"]) < 0.1
    # With a tip, it scores better and is the best player far more often.
    for c in "BC":
        assert res[c]["mean_score_special"] > res[c]["mean_score_others"] + 0.03
        assert res[c]["special_has_best_total"]["rate"] > 0.5
    # Same worlds, same scripted use of the tip: same scores in B and C.
    assert res["B"]["mean_score_special"] == res["C"]["mean_score_special"]
    assert res["C"]["special_says_yes"]["rate"] == 1.0
    assert res["B"]["special_says_yes"]["rate"] == 0.0


# --- detective.py ---

def test_detective_statistical_detectors():
    import detective as d
    cal_rounds = [{"game": "g", "intruder": 3, "scores": [10.0 + k, 20.0 + k, 10.0 - k, 30.0]} for k in (-1, 0, 1)]
    cal = d.calibrate(cal_rounds)
    assert cal["g"]["mean"][:3] == [10.0, 20.0, 10.0]
    r = {"game": "g", "intruder": 0, "scores": [14.0, 20.0, 10.0, 10.0]}
    assert d.detect_top(r) == 0.0            # seat 1 is first, as usual
    assert d.detect_calibrated(r, cal) == 1.0  # seat 0 is far above its own usual level
    assert d.credit([5, 5, 1, 0], 0) == 0.5


def test_detective_prompt_and_parse():
    import detective as d
    cal = d.calibrate([{"game": "g", "intruder": 3, "scores": [1.0, 2.0, 3.0, 9.0]},
                       {"game": "g", "intruder": 3, "scores": [3.0, 2.0, 1.0, 9.0]}])
    r = {"game": "g", "round": 0, "intruder": 2, "decoy": -1, "team": False,
         "scores": [1.0, 2.0, 5.0, 2.0], "timeline": [[0, 0, 0, 0], [1, 1, 2, 1], [1, 2, 5, 2]]}
    text = d.round_prompt(r, cal)
    assert "P3 5" in text and "intruder" in text and "P3 is" not in text
    assert d.parse_seat("Looks like P1.\nANSWER: P3") == 2
    assert d.parse_seat("no idea") is None
