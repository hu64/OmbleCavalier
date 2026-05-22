"""
Train the NNUE model on positions.bin produced by prepare_data.py.

Loss  : MSE between predicted win-probability and target win-probability.
Target: sigmoid(cp_stm / 400), already embedded in the dataset file.

Typical run
───────────
  python train.py \\
      --data  data/positions.bin \\
      --out   checkpoints/ \\
      --epochs 20 \\
      --batch  16384

Tracks every metric with MLflow — run `mlflow ui` in this directory to open
the dashboard. Early stopping halts training when val loss stops improving.

Memory note
───────────
The training split uses StreamingPositionDataset: sequential I/O + a fixed
shuffle buffer. Memory usage is O(--shuffle-buffer), not O(file size).
num_workers=0 is intentional — multiple workers each re-map the full file,
which was the source of 90+ GB memory use with the previous approach.
"""
import argparse
import os
import time
from pathlib import Path

import mlflow
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from dataset import PositionDataset, StreamingPositionDataset, record_count
from model import NNUE

# Win-probability thresholds for 3-class outcome accuracy
_WP_WIN  = 0.55
_WP_LOSS = 0.45


def _pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _make_loader(dataset, batch_size: int, device: torch.device) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        # shuffle=False for both: StreamingPositionDataset shuffles internally;
        # PositionDataset (val/test) doesn't need shuffling.
        shuffle=False,
        # num_workers=0: each worker re-maps the full file, which was the
        # cause of 90+ GB RAM use. Sequential streaming makes workers pointless.
        num_workers=0,
        pin_memory=(device.type == "cuda"),
    )


