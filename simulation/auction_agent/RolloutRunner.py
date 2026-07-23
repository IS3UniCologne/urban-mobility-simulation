import torch
import torch.nn as  nn 

class RolloutRunner:
    def __init__(self, env, actor, critic, num_vehicles, num_stations, rollout_steps=1440, device="cpu"):
        self.env = env
        self.actor = actor.to(device)
        self.critic = critic.to(device)
        self.rollout_steps = rollout_steps
        self.device = device
        self.num_vehicles = num_vehicles
        # each vehicle needs a dummy stations and vice versa 
        self.num_stations = num_stations
        self.max_users = 50
        self.MAX_RELOCATION_TIME = 30
        self.fleet_mask_tensor = torch.as_tensor(self.env.fleet_mask, dtype=torch.long, device=self.device)
        self.max_relocation_distances_normalized = [(operator.OPERATIONS_CONFIG.VEHICLE_RELOCATION_VELOCITY * self.MAX_RELOCATION_TIME) / self.env.feature_extractor.max_distance for operator in self.env.simulation.config.operators]


    def collect_rollout(self):      
        operator_indices = range(self.env.num_operators)

        operator_buffers = []
        for op_idx in operator_indices:
            num_op_vehicles = len(self.env.simulation.world.operators[op_idx].fleet.vehicles)

            operator_buffers.append({
                'allocations': torch.zeros((self.rollout_steps, num_op_vehicles), dtype=torch.long, device=self.device),
                'pricing': torch.zeros((self.rollout_steps, num_op_vehicles), dtype=torch.float, device=self.device),
                'log_probs': torch.zeros((self.rollout_steps), dtype=torch.float, device=self.device),
                'rewards': torch.zeros((self.rollout_steps), dtype=torch.float, device=self.device),
                'masks': torch.zeros((self.rollout_steps), dtype=torch.float, device=self.device),
                
                'obs_vehicles': torch.zeros((self.rollout_steps, num_op_vehicles, self.critic.vehicle_dim), device=self.device),
                'obs_cs_distances': torch.zeros((self.rollout_steps, num_op_vehicles, self.num_stations), device=self.device),
                'obs_user_distances': torch.zeros((self.rollout_steps, num_op_vehicles, self.max_users), device=self.device),

                'value': torch.zeros((self.rollout_steps), dtype=torch.float, device=self.device),
            })

        # Global environment shared observation tracking (users and stations)
        global_obs_buffers = {
            'users': torch.zeros((self.rollout_steps, self.max_users, self.actor.user_dim), device=self.device),
            'users_mask': torch.ones((self.rollout_steps, self.max_users), dtype=torch.bool, device=self.device),
            'stations': torch.zeros((self.rollout_steps, self.num_stations, self.actor.station_dim), device=self.device),
        }

        obs, _ = self.env.reset()
        
        with torch.no_grad():
            for step in range(self.rollout_steps):
                
                # Convert raw incoming dictionary entries to tensors on GPU
                for key in obs.keys():
                    obs[key] = torch.as_tensor(obs[key], dtype=torch.float32, device=self.device)

                # Store global shared tracking states
                global_obs_buffers['stations'][step] = obs['stations']
                
                current_num_users = obs['users'].shape[0] 
                global_obs_buffers['users_mask'][step] = True # Default to mask out all slots
                
                if current_num_users > 0:
                    global_obs_buffers['users'][step, :current_num_users] = obs['users']
                    global_obs_buffers['users_mask'][step, :current_num_users] = False

                # 2. Slice flat environment structures into GPU-level fleet views
                all_fleets_vehicles = torch.tensor_split(obs['vehicles'], self.fleet_mask_tensor, dim=0)
                all_fleets_cs_dist = torch.tensor_split(obs['cs_distances'], self.fleet_mask_tensor, dim=0)
                all_fleets_user_dist = torch.tensor_split(obs['user_distances'], self.fleet_mask_tensor, dim=0)

                # Delivery container for everyone's actions for self.env.step()
                combined_env_actions = []

                # 3. Iterate independently through each operator to build observations and make decisions
                for op_idx in operator_indices:
                    op_vehicles = all_fleets_vehicles[op_idx]
                    op_cs_dist = all_fleets_cs_dist[op_idx]
                    op_user_dist_raw = all_fleets_user_dist[op_idx]
                    
                    # Store clean, decoupled features into this operator's step buffers
                    operator_buffers[op_idx]['obs_vehicles'][step] = op_vehicles
                    operator_buffers[op_idx]['obs_cs_distances'][step] = op_cs_dist
                    
                    if current_num_users > 0:
                        operator_buffers[op_idx]['obs_user_distances'][step, :, :current_num_users] = op_user_dist_raw[:, :current_num_users]

                    max_reachable_distance = self.max_relocation_distances_normalized[op_idx]


                    stations_mask = self.create_sinkhorn_station_mask(op_cs_dist, max_reachable_distance, op_vehicles, self.env.num_operators)

                    # 4. Construct a static padded dictionary view adding the batch dimension [None, ...]
                    padded_obs_step_actor = {
                        'vehicles': op_vehicles[None, :, self.env.num_operators:],
                        'cs_distances': op_cs_dist[None, ...],
                        'stations': global_obs_buffers['stations'][step][None, ...],
                        'users': global_obs_buffers['users'][step][None, ...],
                        'user_distances': operator_buffers[op_idx]['obs_user_distances'][step][None, ...],
                        'users_mask': global_obs_buffers['users_mask'][step][None, ...],
                        'stations_mask': stations_mask[None, ...],
                    }
                    
                    # 5. Forward Pass through Actor
                    station_matrix, pricing_matrix = self.actor(padded_obs_step_actor)
                    
                    # 6. Joint Action Space Sampling
                    allocations, allocation_log_prob = self._sample_from_doubly_stochastic_matrix(station_matrix)
                    
                    means = pricing_matrix[..., 0]
                    stds = torch.clamp(pricing_matrix[..., 1], min=1e-3)
                    price_dist = torch.distributions.Normal(means, stds)
                    all_sampled_prices = price_dist.sample()
                    all_price_log_probs = price_dist.log_prob(all_sampled_prices)

                    
                    # 1. Identify dummy selections
                    is_dummy = allocations >= self.num_stations

                    # 2. Clamp allocations to construct the safe gather index tensor (3D for 3D tensors)
                    gather_index = allocations.clamp(0, self.num_stations - 1).unsqueeze(-1)

                    # --- CHOSEN PRICES ---
                    # Gather from all_sampled_prices using allocations as the index
                    gathered_prices = torch.gather(all_sampled_prices, dim=-1, index=gather_index).squeeze(-1)
                    chosen_prices = torch.where(is_dummy, torch.zeros_like(gathered_prices), gathered_prices)

                    # --- CHOSEN PRICE LOG PROBS ---
                    # Gather from all_price_log_probs using allocations as the index
                    gathered_log_probs = torch.gather(all_price_log_probs, dim=-1, index=gather_index).squeeze(-1)
                    chosen_price_log_probs = torch.where(is_dummy, torch.zeros_like(gathered_log_probs), gathered_log_probs)
                    
                    # Sum the pricing log probabilities across the fleet dimensions and join
                    joint_log_prob = allocation_log_prob + chosen_price_log_probs.sum(dim=-1)

                    # 7. Package this fleet's action array for the physical environment simulation
                    actions_combined = torch.stack([allocations.squeeze(0).float(), chosen_prices.squeeze(0)], dim=-1)
                    op_actions_np = actions_combined.cpu().numpy() 
                    combined_env_actions.append(op_actions_np)
                    
                    # 8. Record step results into the operator's private buffer layout
                    operator_buffers[op_idx]['allocations'][step] = allocations.squeeze(0)
                    operator_buffers[op_idx]['pricing'][step] = chosen_prices.squeeze(0)
                    operator_buffers[op_idx]['log_probs'][step] = joint_log_prob.squeeze(0)

                global_critic_obs = {
                    'vehicles': torch.cat([operator_buffers[i]['obs_vehicles'][step] for i in operator_indices], dim=0)[None, ...],
                    'cs_distances': torch.cat([operator_buffers[i]['obs_cs_distances'][step] for i in operator_indices], dim=0)[None, ...],
                    'user_distances': torch.cat([operator_buffers[i]['obs_user_distances'][step] for i in operator_indices], dim=0)[None, ...],
                    'stations': global_obs_buffers['stations'][step][None, ...],
                    'users': global_obs_buffers['users'][step][None, ...],
                    'users_mask': global_obs_buffers['users_mask'][step][None, ...]
                }

                # Run Centralized Critic once and distribute value scores back to operator storage
                global_values = self.critic(global_critic_obs)

                for op_idx in operator_indices:
                    operator_buffers[op_idx]['value'][step] = global_values[0, op_idx]

                battery_states = [[vehicle.energy_system.current_energy_absolute for vehicle in operator.fleet.vehicles] for operator in self.env.simulation.world.operators]

                # 9. Execute competitive unified step in environment
                next_obs, rewards, terminated, truncated, _ = self.env.step(combined_env_actions)
                
                # 10. Save isolated rewards and termination trackers to respective buffers
                for op_idx in operator_indices:
                    operator_buffers[op_idx]['rewards'][step] = rewards[op_idx]
                    operator_buffers[op_idx]['masks'][step] = 0.0 if terminated else 1.0
                
                if terminated or truncated:
                    obs, _ = self.env.reset()
                else:
                    obs = next_obs
                    
        return operator_buffers, global_obs_buffers

    def _sample_from_doubly_stochastic_matrix(self, sinkhorn_matrix: torch.Tensor):
        batch_size, num_rows, num_columns = sinkhorn_matrix.shape
        flat_probs = sinkhorn_matrix.view(-1, num_columns)
        flat_samples = torch.multinomial(flat_probs, num_samples=1)
        selected_indices = flat_samples.view(batch_size, num_rows)
        
        chosen_probs = torch.gather(
            sinkhorn_matrix, 
            dim=-1, 
            index=selected_indices.unsqueeze(-1)
        )
        individual_log_probs = torch.log(chosen_probs.squeeze(-1) + 1e-8)
        joint_action_log_probs = individual_log_probs.sum(dim=-1)
        return selected_indices[:, :-1], joint_action_log_probs

    def create_sinkhorn_station_mask(
        self,
        vehicle_station_distances: torch.Tensor,
        max_reachable_distance: float,
        vehicle_state_tokens: torch.Tensor,
        num_operators: int
    ) -> torch.Tensor:
        """
        Constructs an unreachable mask for the (num_real_vehicles + 1) x (num_real_stations + 1) Sinkhorn matrix.
        
        Args:
            vehicle_station_distances: Tensor of shape (batch_size, num_real_vehicles, num_real_stations)
            max_reachable_distance: Float threshold for distance reachability
            vehicle_state_tokens: Tensor of shape (batch_size, num_real_vehicles, feature_dim)
            num_operators: Integer offset used to locate the reservation feature index
            
        Returns:
            station_mask: BoolTensor of shape (batch_size, num_real_vehicles + 1, num_real_stations + 1)
                            True indicates an invalid/masked assignment.
        """
        num_real_vehicles, num_real_stations = vehicle_station_distances.shape
        device = vehicle_station_distances.device

        real_distance_mask = vehicle_station_distances > max_reachable_distance

        reservation_feature_index = num_operators + 1
        is_reserved_vehicle = (vehicle_state_tokens[ :, reservation_feature_index] == 1.0)

        reserved_vehicle_mask = is_reserved_vehicle.unsqueeze(-1)
        
        real_vehicles_mask = real_distance_mask | reserved_vehicle_mask

        station_mask = torch.zeros(
            (num_real_vehicles + 1, num_real_stations + 1),
            dtype=torch.bool,
            device=device
        )
        station_mask[:num_real_vehicles, :num_real_stations] = real_vehicles_mask

        return station_mask