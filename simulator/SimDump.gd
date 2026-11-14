extends "res://tools/Simulate.gd"

## Runs the party game's round simulator (four bots, no rendering) and keeps
## every round instead of only the summary: one JSON line per round with the
## final scores, the score timeline (one sample per second of game) and which
## seat was the intruder. This file lives outside the game; nothing in the
## game's repository is changed.
##
##   cd <game folder>
##   DUMP_OUT=<file.jsonl> SIM_ROUNDS=25 SIM_SEED=7 SIM_OUT=<scratch dir> \
##     godot --headless --fixed-fps 60 --path . <this folder>/SimDump.tscn


func _simulate(entry: MinigameEntry) -> void:
	if not entry.supports_intruder(true):
		return
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = hash("%s:%d" % [entry.id, _seed])
	var with_decoy: bool = entry.decoy_available(true)
	var path: String = OS.get_environment("DUMP_OUT")
	var out: FileAccess = FileAccess.open(path, FileAccess.READ_WRITE) if FileAccess.file_exists(path) else FileAccess.open(path, FileAccess.WRITE)
	out.seek_end()
	for i: int in range(_rounds):
		var intruder: int = rng.randi_range(0, 3)
		var decoy: int = -1
		if with_decoy:
			decoy = (intruder + rng.randi_range(1, 3)) % 4
		var r: Dictionary = await _play_round(entry, intruder, decoy, rng.randi())
		out.store_line(JSON.stringify({
			"game": entry.id,
			"round": i,
			"seed": _seed,
			"intruder": intruder,
			"decoy": decoy,
			"team": not (r["teams"] as Dictionary).is_empty(),
			"scores": _row(r["scores"]),
			"timeline": (r["timeline"] as Array).map(_row),
		}))
		out.flush()
	print("[dump] %s : %d rounds" % [entry.id, _rounds])


## Scores of seats 0 to 3, in order.
func _row(scores: Variant) -> Array:
	var d: Dictionary = scores as Dictionary
	var ids: Array = d.keys()
	ids.sort()
	return ids.map(func(id: Variant) -> float: return float(d[id]))
