import pytest
import bulletchess as chess
from bulletchess import WHITE, BLACK, Board

from omblecavalier.engines.omble_cavalier import rook_open_file_bonus


def test_rook_open_file():
    # White rook on d4, no pawns on d-file for either side → open file (+20)
    board = Board.from_fen("k7/8/8/8/3R4/8/PP3PPP/K7 w - - 0 1")
    assert rook_open_file_bonus(board, WHITE) == 20


def test_rook_semi_open_file():
    # White rook on d4, black pawn on d7, no white pawn on d → semi-open (+10)
    board = Board.from_fen("k7/3p4/8/8/3R4/8/PP3PPP/K7 w - - 0 1")
    assert rook_open_file_bonus(board, WHITE) == 10


def test_rook_blocked_by_own_pawn():
    # White rook on d4, white pawn on d3 → no bonus
    board = Board.from_fen("k7/8/8/8/3R4/3P4/PP3PPP/K7 w - - 0 1")
    assert rook_open_file_bonus(board, WHITE) == 0


def test_two_rooks_open_files():
    # White rooks on d4 and e4, no pawns on d or e → 2 open files (+40)
    board = Board.from_fen("k7/8/8/8/3RR3/8/PP3PPP/K7 w - - 0 1")
    assert rook_open_file_bonus(board, WHITE) == 40


def test_black_rook_open_file():
    # Black rook on d5, no pawns on d-file → open file (+20)
    board = Board.from_fen("k7/pp3ppp/8/3r4/8/8/8/K7 b - - 0 1")
    assert rook_open_file_bonus(board, BLACK) == 20


def test_black_rook_semi_open_file():
    # Black rook on d5, white pawn on d2, no black pawn on d → semi-open (+10)
    board = Board.from_fen("k7/pp3ppp/8/3r4/8/8/3P4/K7 b - - 0 1")
    assert rook_open_file_bonus(board, BLACK) == 10


def test_no_rooks():
    # No rooks → bonus is 0
    board = Board.from_fen("k7/pppppppp/8/8/8/8/PPPPPPPP/K7 w - - 0 1")
    assert rook_open_file_bonus(board, WHITE) == 0
    assert rook_open_file_bonus(board, BLACK) == 0
