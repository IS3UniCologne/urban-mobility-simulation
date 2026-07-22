import torch
import torch.nn as nn
import gymnasium as gym
from simulation.auction_agent.nn_modules.BiasedCrossAttention import BiasedCrossAttention
from simulation.auction_agent.nn_modules.StationDecisionHead import StationDecisionHead
from simulation.auction_agent.nn_modules.PricingHead import PricingHead
from simulation.auction_agent.nn_modules.DistanceBiasProjection import DistanceBiasProjection
from simulation.auction_agent.nn_modules.PMA import PMA
from simulation.auction_agent.nn_modules.SAB import SAB


class PermutationInvariantCritic(nn.Module):
    def __init__(self, observation_space: gym.spaces.Dict, num_seeds: int, embedding_dim: int = 64,num_heads: int = 2, num_inds: int = 32, ln: bool = False):
        super().__init__()
        
        self.vehicle_dim = observation_space['vehicles'].feature_space.shape[0]
        self.user_dim = observation_space['users'].feature_space.shape[0]
        self.station_dim = observation_space['stations'].feature_space.shape[0]

        # 1. Replicated Input Heads from Actor
        self.user_head = nn.Sequential(
            nn.Linear(self.user_dim, embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, embedding_dim)
        )
        self.station_head = nn.Sequential(
            nn.Linear(self.station_dim, embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, embedding_dim)
        )
        
        self.vehicle_proj = nn.Linear(self.vehicle_dim, embedding_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim, nhead=num_heads, dim_feedforward=embedding_dim * 2, batch_first=True
        )
        self.vehicle_transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)

        # 2. Replicated Context Aggregation from Actor
        self.cross_attn_users = BiasedCrossAttention(embed_dim=embedding_dim, num_heads=num_heads)
        self.cross_attn_stations = BiasedCrossAttention(embed_dim=embedding_dim, num_heads=num_heads)
        
        self.user_distance_bias_projection = DistanceBiasProjection()
        self.cs_distance_bias_projection = DistanceBiasProjection()

        # 3. Critic Compression (Set Transformer Aggregator)
        # Combines user_context and station_context (embedding_dim * 2)
        self.dec = nn.Sequential(
            PMA(embedding_dim * 2, num_heads, num_seeds=num_seeds, ln=ln),
            SAB(embedding_dim * 2, embedding_dim, num_heads, ln=ln),
            nn.Linear(embedding_dim, 1)
        )

    def forward(self, obs):
        # Extract inputs
        vehicles_raw, users_raw, stations_raw = obs['vehicles'], obs['users'], obs['stations']
        user_distances, cs_distances, users_mask = obs['user_distances'], obs['cs_distances'], obs['users_mask']
        
        # Process input heads (Exactly like Actor)
        user_encodings = self.user_head(users_raw).masked_fill(users_mask.unsqueeze(-1), 0.0)
        station_encodings = self.station_head(stations_raw)
        
        vehicle_projections = self.vehicle_proj(vehicles_raw)
        vehicle_encodings = self.vehicle_transformer(vehicle_projections)

        # Apply biased cross attention (Reduces sets to shape: Batch, V_len, embedding_dim)
        user_distance_biases = self.user_distance_bias_projection(user_distances)
        cs_distances_biases = self.cs_distance_bias_projection(cs_distances)

        user_context = self.cross_attn_users(query=vehicle_encodings, key=user_encodings, value=user_encodings, attn_bias=user_distance_biases, key_padding_mask=users_mask)
        station_context = self.cross_attn_stations(query=vehicle_encodings, key=station_encodings, value=station_encodings, attn_bias=cs_distances_biases)

        # Shape: (Batch, V_len, embedding_dim * 2)
        combined = torch.cat([user_context, station_context], dim=-1)

        # Compress V_len tokens down to 1 scalar value
        val = self.dec(combined) 
        return val.squeeze(-1) # Shape: (Batch, 1)