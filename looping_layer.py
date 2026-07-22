import numpy as np
import torch
from simulation.auction_agent.GymWrapper import GymWrapper
from dotenv import load_dotenv
from simulation.helper.configuration.configuration import Configuration
import os
from simulation.auction_agent.RolloutRunner import RolloutRunner
from simulation.helper.enums import NUM_USER_STATES
from simulation.auction_agent.Actor import MultiEntityActor
from simulation.auction_agent.Critic import PermutationInvariantCritic

load_dotenv(dotenv_path='.env')

print(os.environ.get("CONFIG_PATH"))
config = Configuration(os.environ.get("CONFIG_PATH"))
print('test')
num_vehicles = sum([next(iter(operator.FLEET_CONFIG.VEHICLES.values())) for operator in config.operators])
num_stations = config.charging_infrastructures[0].NUMBER_OF_CHARGING_STATIONS
num_operators = len(config.operators)

vehicle_dim = num_operators + 15
user_dim = NUM_USER_STATES + 17
stations_dim = 3

env = GymWrapper(num_vehicles=num_vehicles, num_charging_stations=num_stations, num_operators=num_operators, num_user_states=NUM_USER_STATES, config=config, cs_locations=config.charging_infrastructures[0].LOCATIONS)

obs, info = env.reset(seed=42)
print("--- Simulation Initialized ---")

# 1. Setup hyperparameters and dimensions
device = "cuda" if torch.cuda.is_available() else "cpu"
actor = MultiEntityActor(env.observation_space_actor, num_stations, embedding_dim=64)
critic = PermutationInvariantCritic(env.observation_space_critic, num_operators)

# 3. Initialize the Runner
runner = RolloutRunner(
    env=env,
    actor=actor,
    critic=critic,
    num_vehicles=num_vehicles,
    num_stations=num_stations,
    rollout_steps=144,
    device=device
)

# 4. Main Training Loop
num_epochs = 10
for epoch in range(num_epochs):
    # Collect a batch of experience
    operator_buffers,global_buffers = runner.collect_rollout()
    
    # --- Your Training Logic Here ---
    # e.g., Compute policy loss using log_probs and advantages (from rewards)
    # loss = -log_probs * advantages
    # optimizer.zero_grad()
    # loss.backward()
    # optimizer.step()
    