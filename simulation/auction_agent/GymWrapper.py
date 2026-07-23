import gymnasium as gym
from gymnasium import spaces
import numpy as np
import simpy
from typing import TYPE_CHECKING
import math
from enum import Enum
from dotenv import load_dotenv, find_dotenv
import os
import torch

from simulation.auction_agent.Actor import MultiEntityActor
from simulation.context.simulation_context import SimulationContext
from simulation.metrics.metrics import Metrics
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.world import World
from simulation.simulation import Simulation
from simulation.auction_agent.utils import *
from simulation.vehicle.vehicle import Vehicle
from simulation.agent.user.user import User
from simulation.auction_agent.FeatureExtractor import FeatureExtractor
from simulation.helper.configuration.configuration import Configuration

load_dotenv(find_dotenv('.env.auction_agent'))
class GymWrapper(gym.Env):
    """A clean Gymnasium wrapper for an existing SimPy auction simulation."""
    metadata = {"render_modes": ["human"]}

    def __init__(self,
                num_vehicles: int,
                num_charging_stations: int,
                num_operators: int,
                num_user_states: int,
                config: Configuration,
                cs_locations: list[str],
                timeblock_duration: float = 60.0
        ):
        super().__init__()
        self.config = config
        self.feature_extractor = None
        self.timeblock_duration = timeblock_duration
        self.max_time = self.config.experiment_management.END_TIME
        print(os.environ.items())
        self._earnings_per_charge = float(os.environ.get('EARNINGS_PER_CHARGE'))
        self._penalty_decay_rate = float(os.environ.get('PENALTY_DECAY_RATE'))
        # TODO improve configuration data structure (no dictionary as key)
        # assumes all fleets have the same number of vehicles 
        self.cs_locations = cs_locations
        self.vehicle_count = num_vehicles
        self.num_charging_stations = num_charging_stations
        self.num_operators = num_operators
        self.fleet_mask = None
        

        self.action_space = spaces.Box(
            low=0.0, high=100.0, shape=(self.vehicle_count * self.num_charging_stations * 3,), dtype=np.float32
        )

        low_bounds_vehicles_critic = np.array([*([0.0] * num_operators), 0.0, 0.0, -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float32)
        high_bounds_vehicles_critic = np.array([1.0] * low_bounds_vehicles_critic.size, dtype=np.float32)

        low_bounds_vehicles_actor = np.array([0.0, 0.0, -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float32)
        high_bounds_vehicles_actor = np.array([1.0] * low_bounds_vehicles_actor.size, dtype=np.float32)

        low_bounds_users = np.array([*([0.0] * num_user_states), -1.0, -1.0, 0.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float32)
        high_bounds_users = np.array([1.0] * low_bounds_users.size, dtype=np.float32)

        low_bounds_stations = np.array([-1.0, -1.0, 0.0])
        high_bounds_stations = np.array([1.0] * low_bounds_stations.size, dtype=np.float32)


        token_space_vehicles_actor = spaces.Box(low=low_bounds_vehicles_actor, high=high_bounds_vehicles_actor, shape=(low_bounds_vehicles_actor.size,), dtype=np.float32)
        token_space_vehicles_critic = spaces.Box(low=low_bounds_vehicles_critic, high=high_bounds_vehicles_critic, shape=(low_bounds_vehicles_critic.size,), dtype=np.float32)
        token_space_users = spaces.Box(low=low_bounds_users, high=high_bounds_users, shape=(low_bounds_users.size,), dtype=np.float32)
        token_space_stations = spaces.Box(low=low_bounds_stations, high=high_bounds_stations, shape=(low_bounds_stations.size,), dtype=np.float32)

        self.observation_space_actor = spaces.Dict({
            'vehicles': spaces.Sequence(token_space_vehicles_actor),
            'users': spaces.Sequence(token_space_users),
            'stations': spaces.Sequence(token_space_stations),
        })

        self.observation_space_critic = spaces.Dict({
            'vehicles': spaces.Sequence(token_space_vehicles_critic),
            'users': spaces.Sequence(token_space_users),
            'stations': spaces.Sequence(token_space_stations),
        })

    def _get_obs(self):

        fleets = [operator.fleet.vehicles for operator in self.simulation.world.operators]

        if self.fleet_mask is None:
            lengths = [len(vehicles) for vehicles in fleets]
            self.fleet_mask = np.cumsum(lengths)[:-1]

        users = self.simulation.world.users
        time = self.simulation.sim.time
        charging_stations = self.simulation.world.charging_infrastructures[0].charging_stations
        
        vehicle_features, cs_distances_normalized, user_distances_normalized = self.feature_extractor.extract_vehicle_features(fleets, users, time)
        user_features = self.feature_extractor.extract_user_features(users, time)
        station_features = self.feature_extractor.extract_charging_stations_features(charging_stations, time)

        observation_dict = {
            'vehicles': torch.from_numpy(vehicle_features),
            'cs_distances': torch.from_numpy(cs_distances_normalized),
            'user_distances': torch.from_numpy(user_distances_normalized),
            'users': torch.from_numpy(user_features),
            'stations': torch.from_numpy(station_features),
        }

        return observation_dict

    def _get_reward(self, earnings: float, socs: np.ndarray):
        penalty_factor = np.sum(np.exp(-self._penalty_decay_rate * socs)) / socs.size
        return (earnings / socs.size) - self._earnings_per_charge * penalty_factor


    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        self.simulation = Simulation(self.config)
        
        #self.simulation.initialize_simulation()
        if seed is not None:
            np.random.seed(seed)

        self.feature_extractor = FeatureExtractor(self.simulation.world.geo_env, self.cs_locations)
        self.prev_revenues = np.array([0 for operator in self.simulation.world.operators])

        return self._get_obs(), {}

    def step(self, action):
        next_time = self.simulation.sim.env.now + self.timeblock_duration

        actions_by_uid = [[np.append(action[op_index][vehicle_index], vehicle.uid) for vehicle_index, vehicle in enumerate(operator.fleet.vehicles)] for op_index, operator in enumerate(self.simulation.world.operators)]

        bids_per_op = [
                {cs_location: 
                [(1, float(op_bid[1].item()), int(op_index), op_bid[2].item()) for op_bid in op_biddings if float(op_bid[0]) == cs_index]
                for op_biddings in actions_by_uid 
                for cs_index, cs_location in enumerate(self.cs_locations)}
            for op_index, operator in enumerate(self.simulation.world.operators)
        ]

        [operator.operations.bidding_strategy.next_action.succeed(bids_per_op[index]) for index, operator in enumerate(self.simulation.world.operators)]
        
        self.simulation.step_simulation(until_time=next_time)        

        observation_dict = self._get_obs()
  

        operators = self.simulation.world.operators
        current_revenues = np.array([operator.operator_log.metrics.total_revenue for operator in operators])
        revenue_delta = current_revenues - self.prev_revenues
        rewards = [self._get_reward(revenue_delta[index], np.array([vehicle.energy_system.current_energy_relative for vehicle in operator.fleet.vehicles])) for index, operator in enumerate(operators)]
        
        terminated = self.simulation.sim.env.now >= self.max_time
        truncated = False
        
        if terminated or truncated:
            self.simulation.finalize_simulation()
            
        return observation_dict, rewards, terminated, truncated, {}