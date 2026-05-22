"""
NNUE inference for the Python engine — no PyTorch required at runtime.

Loads omblecavalier.nnue once at import time and exposes eval_cp(board).
Falls back gracefully (returns None) if no .nnue file is found.

Feature encoding mirrors features.py: 768-bit, side-to-move perspective.
Features are built directly from a bulletchess Board — no FEN round-trip.
"""
import logging
import os
import struct

import numpy as np
from bulletchess import BLACK, PIECE_TYPES, SQUARES, WHITE

_MAGIC   = b"NNUE"
_VERSION = 1

# Square integer mapping — bulletchess SQUARES enumerate a1=0 … h8=63
_SQ_TO_INT = {sq: i for i, sq in enumerate(SQUARES)}

# Rank-mirror: sq → sq on the opposite rank (same as sq ^ 56)
_MIRROR = [(7 - sq // 8) * 8 + sq % 8 for sq in range(64)]


def _search_nnue() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "omblecavalier.nnue"),
        os.path.join(here, "..", "..", "..", "nnue-training", "omblecavalier.nnue"),
        "omblecavalier.nnue",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


class _Net:
    """Pure-numpy forward pass for the 768→256→32→1 NNUE network."""

    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            if f.read(4) != _MAGIC:
                raise ValueError("Bad magic")
            if struct.unpack("<B", f.read(1))[0] != _VERSION:
                raise ValueError("Unsupported version")
            n = struct.unpack("<B", f.read(1))[0]
            sizes = [struct.unpack("<II", f.read(8)) for _ in range(n)]
            self._W: list[np.ndarray] = []
            self._b: list[np.ndarray] = []
            for in_sz, out_sz in sizes:
                self._W.append(
                    np.frombuffer(f.read(out_sz * in_sz * 4), dtype="<f4")
                    .reshape(out_sz, in_sz).copy()
                )
                self._b.append(np.frombuffer(f.read(out_sz * 4), dtype="<f4").copy())

    def forward(self, feat: np.ndarray) -> int:
        x = feat
        for w, b in zip(self._W[:-1], self._b[:-1]):
            x = np.clip(w @ x + b, 0.0, 1.0)
        logit = float((self._W[-1] @ x + self._b[-1])[0])
        wp = 1.0 / (1.0 + np.exp(-logit))
        wp = max(1e-7, min(1.0 - 1e-7, wp))
        return int(400.0 * np.log(wp / (1.0 - wp)))


def _board_to_features(board) -> np.ndarray:
    """Build a (768,) float32 feature vector from a bulletchess Board."""
    feat   = np.zeros(768, dtype=np.float32)
    us     = board.turn
    them   = BLACK if us == WHITE else WHITE
    mirror = us == BLACK
    for i, pt in enumerate(PIECE_TYPES):
        for sq in board[us, pt]:
            s = _SQ_TO_INT[sq]
            feat[i * 64 + (_MIRROR[s] if mirror else s)] = 1.0
        for sq in board[them, pt]:
            s = _SQ_TO_INT[sq]
            feat[384 + i * 64 + (_MIRROR[s] if mirror else s)] = 1.0
    return feat


# ── Module-level singleton loaded once at import time ─────────────────────────

_net: _Net | None = None
_nnue_path = _search_nnue()

if _nnue_path:
    try:
        _net = _Net(_nnue_path)
        logging.info(f"NNUE loaded: {_nnue_path}")
    except Exception as exc:
        logging.warning(f"NNUE load failed ({_nnue_path}): {exc}")
else:
    logging.info("NNUE: no omblecavalier.nnue found — using HCE")


def is_loaded() -> bool:
    return _net is not None


def eval_cp(board) -> int | None:
    """
    Return centipawn score from side-to-move's perspective, or None if no
    .nnue file is loaded (caller should fall back to HCE).
    """
    if _net is None:
        return None
    return _net.forward(_board_to_features(board))