def _empty_cache(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.empty_cache()
    elif device.type == "mps":
        torch.mps.empty_cache()


def _outcome_accuracy(preds: torch.Tensor, targets: torch.Tensor) -> float:
    """% of positions where predicted outcome bucket matches target bucket."""
    def bucket(t: torch.Tensor) -> torch.Tensor:
        return torch.where(t > _WP_WIN, 2, torch.where(t < _WP_LOSS, 0, 1))
    return (bucket(preds.squeeze(1)) == bucket(targets.squeeze(1))).float().mean().item()


def _evaluate(model: nn.Module, loader: DataLoader, loss_fn, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_correct = 0.0
    total_samples = 0
    with torch.no_grad():
        for features, targets in loader:
            features = features.to(device)
            targets  = targets.to(device).unsqueeze(1)
            preds    = torch.sigmoid(model(features))
            total_loss += loss_fn(preds, targets).item()
            b = features.size(0)
            total_correct += _outcome_accuracy(preds, targets) * b
            total_samples += b
    return total_loss / len(loader), total_correct / total_samples


def train(
    data_path: str,
    out_dir: str,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    grad_clip: float,
    val_fraction: float,
    test_fraction: float,
    patience: int,
    shuffle_buffer: int,
) -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    device = _pick_device()
    print(f"Device : {device}")

    # ── Data splits (contiguous byte ranges — no full-file random access) ─
    n_total = record_count(data_path)
    n_test  = max(1, int(n_total * test_fraction))
    n_val   = max(1, int(n_total * val_fraction))
    n_train = n_total - n_val - n_test
    # Layout: [0, n_train) train | [n_train, n_train+n_val) val | rest test
    val_start  = n_train
    test_start = n_train + n_val
    print(f"Dataset: {n_train:,} train  |  {n_val:,} val  |  {n_test:,} test")
    print(f"Shuffle buffer: {shuffle_buffer:,} positions "
          f"({shuffle_buffer * 772 / 1e6:.0f} MB)")

    train_ds = StreamingPositionDataset(
        data_path, start=0, end=n_train,
        buffer_size=shuffle_buffer, seed=42,
    )
    val_ds  = PositionDataset(data_path, start=val_start,  end=test_start)
    test_ds = PositionDataset(data_path, start=test_start, end=n_total)

    train_loader = _make_loader(train_ds, batch_size, device=device)
    val_loader   = _make_loader(val_ds,   batch_size, device=device)
    test_loader  = _make_loader(test_ds,  batch_size, device=device)

    model     = NNUE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs * len(train_loader), eta_min=lr * 0.01
    )
    loss_fn = nn.MSELoss()

    best_val_loss     = float("inf")
    epochs_no_improve = 0
    steps_per_epoch   = (n_train + batch_size - 1) // batch_size
    log_interval      = max(1, steps_per_epoch // 20)

    mlflow.set_experiment("nnue-training")
    with mlflow.start_run():
        mlflow.log_params({
            "epochs_max":     epochs,
            "batch_size":     batch_size,
            "lr":             lr,
            "weight_decay":   weight_decay,
            "grad_clip":      grad_clip,
            "val_fraction":   val_fraction,
            "test_fraction":  test_fraction,
            "patience":       patience,
            "shuffle_buffer": shuffle_buffer,
            "device":         str(device),
            "n_train":        n_train,
            "n_val":          n_val,
            "n_test":         n_test,
        })

        global_step = 0

        for epoch in range(1, epochs + 1):
            # ── Training ──────────────────────────────────────────────────
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
                if grad_clip > 0:
                    nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                optimizer.step()
                scheduler.step()

                running_loss += loss.item()
                global_step  += 1

                if step % log_interval == 0:
                    avg       = running_loss / log_interval
                    elapsed   = time.time() - t0
                    pos_per_s = step * batch_size / elapsed
                    print(
                        f"Epoch {epoch}/{epochs}  step {step:>6}/{steps_per_epoch}"
                        f"  loss {avg:.6f}  lr {scheduler.get_last_lr()[0]:.2e}"
                        f"  {pos_per_s:,.0f} pos/s"
                    )
                    mlflow.log_metric("train_loss", avg, step=global_step)
                    running_loss = 0.0

            # ── Validation ────────────────────────────────────────────────
            val_loss, val_acc = _evaluate(model, val_loader, loss_fn, device)
            elapsed = time.time() - t0
            print(
                f"── Epoch {epoch} done"
                f"  val_loss {val_loss:.6f}  val_acc {val_acc:.4f}"
                f"  ({elapsed:.0f}s) ──"
            )
            mlflow.log_metrics(
                {"val_loss": val_loss, "val_accuracy": val_acc, "lr": scheduler.get_last_lr()[0]},
                step=epoch,
            )

            _empty_cache(device)

            # ── Checkpoint + early stopping ───────────────────────────────
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                epochs_no_improve = 0
                best_path = os.path.join(out_dir, "best.pt")
                torch.save(model.state_dict(), best_path)
                print(f"   ↳ New best ({best_val_loss:.6f}) → {best_path}")
                mlflow.log_metric("best_val_loss", best_val_loss, step=epoch)
            else:
                epochs_no_improve += 1
                print(f"   ↳ No improvement {epochs_no_improve}/{patience}")
                if epochs_no_improve >= patience:
                    print(f"Early stopping at epoch {epoch}.")
                    break

        # ── Test set evaluation (always on best checkpoint) ───────────────
        print("\nEvaluating held-out test set…")
        model.load_state_dict(torch.load(
            os.path.join(out_dir, "best.pt"), map_location=device, weights_only=True
        ))
        test_loss, test_acc = _evaluate(model, test_loader, loss_fn, device)
        print(f"Test  loss {test_loss:.6f}  acc {test_acc:.4f}")
        mlflow.log_metrics({"test_loss": test_loss, "test_accuracy": test_acc})

        print(f"\nTraining complete.  Best val_loss: {best_val_loss:.6f}")
        print(f"Best model : {os.path.join(out_dir, 'best.pt')}")
        print("Next       : python export.py --model checkpoints/best.pt --output omblecavalier.nnue")
        print("Visualise  : mlflow ui")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train NNUE model")
    parser.add_argument("--data",          default="data/positions.bin", help="Training data binary")
    parser.add_argument("--out",           default="checkpoints/",       help="Checkpoint directory")
    parser.add_argument("--epochs",        type=int,   default=20,       help="Max epochs (default 20)")
    parser.add_argument("--batch",         type=int,   default=16384,    help="Batch size (default 16384)")
    parser.add_argument("--lr",            type=float, default=1e-3,     help="Initial LR (default 1e-3)")
    parser.add_argument("--weight-decay",  type=float, default=1e-5,     help="L2 weight decay (default 1e-5)")
    parser.add_argument("--grad-clip",     type=float, default=1.0,      help="Gradient clip norm (default 1.0, 0=off)")
    parser.add_argument("--val-fraction",  type=float, default=0.02,     help="Val fraction (default 0.02)")
    parser.add_argument("--test-fraction", type=float, default=0.02,     help="Test fraction (default 0.02)")
    parser.add_argument("--patience",       type=int,   default=5,        help="Early-stop patience in epochs (default 5)")
    parser.add_argument("--shuffle-buffer", type=int,   default=200_000,  help="Shuffle buffer size in positions (default 200000, ~150 MB)")
    args = parser.parse_args()

    train(
        data_path=args.data,
        out_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch,
        lr=args.lr,
        weight_decay=args.weight_decay,
        grad_clip=args.grad_clip,
        val_fraction=args.val_fraction,
        test_fraction=args.test_fraction,
        patience=args.patience,
        shuffle_buffer=args.shuffle_buffer,
    )


if __name__ == "__main__":
    main()
