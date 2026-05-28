"""
NNUE inference for the Python engine — no PyTorch required at runtime.

Loads omblecavalier.nnue (v2) once at import time and exposes eval_cp(board).
Falls back gracefully (returns None) if no .nnue file is found.

Architecture: 768 → 512 (SCReLU) → N_BUCKETS (8) output heads.
Bucket selected by piece count: clamp((32 - pieces) * 8 / 32, 0, 7).
Feature encoding mirrors features.py: 768-bit, side-to-move perspective.
Features are built directly from a bulletchess Board — no FEN round-trip.

Inference backend priority:
  1. onnxruntime + CUDAExecutionProvider   (NVIDIA GPU, Linux/Windows)
  2. onnxruntime + CoreML EP              (Apple Silicon ~15× vs numpy)
  3. onnxruntime + CPU EP                 (~5× vs numpy)
  4. Pure numpy with sparse gather        (fallback, no extra deps)

Sparse gather: builds a list of ~25 active feature indices instead of a
dense (768,) vector, then sums the corresponding rows of w1_T.  Replaces
a 512×768 dense matmul (~393 k ops) with ~25 row additions (~13 k ops).

No incremental accumulator: full forward pass per eval call.
"""
import logging
import os
import struct
import sys
from typing import Union

import numpy as np
from bulletchess import BLACK, PIECE_TYPES, SQUARES, WHITE

_MAGIC   = b"NNUE"
_VERSION = 2

# Square integer mapping — bulletchess SQUARES enumerate a1=0 … h8=63
_SQ_TO_INT = {sq: i for i, sq in enumerate(SQUARES)}

# Rank-mirror: sq → sq on the opposite rank (same as sq ^ 56)
_MIRROR = [(7 - sq // 8) * 8 + sq % 8 for sq in range(64)]


def _search_nnue() -> tuple[Union[str, None], Union[str, None]]:
    """Return (nnue_path, onnx_path) for the first matching pair found."""
    here = os.path.dirname(os.path.abspath(__file__))
    roots = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)
    roots += [
        here,
        os.path.join(here, "..", "..", "..", "nnue-training"),
        ".",
    ]
    for root in roots:
        nnue = os.path.join(root, "omblecavalier.nnue")
        onnx = os.path.join(root, "omblecavalier.onnx")
        if os.path.isfile(nnue):
            onnx_found = os.path.abspath(onnx) if os.path.isfile(onnx) else None
            return os.path.abspath(nnue), onnx_found
    return None, None


class _OrtNet:
    """onnxruntime inference session: CUDA → CoreML → CPU EP fallback."""

    def __init__(self, onnx_path: str) -> None:
        import onnxruntime as ort

        providers: list[str] = []
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        if "CoreMLExecutionProvider" in available:
            providers.append("CoreMLExecutionProvider")
        providers.append("CPUExecutionProvider")

        self._session = ort.InferenceSession(onnx_path, providers=providers)
        active = self._session.get_providers()[0]
        logging.info(f"ONNX loaded ({active}): {onnx_path}")

    def forward(self, indices: list[int], n_pieces: int) -> int:
        feat = np.zeros(768, dtype=np.float32)
        feat[indices] = 1.0
        logit = float(self._session.run(None, {"features": feat.reshape(1, -1)})[0][0, 0])
        wp = 1.0 / (1.0 + np.exp(-logit))
        wp = max(1e-7, min(1.0 - 1e-7, wp))
        return int(400.0 * np.log(wp / (1.0 - wp)))


class _Net:
    """Pure-numpy forward pass with sparse gather for the L1 layer.

    Instead of the 512×768 dense matmul, we sum only the ~25 active rows of
    the transposed weight matrix w1_T[768, 512].  This is ~30× fewer ops.
    """

    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            if f.read(4) != _MAGIC:
                raise ValueError("Bad magic — not a .nnue file")
            version = struct.unpack("<B", f.read(1))[0]
            if version != _VERSION:
                raise ValueError(f"Unsupported .nnue version {version} (expected {_VERSION})")
            self._n_buckets = struct.unpack("<B", f.read(1))[0]
            n0 = struct.unpack("<I", f.read(4))[0]
            n1 = struct.unpack("<I", f.read(4))[0]

            # Load w1 [n1, n0], immediately transpose to [n0, n1] for row-sparse access.
            # C-contiguous layout ensures each feature row is a contiguous n1-float block.
            raw_w1 = np.frombuffer(f.read(n1 * n0 * 4), dtype="<f4").reshape(n1, n0)
            self._w1_T = np.ascontiguousarray(raw_w1.T)  # shape [768, 512]

            self._b1 = np.frombuffer(f.read(n1 * 4), dtype="<f4").copy()
            self._w_out = (
                np.frombuffer(f.read(self._n_buckets * n1 * 4), dtype="<f4")
                .reshape(self._n_buckets, n1).copy()
            )
            self._b_out = np.frombuffer(f.read(self._n_buckets * 4), dtype="<f4").copy()

    @staticmethod
    def _screlu(x: np.ndarray) -> np.ndarray:
        c = np.clip(x, 0.0, 1.0)
        return c * c

    def forward(self, indices: list[int], n_pieces: int) -> int:
        # Sparse gather: sum active feature rows + bias, then SCReLU
        x1 = self._screlu(self._w1_T[indices].sum(axis=0) + self._b1)

        bucket = min(self._n_buckets - 1, (32 - n_pieces) * self._n_buckets // 32)
        logit = float(self._w_out[bucket] @ x1 + self._b_out[bucket])

        wp = 1.0 / (1.0 + np.exp(-logit))
        wp = max(1e-7, min(1.0 - 1e-7, wp))
        return int(400.0 * np.log(wp / (1.0 - wp)))


def _board_to_feature_indices(board) -> tuple[list[int], int]:
    """Return (active_feature_indices, piece_count) for the current position."""
    indices = []
    us      = board.turn
    them    = BLACK if us == WHITE else WHITE
    mirror  = us == BLACK
    n_pieces = 0
    for i, pt in enumerate(PIECE_TYPES):
        for sq in board[us, pt]:
            s = _SQ_TO_INT[sq]
            indices.append(i * 64 + (_MIRROR[s] if mirror else s))
            n_pieces += 1
        for sq in board[them, pt]:
            s = _SQ_TO_INT[sq]
            indices.append(384 + i * 64 + (_MIRROR[s] if mirror else s))
            n_pieces += 1
    return indices, n_pieces


# ── Module-level singleton loaded once at import time ─────────────────────────

_net: Union[_OrtNet, _Net, None] = None
_nnue_path, _onnx_path = _search_nnue()

if _onnx_path:
    try:
        _net = _OrtNet(_onnx_path)
    except Exception as exc:
        logging.warning(f"onnxruntime load failed ({_onnx_path}): {exc} — falling back to numpy")

if _net is None and _nnue_path:
    try:
        _net = _Net(_nnue_path)
        logging.info(f"NNUE (numpy sparse) loaded: {_nnue_path}")
    except Exception as exc:
        logging.warning(f"NNUE load failed ({_nnue_path}): {exc}")

if _net is None:
    logging.info("NNUE: no omblecavalier.nnue/.onnx found — using HCE")


def is_loaded() -> bool:
    return _net is not None


def eval_cp(board) -> Union[int, None]:
    """
    Return centipawn score from side-to-move's perspective, or None if no
    .nnue file is loaded (caller should fall back to HCE).
    """
    if _net is None:
        return None
    indices, n_pieces = _board_to_feature_indices(board)
    return _net.forward(indices, n_pieces)
