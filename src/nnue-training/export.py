"""
Export a trained PyTorch checkpoint to a self-contained .nnue binary file,
and provide a pure-numpy inference class (NNUEInference) that both the
validate script and the Python engine can import without PyTorch.

.nnue binary layout
────────────────────
  Offset  Size   Description
  0       4      Magic: b'NNUE'
  4       1      Version: uint8 = 1
  5       1      Num layers: uint8 (= 3 for this architecture)
  6       8×N    Layer descriptors: (in_size uint32 LE, out_size uint32 LE) × N
  …       …      For each layer in order:
                   weights: float32 LE  shape (out, in), row-major
                   biases : float32 LE  shape (out,)

Usage
─────
  python export.py --model checkpoints/best.pt --output omblecavalier.nnue
"""
import argparse
import struct

import numpy as np
import torch

from model import NNUE

MAGIC   = b"NNUE"
VERSION = 1


def export(model_path: str, output_path: str) -> None:
    model = NNUE()
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()

    layers = [model.l1, model.l2, model.l3]

    with open(output_path, "wb") as f:
        # Header
        f.write(MAGIC)
        f.write(struct.pack("<B", VERSION))
        f.write(struct.pack("<B", len(layers)))

        # Layer descriptors
        for layer in layers:
            in_sz  = layer.weight.shape[1]
            out_sz = layer.weight.shape[0]
            f.write(struct.pack("<II", in_sz, out_sz))

        # Weights and biases
        for layer in layers:
            w = layer.weight.detach().numpy().astype("<f4")   # (out, in)
            b = layer.bias.detach().numpy().astype("<f4")     # (out,)
            f.write(w.tobytes())
            f.write(b.tobytes())

    import os
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Exported {output_path}  ({size_kb:.1f} KB)")


# ──────────────────────────────────────────────────────────────────────────────
# Pure-numpy inference  (no PyTorch required at runtime)
# ──────────────────────────────────────────────────────────────────────────────

class NNUEInference:
    """Load a .nnue file and evaluate positions using only numpy."""

    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            magic   = f.read(4)
            version = struct.unpack("<B", f.read(1))[0]
            n_layers = struct.unpack("<B", f.read(1))[0]

            if magic != MAGIC:
                raise ValueError(f"Not a .nnue file: bad magic {magic!r}")
            if version != VERSION:
                raise ValueError(f"Unsupported .nnue version {version}")

            layer_sizes = []
            for _ in range(n_layers):
                in_sz, out_sz = struct.unpack("<II", f.read(8))
                layer_sizes.append((in_sz, out_sz))

            self._weights: list[np.ndarray] = []
            self._biases:  list[np.ndarray] = []
            for in_sz, out_sz in layer_sizes:
                w = np.frombuffer(f.read(out_sz * in_sz * 4), dtype="<f4").reshape(out_sz, in_sz).copy()
                b = np.frombuffer(f.read(out_sz * 4),         dtype="<f4").copy()
                self._weights.append(w)
                self._biases.append(b)

    def forward(self, features: np.ndarray) -> float:
        """Raw logit output for a (768,) float32 feature vector."""
        x = features.astype(np.float32)
        for w, b in zip(self._weights[:-1], self._biases[:-1]):
            x = np.clip(w @ x + b, 0.0, 1.0)   # ClippedReLU
        x = self._weights[-1] @ x + self._biases[-1]
        return float(x[0])

    def win_prob(self, features: np.ndarray) -> float:
        """Win-probability in [0, 1] from side-to-move perspective."""
        logit = self.forward(features)
        return float(1.0 / (1.0 + np.exp(-logit)))

    def eval_fen(self, fen: str) -> float:
        """Win-probability for a FEN string (0 = loss, 0.5 = draw, 1 = win)."""
        from features import fen_to_features
        return self.win_prob(fen_to_features(fen).astype(np.float32))

    def eval_cp(self, fen: str) -> int:
        """Centipawn estimate from side-to-move perspective (inverse sigmoid × 400)."""
        wp = np.clip(self.eval_fen(fen), 1e-7, 1.0 - 1e-7)
        return int(400.0 * float(np.log(wp / (1.0 - wp))))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained model to .nnue binary")
    parser.add_argument("--model",  required=True,                   help="Path to .pt checkpoint")
    parser.add_argument("--output", default="omblecavalier.nnue",    help="Output .nnue file (default: omblecavalier.nnue)")
    args = parser.parse_args()
    export(args.model, args.output)


if __name__ == "__main__":
    main()
