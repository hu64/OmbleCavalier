"""
Prepare training data from the Lichess eval database.

Input : lichess_db_eval.jsonl.zst  (download from database.lichess.org)
Output: positions.bin              (fixed-size binary records)

Binary format
─────────────
Header  (12 bytes):
  4 bytes  magic       b'OCDT'
  4 bytes  version     uint32 LE = 1
  4 bytes  record_size uint32 LE = 772

Per record (772 bytes):
  768 bytes  features  uint8  (0 or 1, side-to-move perspective)
    4 bytes  target    float32 LE  win-probability in [0, 1]

Target derivation
─────────────────
  cp_stm = best_cp * (+1 if white-to-move else -1)
  target = sigmoid(cp_stm / 400)

Usage
─────
  python prepare_data.py \\
      --input  /path/to/lichess_db_eval.jsonl.zst \\
      --output data/positions.bin \\
      --max-positions 5_000_000 \\
      --min-depth 12
"""
import argparse
import io
import json
import os
import struct
from pathlib import Path

import chess
import numpy as np
import zstandard as zstd
from tqdm import tqdm

from features import fen_to_features

MAGIC        = b"OCDT"
VERSION      = 1
RECORD_SIZE  = 772   # 768 uint8 features + 4 float32 target
HEADER_SIZE  = 12
CP_CLAMP     = 3000  # saturate at ±30 pawns to keep sigmoid targets sane
CP_SCALE     = 400.0


def _sigmoid(x: float) -> float:
    import math
    return 1.0 / (1.0 + math.exp(-x))


def _best_cp(entry: dict, min_depth: int) -> float | None:
    """Extract best centipawn eval from a Lichess eval DB entry.

    Returns None if quality is below min_depth or no valid eval exists.
    """
    evals = entry.get("evals")
    if not evals:
        return None

    # Lichess sorts evals ascending by depth; take the deepest.
    best = None
    for ev in evals:
        if ev.get("depth", 0) < min_depth:
            continue
        pvs = ev.get("pvs")
        if not pvs:
            continue
        pv = pvs[0]
        if "cp" in pv:
            best = float(pv["cp"])
        elif "mate" in pv:
            m = pv["mate"]
            best = CP_CLAMP if m > 0 else -CP_CLAMP
        # keep iterating to use the highest-depth eval

    return best


def prepare(
    input_path: str,
    output_path: str,
    max_positions: int,
    min_depth: int,
) -> None:
    os.makedirs(Path(output_path).parent, exist_ok=True)

    written = 0
    skipped = 0

    dctx = zstd.ZstdDecompressor()

    with open(output_path, "wb") as out:
        # Write header (record count unknown upfront; derive from file size)
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<I", RECORD_SIZE))

        with open(input_path, "rb") as f:
            with dctx.stream_reader(f) as reader:
                text_stream = io.TextIOWrapper(io.BufferedReader(reader), encoding="utf-8")

                with tqdm(total=max_positions, unit="pos", desc="Preparing") as bar:
                    for raw_line in text_stream:
                        if written >= max_positions:
                            break

                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue

                        try:
                            entry = json.loads(raw_line)
                        except json.JSONDecodeError:
                            skipped += 1
                            continue

                        cp = _best_cp(entry, min_depth)
                        if cp is None:
                            skipped += 1
                            continue

                        fen = entry.get("fen", "")
                        if not fen:
                            skipped += 1
                            continue

                        try:
                            board = chess.Board(fen)
                        except ValueError:
                            skipped += 1
                            continue

                        # Convert to side-to-move perspective
                        stm_factor = 1.0 if board.turn == chess.WHITE else -1.0
                        cp_stm = max(-CP_CLAMP, min(CP_CLAMP, cp * stm_factor))
                        target = _sigmoid(cp_stm / CP_SCALE)

                        features = fen_to_features(fen)

                        out.write(features.tobytes())                       # 768 bytes
                        out.write(struct.pack("<f", target))                # 4 bytes

                        written += 1
                        bar.update(1)

    print(f"Done — {written:,} positions written, {skipped:,} skipped")
    print(f"Output: {output_path}  ({os.path.getsize(output_path) / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare NNUE training data from Lichess eval DB")
    parser.add_argument("--input",  required=True,           help="Path to lichess_db_eval.jsonl.zst")
    parser.add_argument("--output", default="data/positions.bin", help="Output binary file (default: data/positions.bin)")
    parser.add_argument("--max-positions", type=int, default=5_000_000, help="Max positions to extract (default: 5M)")
    parser.add_argument("--min-depth",     type=int, default=12,        help="Minimum eval depth to accept (default: 12)")
    args = parser.parse_args()

    prepare(
        input_path=args.input,
        output_path=args.output,
        max_positions=args.max_positions,
        min_depth=args.min_depth,
    )


if __name__ == "__main__":
    main()
