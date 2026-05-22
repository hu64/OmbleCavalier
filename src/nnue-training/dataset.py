"""
Dataset classes for positions.bin produced by prepare_data.py.

Each record is RECORD_SIZE bytes:
  [0:768]   uint8   features (0/1 binary)
  [768:772] float32 LE  target win-probability in [0, 1]

Two classes are provided:

  StreamingPositionDataset (IterableDataset)
      Reads the file sequentially with a fixed-size shuffle buffer.
      Memory usage is O(buffer_size), not O(file_size).
      Use this for the training split.

  PositionDataset (Dataset)
      Memory-mapped random-access view of a byte range in the file.
      Suitable for the small val/test splits (≤ a few hundred MB).
"""
import os
import struct

import numpy as np
import torch
from torch.utils.data import Dataset, IterableDataset

MAGIC       = b"OCDT"
HEADER_SIZE = 12
RECORD_SIZE = 772
FEATURES    = 768
_IO_CHUNK   = 4096  # records per read() call in streaming mode


def record_count(path: str) -> int:
    """Return the number of position records in a positions.bin file."""
    with open(path, "rb") as f:
        magic  = f.read(4)
        _      = f.read(4)   # version
        rec_sz = struct.unpack("<I", f.read(4))[0]
    if magic != MAGIC:
        raise ValueError(f"Bad magic {magic!r} in {path}")
    if rec_sz != RECORD_SIZE:
        raise ValueError(f"Unexpected record_size {rec_sz} in {path}")
    data_bytes = os.path.getsize(path) - HEADER_SIZE
    if data_bytes % RECORD_SIZE != 0:
        raise ValueError(f"File size not aligned to RECORD_SIZE in {path}")
    return data_bytes // RECORD_SIZE


class StreamingPositionDataset(IterableDataset):
    """Sequential streaming reader with a reservoir shuffle buffer.

    Reads the file in order (sequential I/O, OS-cache-friendly) while holding
    a fixed-size buffer of positions from which it samples randomly. This
    gives approximate shuffling at O(buffer_size) memory regardless of how
    large the file is.

    The seed is varied each epoch so successive passes see different orderings.
    Use num_workers=0 in the DataLoader — IterableDataset + multiple workers
    requires splitting the range per worker, which adds complexity for no gain
    when the bottleneck is GPU compute rather than data loading.
    """

    def __init__(
        self,
        path: str,
        start: int,
        end: int,
        buffer_size: int = 200_000,
        seed: int = 42,
    ) -> None:
        self.path        = path
        self.start       = start
        self.end         = end
        self.buffer_size = buffer_size
        self._seed       = seed
        self._epoch      = 0

    def __len__(self) -> int:
        return self.end - self.start

    def __iter__(self):
        rng  = np.random.default_rng(self._seed + self._epoch)
        self._epoch += 1

        buf_f = np.empty((self.buffer_size, FEATURES), dtype=np.float32)
        buf_t = np.empty(self.buffer_size,             dtype=np.float32)
        fill  = 0

        with open(self.path, "rb") as fh:
            fh.seek(HEADER_SIZE + self.start * RECORD_SIZE)
            remaining = self.end - self.start

            while remaining > 0:
                chunk = min(_IO_CHUNK, remaining)
                raw   = np.frombuffer(fh.read(chunk * RECORD_SIZE), dtype=np.uint8)
                raw   = raw.reshape(chunk, RECORD_SIZE)
                remaining -= chunk

                for rec in raw:
                    feat   = rec[:FEATURES].astype(np.float32)
                    target = float(np.frombuffer(bytes(rec[FEATURES:]), dtype="<f4")[0])

                    if fill < self.buffer_size:
                        buf_f[fill] = feat
                        buf_t[fill] = target
                        fill += 1
                    else:
                        idx        = int(rng.integers(0, self.buffer_size))
                        out_f      = buf_f[idx].copy()
                        out_t      = float(buf_t[idx])
                        buf_f[idx] = feat
                        buf_t[idx] = target
                        yield (
                            torch.from_numpy(out_f),
                            torch.tensor(out_t, dtype=torch.float32),
                        )

        # drain remaining buffer in random order
        for idx in rng.permutation(fill):
            yield (
                torch.from_numpy(buf_f[idx].copy()),
                torch.tensor(float(buf_t[idx]), dtype=torch.float32),
            )


class PositionDataset(Dataset):
    """Random-access dataset backed by a memory-mapped byte range.

    Suitable for small subsets (val/test, typically a few hundred MB).
    For the full training set use StreamingPositionDataset instead.
    """

    def __init__(self, path: str, start: int = 0, end: int | None = None) -> None:
        n_total = record_count(path)
        end     = end if end is not None else n_total
        self._n = end - start
        self._data = np.memmap(
            path,
            dtype=np.uint8,
            mode="r",
            offset=HEADER_SIZE + start * RECORD_SIZE,
            shape=(self._n, RECORD_SIZE),
        )

    def __len__(self) -> int:
        return self._n

    def __getitem__(self, idx: int):
        record   = self._data[idx]
        features = record[:FEATURES].astype(np.float32)
        target   = float(np.frombuffer(record[FEATURES:].tobytes(), dtype="<f4")[0])
        return torch.from_numpy(features), torch.tensor(target, dtype=torch.float32)
