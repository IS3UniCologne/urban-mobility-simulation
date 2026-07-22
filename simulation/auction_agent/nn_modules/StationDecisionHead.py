import torch
import torch.nn as nn

class StationDecisionHead(nn.Module):
    def __init__(self, combined_dim: int, embedding_dim: int, num_stations: int, num_iters: int = 10):
        super().__init__()
        self.num_stations = num_stations
        self.num_iters = num_iters
        
        self.mlp = nn.Sequential(
            nn.Linear(combined_dim, embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, num_stations)
        )

    def forward(
        self, 
        combined_features: torch.Tensor, 
        unreachable_mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        """
        Args:
            combined_features: Tensor of shape (Batch, Vehicle_len, combined_dim)
            unreachable_mask: Optional boolean Tensor of shape (Batch, Vehicle_len, Station_len)
                              where True indicates an unreachable/invalid station.
        Returns:
            Doubly stochastic allocation matrix of shape (Batch, Vehicle_len, Station_len)
        """
        # logits shape: (Batch, Vehicle_len, Station_len)
        logits = self.mlp(combined_features)
        
        # 1. Apply hard action mask prior to exponentiation
        if unreachable_mask is not None:
            # Masked positions get -inf so exp(logits) evaluates to 0.0
            logits = logits.masked_fill(unreachable_mask, float('-inf'))
        
        # 2. Exponentiate to get initial non-negative matrix M
        M = torch.exp(logits)
        
        # Zero out any remaining potential NaNs caused by exp(-inf) arithmetic edge cases
        if unreachable_mask is not None:
            M = M.masked_fill(unreachable_mask, 0.0)

        # 3. Sinkhorn-Knopp Normalization
        # Keeps 0.0 entries at 0.0 while normalizing reachable pairs across rows/cols
        for _ in range(self.num_iters):
            # Row normalization (across stations per vehicle)
            M = M / (M.sum(dim=-1, keepdim=True) + 1e-8)
            # Column normalization (across vehicles per station)
            M = M / (M.sum(dim=-2, keepdim=True) + 1e-8)
            
            # Re-enforce zero mask to prevent epsilon drift (1e-8)
            if unreachable_mask is not None:
                M = M.masked_fill(unreachable_mask, 0.0)
            
        return M