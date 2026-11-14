#!/bin/sh
# Simulate party-game rounds and keep every round (see SimDump.gd).
#   GODOT=<godot exe> GAME=<game folder> simulator/dump.sh
# One Godot process per mini-game, so an interrupted run resumes where it stopped.
set -u
HERE="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"
OUT="$HERE/../results"
TMP="${TMPDIR:-/tmp}/party_sim"
mkdir -p "$TMP"
cd "$GAME" || exit 1
IDS=$(grep -l "enabled = true" data/minigames/*.tres | xargs grep -h '^id = ' | sed 's/.*"\(.*\)"/\1/')
run() { # file rounds seed
	for id in $IDS; do
		grep -q "\"game\":\"$id\"" "$OUT/$1" 2>/dev/null && [ "$(grep -c "\"game\":\"$id\"" "$OUT/$1")" -ge "$2" ] && continue
		grep -v "\"game\":\"$id\"" "$OUT/$1" > "$OUT/$1.tmp" 2>/dev/null; mv "$OUT/$1.tmp" "$OUT/$1"
		DUMP_OUT="$OUT/$1" SIM_OUT="$TMP" SIM_ID="$id" SIM_ROUNDS="$2" SIM_SEED="$3" \
			"$GODOT" --headless --fixed-fps 60 --path . "$HERE/SimDump.tscn" 2>&1 | grep "dump\|SCRIPT ERROR"
	done
}
run party_test.jsonl 30 2
run party_calibration.jsonl 60 1
echo "[dump] all done"
