#!/usr/bin/env python3
"""Generate CMake add_test() entries from puzzles.json."""
import json
import sys

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <puzzles.json> <output.cmake>", file=sys.stderr)
    sys.exit(1)

with open(sys.argv[1]) as f:
    puzzles = json.load(f)

with open(sys.argv[2], "w") as out:
    for p in puzzles:
        out.write(
            f'add_test(NAME "{p["name"]}" '
            f'COMMAND omble_cavalier++ --test "{p["fen"]}" "{p["best_move"]}" {p["depth"]})\n'
        )
