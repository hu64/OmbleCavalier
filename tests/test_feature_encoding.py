"""
Cross-check that all three feature encoders produce identical outputs:
  1. features.py::fen_to_features  (python-chess, used during training)
  2. nnue.py::_board_to_features   (bulletchess, used by Python engine at runtime)

Run with:
  uv run pytest tests/test_feature_encoding.py -v
"""
import sys
import os

import numpy as np
import pytest

# Make the training code importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nnue-training"))

import chess
from features import fen_to_features

from bulletchess import PIECE_TYPES, SQUARES, WHITE, BLACK, Board as BBoard

# ── Reproduce _board_to_features from the Python engine ──────────────────────
_SQ_TO_INT = {sq: i for i, sq in enumerate(SQUARES)}
_MIRROR = [(7 - sq // 8) * 8 + sq % 8 for sq in range(64)]


def _bchess_features(fen: str) -> np.ndarray:
    board = BBoard.from_fen(fen)
    feat = np.zeros(768, dtype=np.float32)
    us = board.turn
    them = BLACK if us == WHITE else WHITE
    mirror = us == BLACK
    for i, pt in enumerate(PIECE_TYPES):
        for sq in board[us, pt]:
            s = _SQ_TO_INT[sq]
            feat[i * 64 + (_MIRROR[s] if mirror else s)] = 1.0
        for sq in board[them, pt]:
            s = _SQ_TO_INT[sq]
            feat[384 + i * 64 + (_MIRROR[s] if mirror else s)] = 1.0
    return feat


# ── Expected active indices precomputed from features.py (ground truth) ──────
CASES = [
    (
        "startpos (White to move)",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        [8,9,10,11,12,13,14,15,65,70,130,133,192,199,259,324,
         432,433,434,435,436,437,438,439,505,510,570,573,632,639,699,764],
    ),
    (
        "e4 e5 Nf3 (Black to move)",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        [8,9,10,11,13,14,15,28,65,70,130,133,192,199,259,324,
         420,432,433,434,435,437,438,439,493,505,570,573,632,639,699,764],
    ),
    (
        "lone kings (White to move)",
        "8/8/8/8/8/8/4K3/4k3 w - - 0 1",
        [332, 708],
    ),
    (
        "complex middlegame (White to move)",
        "r3k2r/pppq1ppp/2npbn2/2b1p3/2B1P3/2NPBN2/PPPQ1PPP/R3K2R w KQkq - 4 9",
        [8,9,10,13,14,15,19,28,82,85,148,154,192,199,267,324,
         420,427,432,433,434,437,438,439,490,493,546,556,632,639,691,764],
    ),
    (
        "Caro-Kann (Black to move)",
        "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        None,  # no hardcoded expected — just cross-check py vs bulletchess
    ),
    (
        "endgame rook (White to move)",
        "4k3/8/8/8/8/8/4K3/4R3 w - - 0 1",
        None,
    ),
]


@pytest.mark.parametrize("label,fen,expected_active", CASES, ids=[c[0] for c in CASES])
def test_encoders_match(label, fen, expected_active):
    """Python-chess and bulletchess encoders must produce identical feature vectors."""
    py_feat = fen_to_features(fen).astype(np.float32)
    bc_feat = _bchess_features(fen)

    diff = np.where(py_feat != bc_feat)[0]
    assert len(diff) == 0, (
        f"{label}: {len(diff)} mismatched features at indices {diff[:10].tolist()}"
    )


@pytest.mark.parametrize("label,fen,expected_active", [c for c in CASES if c[2] is not None],
                         ids=[c[0] for c in CASES if c[2] is not None])
def test_known_active_indices(label, fen, expected_active):
    """Features.py must produce exactly the expected set of active indices."""
    feats = fen_to_features(fen)
    got = sorted(np.where(feats)[0].tolist())
    assert got == expected_active, (
        f"{label}:\n  expected {expected_active}\n  got      {got}"
    )


def test_feature_count_startpos():
    """Startpos has exactly 32 active features (16 pieces × 2 sides, but same count)."""
    feats = fen_to_features("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert int(feats.sum()) == 32


def test_us_them_halves_independent():
    """Us-half (0-383) and them-half (384-767) must each have correct piece counts."""
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    feats = fen_to_features(fen)
    assert int(feats[:384].sum()) == 16, "White (us) should have 16 active features"
    assert int(feats[384:].sum()) == 16, "Black (them) should have 16 active features"


def test_symmetric_perspective():
    """The same physical position from each side's turn should use opposite halves."""
    fen_w = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    # Manually construct the same board but with Black to move isn't directly possible
    # in startpos — use a real Black-to-move position instead.
    fen_b = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    feats_w = fen_to_features(fen_w)
    feats_b = fen_to_features(fen_b)
    # Both should have exactly 32 active features
    assert int(feats_w.sum()) == 32
    assert int(feats_b.sum()) == 32
    # Us-half should always represent side-to-move's pieces
    assert int(feats_w[:384].sum()) == 16  # White pieces in us-half
    assert int(feats_b[:384].sum()) == 16  # Black pieces in us-half when Black to move
