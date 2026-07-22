import torch
import torch.nn as nn
import gymnasium as gym
from simulation.auction_agent.nn_modules.BiasedCrossAttention import BiasedCrossAttention
from simulation.auction_agent.nn_modules.StationDecisionHead import StationDecisionHead
from simulation.auction_agent.nn_modules.PricingHead import PricingHead
from simulation.auction_agent.nn_modules.DistanceBiasProjection import DistanceBiasProjection

class MultiEntityActor(nn.Module):
    def __init__(self, observation_space: gym.spaces.Dict, num_stations: int, embedding_dim: int = 64):
        super().__init__()
        
        self.vehicle_dim = observation_space['vehicles'].feature_space.shape[0]
        self.user_dim = observation_space['users'].feature_space.shape[0]
        self.station_dim = observation_space['stations'].feature_space.shape[0]
        
        self.embedding_dim = embedding_dim

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
            d_model=embedding_dim, 
            nhead=2, 
            dim_feedforward=embedding_dim * 2, 
            batch_first=True
        )

        self.vehicle_transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)

        self.cs_distance_bias_projection = DistanceBiasProjection()
        self.user_distance_bias_projection = DistanceBiasProjection()

        self.cross_attn_users = BiasedCrossAttention(
            embed_dim=embedding_dim, num_heads=2
        )
        self.cross_attn_stations = BiasedCrossAttention(
            embed_dim=embedding_dim, num_heads=2
        )
        combined_dim = embedding_dim * 2
        
        self.station_decision_head = StationDecisionHead(
            combined_dim=combined_dim,
            embedding_dim=embedding_dim,
            num_stations=num_stations,
            num_iters=10,
        )
        
        self.pricing_head = PricingHead(
            combined_dim=combined_dim,
            embedding_dim=embedding_dim,
            num_stations=num_stations,
        )

    def forward(self, obs):
        """
        Expects a dictionary where values are tensors of shape:
        - vehicles: (Batch, V_len, vehicle_dim)
        - users:    (Batch, U_len, user_dim)
        - stations: (Batch, S_len, station_dim)
        """
        
        vehicles_raw = obs['vehicles']
        cs_distances = obs['cs_distances']
        user_distances = obs['user_distances']
        users_raw = obs['users']
        stations_raw = obs['stations']
        users_mask = obs['users_mask']
        
        user_encodings = self.user_head(users_raw)
        user_encodings = user_encodings.masked_fill(users_mask.unsqueeze(-1), 0.0)
        station_encodings = self.station_head(stations_raw)
        
        vehicle_projections = self.vehicle_proj(vehicles_raw)
        vehicle_encodings = self.vehicle_transformer(vehicle_projections)

        user_distance_biases = self.user_distance_bias_projection(user_distances)
        cs_distances_biases = self.cs_distance_bias_projection(cs_distances)

        user_context = self.cross_attn_users(query=vehicle_encodings, key=user_encodings, value=user_encodings, attn_bias=user_distance_biases, key_padding_mask=users_mask) 
        station_context = self.cross_attn_stations(query=vehicle_encodings, key=station_encodings, value=station_encodings, attn_bias=cs_distances_biases)

        combined = torch.cat([user_context, station_context], dim=-1)

        station_decision_matrix = self.station_decision_head(combined)
        pricing_matrix = self.pricing_head(combined)

        return station_decision_matrix, pricing_matrix
