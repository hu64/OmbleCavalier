import bulletchess as chess
import pytest

from omblecavalier.engines.omble_cavalier import find_best_move_iterative


@pytest.mark.parametrize(
    "fen, description, expected_best_move, depth",
    [
        ("kbK5/pp6/1P6/8/8/8/R7/8 w - - 0 2", "mate in 2 (a2a6)", "a2a6", 4),
        (
            "rnbqkbnr/ppp2ppp/3p4/4p3/4P1Q1/8/PPPP1PPP/RNB1KBNR b KQkq - 1 3",
            "black wins a queen (c8g4)",
            "c8g4",
            6,
        ),
        (
            "rnbqkbnr/1pp2ppp/p2p4/4p1B1/4P3/3P4/PPP2PPP/RN1QKBNR w KQkq - 0 4",
            "white wins a queen (g5d8)",
            "g5d8",
            6,
        ),
        (
            "r1b1kb1r/pppp1ppp/5q2/4n3/3KP3/2N3PN/PPP4P/R1BQ1B1R b kq - 0 1",
            "",
            "f8c5",
            6,
        ),
        (
            "1r5k/5ppp/3Q4/8/8/Prq3P1/2P1K2P/3R1R2 b - - 5 27",
            "",
            "c3e3",
            6,
        ),
        (
            "8/1Q6/2PBK3/k7/8/2P2P2/8/7q w - - 7 63",
            "mate in 2",
            "d6c7",
            4,
        ),
        (
            "r3k2r/ppp2Npp/1b5n/4p2b/2B1P2q/BQP2P2/P5PP/RN5K w kq - 1 0",
            "mate in 3",
            "c4b5",
            6,
        ),
        (
            "r2n1rk1/1ppb2pp/1p1p4/3Ppq1n/2B3P1/2P4P/PP1N1P1K/R2Q1RN1 b - - 0 1",
            "mate in 3",
            "f5f2",
            6,
        ),
        (
            "8/8/8/3k4/1Q1Np2p/1p2P2P/1Pp2b2/2K5 w - - 1 50",
            "mate in 6",
            "b4a5",
            12,
        ),
    ],
)
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