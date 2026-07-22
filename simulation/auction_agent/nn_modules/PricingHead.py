import torch
import torch.nn as nn

class PricingHead(nn.Module):
    def __init__(self, combined_dim: int, embedding_dim: int, num_stations: int):
        super().__init__()
        self.num_stations = num_stations
        
        self.mlp = nn.Sequential(
            nn.Linear(combined_dim, embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, num_stations * 2)
        )

    def forward(self, combined_features: torch.Tensor) -> torch.Tensor:
        """
        Returns:
            Tensor of shape (Batch, Vehicle_len, Station_len, 2) 
            where dim=-1 contains [mean, std_dev] for every vehicle-station pair.
        """
        dist_params = self.mlp(combined_features)
        
        mean_logits, raw_std_logits = torch.split(dist_params, self.num_stations, dim=-1)
        
        means = mean_logits
        stds = torch.exp(raw_std_logits)
        
        return torch.stack([means, stds], dim=-1)