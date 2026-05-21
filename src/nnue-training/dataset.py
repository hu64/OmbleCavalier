"""
Memory-mapped PyTorch Dataset that reads positions.bin produced by prepare_data.py.

Each record is RECORD_SIZE bytes:
  [0:768]   uint8  features (0/1)
  [768:772] float32 LE  target win-probability in [0, 1]

Using np.memmap means the OS pages records in on demand — training on a
file larger than RAM works fine with no explicit chunking.
"""
import os
import struct

import numpy as np
import torch
from torch.utils.data import Dataset

MAGIC       = b"OCDT"
HEADER_SIZE = 12
RECORD_SIZE = 772
FEATURES    = 768


def _read_header(path: str) -> None:
    """Validate the file header; raises ValueError on mismatch."""
    with open(path, "rb") as f:
        magic   = f.read(4)
        version = struct.unpack("<I", f.read(4))[0]
        rec_sz  = struct.unpack("<I", f.read(4))[0]

    if magic != MAGIC:
        raise ValueError(f"Bad magic in {path}: {magic!r}")
    if rec_sz != RECORD_SIZE:
        raise ValueError(f"Unexpected record_size {rec_sz} in {path}; expected {RECORD_SIZE}")


class PositionDataset(Dataset):
    """Random-access dataset backed by a memory-mapped positions.bin file."""

    def __init__(self, path: str) -> None:
        _read_header(path)

        file_size = os.path.getsize(path)
        data_size = file_size - HEADER_SIZE
        if data_size % RECORD_SIZE != 0:
            raise ValueError(
                f"Data section size {data_size} is not a multiple of RECORD_SIZE {RECORD_SIZE}"
            )

        self._n = data_size // RECORD_SIZE
        # Map the data section as a flat byte array; shape (n, 772)
        self._data = np.memmap(
            path,
            dtype=np.uint8,
            mode="r",
            offset=HEADER_SIZE,
            shape=(self._n, RECORD_SIZE),
        )

    def __len__(self) -> int:
        return self._n

    def __getitem__(self, idx: int):
        record = self._data[idx]                                  # (772,) uint8
        features = record[:FEATURES].astype(np.float32)          # (768,) float32
        # Reinterpret bytes 768-771 as little-endian float32
        target = float(np.frombuffer(record[FEATURES:].tobytes(), dtype="<f4")[0])
        return torch.from_numpy(features), torch.tensor(target, dtype=torch.float32)

    @property
    def num_positions(self) -> int:
        return self._n
