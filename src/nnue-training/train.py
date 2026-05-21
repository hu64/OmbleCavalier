"""
Train the NNUE model on positions.bin produced by prepare_data.py.

Loss  : MSE between predicted win-probability and target win-probability.
Target: sigmoid(cp_stm / 400), already embedded in the dataset file.

Typical run
───────────
  python train.py \\
      --data  data/positions.bin \\
      --out   checkpoints/ \\
      --epochs 3 \\
      --batch  16384

The best model (lowest validation loss) is saved as checkpoints/best.pt.
After training, run export.py to convert best.pt → a .nnue file.
"""
import argparse
import os
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from dataset import PositionDataset
from model import NNUE


def _pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _make_loader(dataset, batch_size: int, shuffle: bool, device: torch.device) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=min(4, os.cpu_count() or 1),
        # pin_memory only helps on CUDA; MPS uses unified memory so it's a no-op
        # and can cause warnings on macOS
        pin_memory=(device.type == "cuda"),
        persistent_workers=True,
    )


def train(
    data_path: str,
    out_dir: str,
    epochs: int,
    batch_size: int,
    lr: float,
    val_fraction: float,
) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    device = _pick_device()
    print(f"Device : {device}")

    full_dataset = PositionDataset(data_path)
    n_val  = max(1, int(len(full_dataset) * val_fraction))
    n_train = len(full_dataset) - n_val
    train_ds, val_ds = random_split(
        full_dataset,
        [n_train, n_val],
        generator=torch.Generator().manual_seed(42),
    )
    print(f"Dataset: {n_train:,} train  |  {n_val:,} val")

    train_loader = _make_loader(train_ds, batch_size, shuffle=True,  device=device)
    val_loader   = _make_loader(val_ds,   batch_size, shuffle=False, device=device)

    model     = NNUE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs * len(train_loader), eta_min=lr * 0.01
    )
    loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    log_interval  = max(1, len(train_loader) // 20)   # ~20 log lines per epoch

    for epoch in range(1, epochs + 1):
        # ── Training ────────────────────────────────────────────────────
        model.train()
        running_loss = 0.0
        t0 = time.time()

        for step, (features, targets) in enumerate(train_loader, 1):
            features = features.to(device)
            targets  = targets.to(device).unsqueeze(1)

            optimizer.zero_grad(set_to_none=True)
            preds = torch.sigmoid(model(features))
            loss  = loss_fn(preds, targets)
            loss.backward()
            optimizer.step()
            scheduler.step()

            running_loss += loss.item()

            if step % log_interval == 0:
                avg = running_loss / log_interval
                elapsed = time.time() - t0
                pos_per_s = step * batch_size / elapsed
                print(
                    f"Epoch {epoch}/{epochs}  step {step:>6}/{len(train_loader)}"
                    f"  loss {avg:.6f}  lr {scheduler.get_last_lr()[0]:.2e}"
                    f"  {pos_per_s:,.0f} pos/s"
                )
                running_loss = 0.0

        # ── Validation ──────────────────────────────────────────────────
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for features, targets in val_loader:
                features = features.to(device)
                targets  = targets.to(device).unsqueeze(1)
                preds    = torch.sigmoid(model(features))
                val_loss += loss_fn(preds, targets).item()
        val_loss /= len(val_loader)

        print(f"── Epoch {epoch} done  val_loss {val_loss:.6f}  ({time.time()-t0:.0f}s) ──")

        # Save checkpoint every epoch
        ckpt_path = os.path.join(out_dir, f"nnue_epoch{epoch}.pt")
        torch.save(model.state_dict(), ckpt_path)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_path = os.path.join(out_dir, "best.pt")
            torch.save(model.state_dict(), best_path)
            print(f"   ↳ New best  ({best_val_loss:.6f})  → {best_path}")

    print(f"\nTraining complete.  Best val_loss: {best_val_loss:.6f}")
    print(f"Best model: {os.path.join(out_dir, 'best.pt')}")
    print("Next: python export.py --model checkpoints/best.pt --output omblecavalier.nnue")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train NNUE model")
    parser.add_argument("--data",   default="data/positions.bin", help="Training data binary")
    parser.add_argument("--out",    default="checkpoints/",       help="Checkpoint directory")
    parser.add_argument("--epochs", type=int,   default=3,        help="Epochs (default 3)")
    parser.add_argument("--batch",  type=int,   default=16384,    help="Batch size (default 16384)")
    parser.add_argument("--lr",     type=float, default=1e-3,     help="Initial learning rate (default 1e-3)")
    parser.add_argument("--val-fraction", type=float, default=0.02, help="Fraction of data for validation (default 0.02)")
    args = parser.parse_args()

    train(
        data_path=args.data,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch,
        lr=args.lr,
        val_fraction=args.val_fraction,
    )


if __name__ == "__main__":
    main()
