import torch
import torch.nn as nn

class StationDecisionHead(nn.Module):
    def __init__(
        self, 
        combined_dim: int, 
        embedding_dim: int, 
        num_stations: int, 
        num_iters: int = 10
    ):
        super().__init__()
        self.num_stations = num_stations
        self.num_iters = num_iters
        
        self.dummy_vehicle_embedding = nn.Parameter(torch.zeros(1, 1, combined_dim))
        # Output layer projects features to (num_stations + 1) to account for 
        # the single dummy station column.
        self.mlp = nn.Sequential(
            nn.Linear(combined_dim, embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, num_stations + 1)
        )

    def forward(
        self, 
        combined_features: torch.Tensor, 
        station_mask: torch.Tensor | None = None
    ) -> torch.Tensor:
        """
        Args:
            combined_features: Tensor of shape (batch_size, num_vehicles_plus_dummy, combined_dim)
                               Where indices :-1 represent real vehicles and index -1 represents 
                               the single dummy vehicle row.
            station_mask: Optional boolean Tensor of shape (batch_size, num_vehicles_plus_dummy, num_stations_plus_dummy)
                              Where True indicates an invalid/unreachable assignment.
        Returns:
            Doubly stochastic allocation matrix of shape (batch_size, num_vehicles_plus_dummy, num_stations_plus_dummy)
        """

        batch_size = combined_features.shape[0]
        dummy_vehicle_token = self.dummy_vehicle_embedding.expand(batch_size, -1, -1)
        combined_features = torch.cat([combined_features, dummy_vehicle_token], dim=1)
        total_vehicles_with_dummy = combined_features.shape[1]
        total_stations_with_dummy = self.num_stations + 1
        
        num_real_vehicles = total_vehicles_with_dummy - 1
        
        # 1. Compute unnormalized raw logits: shape (batch_size, total_vehicles_with_dummy, total_stations_with_dummy)
        allocation_logits = self.mlp(combined_features)
        
        # 2. Apply action mask prior to exponentiation
        if station_mask is not None:
            allocation_logits = allocation_logits.masked_fill(station_mask, float('-inf'))
        
        # 3. Exponentiate to compute initial non-negative cost/affinity matrix
        # Numerical stabilization: subtract maximum logit per vehicle row to prevent overflow
        max_logits_per_row = torch.max(allocation_logits, dim=-1, keepdim=True).values
        stabilized_logits = allocation_logits - torch.where(
            torch.isneginf(max_logits_per_row), 
            torch.zeros_like(max_logits_per_row), 
            max_logits_per_row
        )
        
        allocation_matrix = torch.exp(stabilized_logits)
        
        if station_mask is not None:
            allocation_matrix = allocation_matrix.masked_fill(station_mask, 0.0)

        # 4. Construct Target Marginals for Weighted Sinkhorn Normalization
        # Target row sums: real vehicles sum to 1.0; dummy vehicle row sums to num_real_stations
        target_row_marginals = torch.ones(
            (1, total_vehicles_with_dummy, 1), 
            device=allocation_logits.device, 
            dtype=allocation_logits.dtype
        )
        target_row_marginals[:, -1, :] = float(self.num_stations)
        
        # Target column sums: real stations sum to 1.0; dummy station column sums to num_real_vehicles
        target_column_marginals = torch.ones(
            (1, 1, total_stations_with_dummy), 
            device=allocation_logits.device, 
            dtype=allocation_logits.dtype
        )
        target_column_marginals[:, :, -1] = float(num_real_vehicles)

        # 5. Iterative Weighted Sinkhorn-Knopp Matrix Scaling
        for _ in range(self.num_iters):
            # Row normalization step (forces each row sum to match its target marginal)
            current_row_sums = allocation_matrix.sum(dim=-1, keepdim=True) + 1e-8
            allocation_matrix = allocation_matrix * (target_row_marginals / current_row_sums)
            
            # Column normalization step (forces each column sum to match its target marginal)
            current_column_sums = allocation_matrix.sum(dim=-2, keepdim=True) + 1e-8
            allocation_matrix = allocation_matrix * (target_column_marginals / current_column_sums)
            
            # Re-enforce unreachable mask to clear numerical drift (1e-8)
            if station_mask is not None:
                allocation_matrix = allocation_matrix.masked_fill(station_mask, 0.0)
            
        return allocation_matrix