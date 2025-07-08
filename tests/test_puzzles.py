import pytest
from omblecavalier.engines.omble_cavalier import evaluate_board, find_best_move  # adjust import path
import chess

@pytest.mark.parametrize("fen, description, expected_best_move", [
    ("kbK5/pp6/1P6/8/8/8/R7/8 w - - 0 2", "mate in 2 (a2a6)", "a2a6"),
    ("rnbqkbnr/ppp2ppp/3p4/4p3/4P1Q1/8/PPPP1PPP/RNB1KBNR b KQkq - 1 3", "black wins a queen (c8g4)", "c8g4"),
    ("rnbqkbnr/1pp2ppp/p2p4/4p1B1/4P3/3P4/PPP2PPP/RN1QKBNR w KQkq - 0 4", "white wins a queen (g5d8)", "g5d8"),
])
def test_puzzles(fen, description, expected_best_move):
    board = chess.Board()
    board.set_fen(fen)
    
    print(f"Testing: {description}")
    print(board)
    eval_score = evaluate_board(board)
    print(f"Evaluation: {eval_score}\n")
    
    best_move = find_best_move(board, depth=3, total_time_remaining=10)
    print(f"Best Move: {best_move}\n")
    
    # Check if the best move matches expected (you can refine the check to allow UCI or Move object)
    assert str(best_move) == expected_best_move, f"Expected {expected_best_move}, got {best_move}"