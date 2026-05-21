"""
768-feature encoding: 6 piece types × 2 sides × 64 squares.

Always from the side-to-move's perspective:
  indices   0–383  = our pieces   (piece_type * 64 + effective_square)
  indices 384–767  = their pieces (piece_type * 64 + effective_square)

For White-to-move: effective_square == square (a1=0 ... h8=63).
For Black-to-move: ranks are mirrored (square_mirror), so both sides always
see their own back rank at the low end of each 64-square block.
"""
import chess
import numpy as np

# Canonical piece-type ordering shared with the model and both engines.
PIECE_ORDER = [
    chess.PAWN,    # 0
    chess.KNIGHT,  # 1
    chess.BISHOP,  # 2
    chess.ROOK,    # 3
    chess.QUEEN,   # 4
    chess.KING,    # 5
]

_PT_IDX = {pt: i for i, pt in enumerate(PIECE_ORDER)}

NUM_FEATURES = 768


def fen_to_features(fen: str) -> np.ndarray:
    """Return a (768,) uint8 array for the given FEN position."""
    board = chess.Board(fen)
    features = np.zeros(NUM_FEATURES, dtype=np.uint8)

    us = board.turn  # side to move (True = WHITE)

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None:
            continue

        pt_idx = _PT_IDX[piece.piece_type]

        # Flip ranks for Black so both sides see their own back rank at index 0.
        eff_sq = sq if us == chess.WHITE else chess.square_mirror(sq)

        if piece.color == us:
            features[pt_idx * 64 + eff_sq] = 1
        else:
            features[384 + pt_idx * 64 + eff_sq] = 1

    return features


def fen_to_features_batch(fens: list[str]) -> np.ndarray:
    """Return a (N, 768) uint8 array for a list of FEN strings."""
    result = np.zeros((len(fens), NUM_FEATURES), dtype=np.uint8)
    for i, fen in enumerate(fens):
        result[i] = fen_to_features(fen)
    return result
