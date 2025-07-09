import pytest
from omblecavalier.engines.omble_cavalier import evaluate_board, find_best_move_iterative  # adjust import path
import chess

@pytest.mark.parametrize("fen, description, expected_best_move", [
    ("kbK5/pp6/1P6/8/8/8/R7/8 w - - 0 2", "mate in 2 (a2a6)", "a2a6"),
    ("rnbqkbnr/ppp2ppp/3p4/4p3/4P1Q1/8/PPPP1PPP/RNB1KBNR b KQkq - 1 3", "black wins a queen (c8g4)", "c8g4"),
    ("rnbqkbnr/1pp2ppp/p2p4/4p1B1/4P3/3P4/PPP2PPP/RN1QKBNR w KQkq - 0 4", "white wins a queen (g5d8)", "g5d8"),
("r1b1kb1r/pppp1ppp/5q2/4n3/3KP3/2N3PN/PPP4P/R1BQ1B1R b kq - 0 1", "", "f8c5"),
])
def test_puzzles(fen, description, expected_best_move):
    board = chess.Board()
    board.set_fen(fen)
    best_move = find_best_move_iterative(board, max_depth=6, total_time_remaining=100)
    
    # Check if the best move matches expected (you can refine the check to allow UCI or Move object)
    assert str(best_move) == expected_best_move, f"Expected {expected_best_move}, got {best_move}"