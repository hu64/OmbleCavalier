"""
NNUE network: 768 → 512 → N_BUCKETS (8 output heads).

Architecture follows Weiawaga/Mimir:
  - L1 widened to 512 for more representational capacity.
  - SCReLU activation: clamp(x, 0, 1)^2  (empirically stronger than plain CReLU).
  - N_BUCKETS independent output heads, one selected per position by piece count.
    Bucket 0 = 32-piece opening, bucket 7 = sparse endgame.
    index = clamp((32 - piece_count) * N_BUCKETS // 32, 0, N_BUCKETS - 1)
  - No L2 hidden layer: with 512-wide L1 and phase-specialised heads, a second
    hidden layer adds cost without measurable gain for this architecture.
"""
import torch
import torch.nn as nn

from features import NUM_FEATURES

L1 = 512
N_BUCKETS = 8


def _screlu(x: torch.Tensor) -> torch.Tensor:
    """Squared Clipped ReLU: clamp(x, 0, 1)²."""
    return torch.clamp(x, 0.0, 1.0) ** 2


def bucket_indices(features: torch.Tensor) -> torch.Tensor:
    """Map a batch of feature vectors to bucket indices (int64).

    piece_count = features.sum(dim=1)  (each active feature = one piece on board)
    bucket      = clamp((32 - piece_count) * N_BUCKETS // 32, 0, N_BUCKETS - 1)
    """
    n_pieces = features.sum(dim=1).long()
    return ((32 - n_pieces) * N_BUCKETS // 32).clamp(0, N_BUCKETS - 1)


class NNUE(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.l1 = nn.Linear(NUM_FEATURES, L1)
        self.output_heads = nn.ModuleList([nn.Linear(L1, 1) for _ in range(N_BUCKETS)])

        nn.init.kaiming_uniform_(self.l1.weight, nonlinearity="relu")
        nn.init.zeros_(self.l1.bias)
        for head in self.output_heads:
            nn.init.xavier_uniform_(head.weight)
            nn.init.zeros_(head.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: (B, 768) float32 feature vectors.
        Returns:
            (B, 1) raw logits.
        """
        buckets = bucket_indices(x)                                  # (B,)
        x1 = _screlu(self.l1(x))                                     # (B, L1)

        # Run all heads in one stack, then gather the correct bucket per sample.
        all_out = torch.stack(
            [head(x1) for head in self.output_heads], dim=1
        ).squeeze(2)                                                  # (B, N_BUCKETS)
        return all_out.gather(1, buckets.unsqueeze(1))                # (B, 1)

    def win_prob(self, x: torch.Tensor) -> torch.Tensor:
        """Win-probability in [0, 1] from side-to-move perspective."""
        return torch.sigmoid(self.forward(x))
