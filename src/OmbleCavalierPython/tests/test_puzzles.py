import json
import os

import bulletchess as chess
import pytest

from omblecavalier.engines.omble_cavalier import find_best_move_iterative

_PUZZLES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "puzzles.json")


def _load_puzzles():
    with open(_PUZZLES_FILE) as f:
        puzzles = json.load(f)
    return [(p["fen"], p["description"], p["best_move"], p["depth"]) for p in puzzles]


@pytest.mark.parametrize("fen, description, expected_best_move, depth", _load_puzzles())
def test_puzzles(fen, description, expected_best_move, depth):
    board = chess.Board.from_fen(fen)

    best_move = find_best_move_iterative(
        board,
        max_depth=depth,
        total_time_remaining=1000,
    )

    assert best_move is not None, f"{description}: engine returned None"

    assert best_move.uci() == expected_best_move, (
        f"{description}: expected {expected_best_move}, got {best_move.uci()}"
    )


if __name__ == "__main__":
    pytest.main(["-v", __file__])
