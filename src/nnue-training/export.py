"""
Export a trained PyTorch checkpoint to two runtime files:

  omblecavalier.nnue   — custom binary for the C++ engine (v2)
  omblecavalier.onnx   — ONNX graph for the Python engine (onnxruntime)

Both are written by a single export.py run.  The ONNX file gives the Python
engine ~5× faster inference vs numpy (CoreML EP on Apple Silicon: ~15×).

.nnue v2 binary layout
───────────────────────
  Offset  Size        Description
  0       4           Magic: b'NNUE'
  4       1           Version: uint8 = 2
  5       1           N_BUCKETS: uint8 = 8
  6       4           N0 (input size): uint32 LE = 768
  10      4           N1 (hidden size): uint32 LE = 512
  14      N1*N0*4     L1 weights float32[N1][N0]  (row-major)
  +N1*4              L1 biases  float32[N1]
  +N_BUCKETS*N1*4    Output weights float32[N_BUCKETS][N1]
  +N_BUCKETS*4       Output biases  float32[N_BUCKETS]

Usage
─────
  python export.py --model checkpoints/best.pt --output omblecavalier.nnue
  # also writes omblecavalier.onnx in the same directory
"""
import argparse
import struct

import numpy as np
import torch

from model import NNUE, L1, N_BUCKETS
from features import NUM_FEATURES

MAGIC   = b"NNUE"
VERSION = 2


def export(model_path: str, output_path: str) -> None:
    model = NNUE()
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()

    w1 = model.l1.weight.detach().numpy().astype("<f4")       # (L1, N0)
    b1 = model.l1.bias.detach().numpy().astype("<f4")         # (L1,)

    # Stack all output-head weights into (N_BUCKETS, L1) and biases into (N_BUCKETS,)
    w_out = np.stack(
        [h.weight.detach().numpy().astype("<f4").squeeze(0) for h in model.output_heads]
    )  # (N_BUCKETS, L1)
    b_out = np.array(
        [h.bias.detach().numpy().astype("<f4").item() for h in model.output_heads],
        dtype="<f4",
    )  # (N_BUCKETS,)

    with open(output_path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<B", VERSION))
        f.write(struct.pack("<B", N_BUCKETS))
        f.write(struct.pack("<I", NUM_FEATURES))   # N0
        f.write(struct.pack("<I", L1))             # N1
        f.write(w1.tobytes())
        f.write(b1.tobytes())
        f.write(w_out.tobytes())
        f.write(b_out.tobytes())

    import os
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Exported {output_path}  ({size_kb:.1f} KB)")


# ─────────────────────────────────────────────────────────────────────────────
# Pure-numpy inference  (no PyTorch required at runtime)
# ─────────────────────────────────────────────────────────────────────────────

class NNUEInference:
    """Load a v2 .nnue file and evaluate positions using only numpy."""

    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            magic      = f.read(4)
            version    = struct.unpack("<B", f.read(1))[0]
            n_buckets  = struct.unpack("<B", f.read(1))[0]
            n0         = struct.unpack("<I", f.read(4))[0]
            n1         = struct.unpack("<I", f.read(4))[0]

            if magic != MAGIC:
                raise ValueError(f"Not a .nnue file: bad magic {magic!r}")
            if version != VERSION:
                raise ValueError(f"Unsupported .nnue version {version} (expected {VERSION})")

            self._n1        = n1
            self._n_buckets = n_buckets

            self._w1 = np.frombuffer(f.read(n1 * n0 * 4), dtype="<f4").reshape(n1, n0).copy()
            self._b1 = np.frombuffer(f.read(n1 * 4),      dtype="<f4").copy()
            self._w_out = np.frombuffer(f.read(n_buckets * n1 * 4), dtype="<f4").reshape(n_buckets, n1).copy()
            self._b_out = np.frombuffer(f.read(n_buckets * 4),      dtype="<f4").copy()

    @staticmethod
    def _screlu(x: np.ndarray) -> np.ndarray:
        c = np.clip(x, 0.0, 1.0)
        return c * c

    def forward(self, features: np.ndarray) -> float:
        """Raw logit for a (768,) float32 feature vector."""
        x = features.astype(np.float32)
        x1 = self._screlu(self._w1 @ x + self._b1)   # (N1,)

        # Bucket by piece count
        n_pieces = int(features.sum())
        bucket   = min(self._n_buckets - 1, (32 - n_pieces) * self._n_buckets // 32)

        return float(self._w_out[bucket] @ x1 + self._b_out[bucket])

    def win_prob(self, features: np.ndarray) -> float:
        logit = self.forward(features)
        return float(1.0 / (1.0 + np.exp(-logit)))

    def eval_fen(self, fen: str) -> float:
        from features import fen_to_features
        return self.win_prob(fen_to_features(fen).astype(np.float32))

    def eval_cp(self, fen: str) -> int:
        wp = np.clip(self.eval_fen(fen), 1e-7, 1.0 - 1e-7)
        return int(400.0 * float(np.log(wp / (1.0 - wp))))


def export_onnx(model_path: str, output_path: str) -> None:
    """Export the trained model to ONNX (opset 17) for onnxruntime inference."""
    model = NNUE()
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()

    dummy = torch.zeros(1, NUM_FEATURES, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        output_path,
        input_names=["features"],
        output_names=["logit"],
        dynamic_axes={"features": {0: "batch"}, "logit": {0: "batch"}},
        opset_version=17,
    )

    import os
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Exported {output_path}  ({size_kb:.1f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained model to .nnue and .onnx")
    parser.add_argument("--model",  required=True,                help="Path to .pt checkpoint")
    parser.add_argument("--output", default="omblecavalier.nnue", help="Output .nnue file")
    args = parser.parse_args()

    export(args.model, args.output)

    onnx_path = args.output.replace(".nnue", ".onnx")
    if not onnx_path.endswith(".onnx"):
        onnx_path += ".onnx"
    try:
        export_onnx(args.model, onnx_path)
    except Exception as exc:
        print(f"Warning: ONNX export skipped ({exc})")


if __name__ == "__main__":
    main()
