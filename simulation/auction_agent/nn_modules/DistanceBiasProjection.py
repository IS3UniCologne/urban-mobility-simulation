import torch
import torch.nn as nn

class DistanceBiasProjection(nn.Module):
    def __init__(self, hidden_dim: int = 16):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(1, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        """
        Args:
            distances: Tensor of shape (Batch, Query_len, Key_len)
        Returns:
            Transformed bias tensor of shape (Batch, Query_len, Key_len)
        """
        x = distances.unsqueeze(-1)
        
        x = self.mlp(x)
        
        return x.squeeze(-1)