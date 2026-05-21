"""
NNUE network: 768 → 256 → 32 → 1.

Hidden layers use ClippedReLU (clamp to [0, 1]) which is the standard
NNUE activation and maps cleanly to int8 quantisation later.
The output is a raw logit; apply sigmoid to get a win-probability in [0, 1].
"""
import torch
import torch.nn as nn

from features import NUM_FEATURES

L1 = 256
L2 = 32


class NNUE(nn.Module):
    def __init__(self):
        super().__init__()
        self.l1 = nn.Linear(NUM_FEATURES, L1)
        self.l2 = nn.Linear(L1, L2)
        self.l3 = nn.Linear(L2, 1)

        # Kaiming init is a good default for clipped-relu nets
        nn.init.kaiming_uniform_(self.l1.weight, nonlinearity="relu")
        nn.init.kaiming_uniform_(self.l2.weight, nonlinearity="relu")
        nn.init.xavier_uniform_(self.l3.weight)
        nn.init.zeros_(self.l1.bias)
        nn.init.zeros_(self.l2.bias)
        nn.init.zeros_(self.l3.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = torch.clamp(self.l1(x), 0.0, 1.0)
        x = torch.clamp(self.l2(x), 0.0, 1.0)
        return self.l3(x)

    # ------------------------------------------------------------------
    # Convenience: return win-probability in [0, 1]
    # ------------------------------------------------------------------
    def win_prob(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(x))
