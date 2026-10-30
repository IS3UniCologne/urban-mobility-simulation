# Decision-Making Extensions
Many decisions in the simulation, especially on the `Operator` side of things, use decision making of varying complexity.
We aim for generalizable decision making interfaces that can take anything from a simple rule-based decision to dedicated algorithms.
Below we outline two types of extensions that can be used as needed.

## Reinforcement Learning

The `rl` package exposes a simulation as a Gymnasium environment, `rl.env.UmosimEnv`.
It needs the `rl` extra (`uv sync --extra rl`).

### RL Demo

`rl.problems` ships `AdmissionProblem` and `umosim demo` builds a project for it.
In `ridehailing_admission_demo` a learning agent offers or defers each ride request
through `BrokeredAdmissionSearchEngine`, a synchronous decision point inside the user's
search. The project's `run.py` sweeps the fixed policies in `scripts/rl_baselines.py`
and prints the episode profit, fulfilled trips, lost users and mean wait a trained
policy has to beat:

```bash
uv run umosim run ridehailing_admission_demo
```

Stepping the environment by hand, from the repository root:

```python
from rl.env import UmosimEnv
from rl.problems import AdmissionProblem

env = UmosimEnv(
    "data/projects/ridehailing_admission_demo", AdmissionProblem(), horizon_min=1440
)
observation, info = env.reset(seed=1)
observation, reward, terminated, truncated, info = env.step(env.action_space.sample())
env.close()
```

Training is the trainer's job, none is bundled. With Stable-Baselines3 installed
(`uv pip install stable-baselines3`), the environment trains as any other. Train the
admission problem on its `Surplus` reward, which pays each decision the estimated surplus of the assignment it offered.
Evaluate the policy on
the default `Profit` reward, whose rewards sum to the profit after the first decision point:

```python
from stable_baselines3 import PPO

from rl.env import UmosimEnv
from rl.problems import AdmissionProblem
from rl.problems.admission import Surplus

project = "data/projects/ridehailing_admission_demo"
model = PPO(
    "MlpPolicy",
    UmosimEnv(
        project, AdmissionProblem(Surplus(wait_cost_per_min=0.3)), horizon_min=1440
    ),
)
model.learn(total_timesteps=1_000_000)

env = UmosimEnv(project, AdmissionProblem(), horizon_min=1440)
observation, _ = env.reset(seed=1)
profit = 0.0
while True:
    observation, reward, terminated, truncated, _ = env.step(
        model.predict(observation, deterministic=True)[0]
    )
    profit += reward
    if terminated or truncated:
        break
```

### Build your own Problem:
1. Subclass `rl.operator_problem.OperatorProblem` to define the observation, action and reward
   when the learning agent acts for one operator, otherwise `rl.problem.Problem`.
2. Select (or write) a seam adapter from `rl.adapters` in the project's `operators.py` through the
   matching `*_TYPE` field, e.g. `SEARCH_ENGINE_TYPE=BrokeredAdmissionSearchEngine`.
3. Create the environment with `UmosimEnv(project_dir, YourProblem())`.

## Mathematical Optimization

> This needs the `ml` extra (`uv sync --extra ml`) and installs pyomo which we prefer for optimization.

For more classical "one-shot" problems, we do not have a dedicated package and harness / framework, but we still aim for plug-and-play substitutability of algorithms through configuration, as long as the algorithm implements a specific decision method.
In the following, we shortly show one example:

A `RideHailingOperator` faces, among others, the question of vehicle-to-charger allocation.
We subclass `RideHailingOperations` in `RideHailingMPChargingOperations` to patch the `execute` loop with a snippet that delegates this charger dispatch decision to an abstract algorithm, which we configure through `CHARGING_ALGORITHM_TYPE`.

```python
# generate charging allocation using mathematical programming
# list of pairs {vehicle: V, charging_station: C}
allocations = self._algo.generate_charging_allocation(
    vehicles_to_charge,
    self._virtual_charging_infrastructure.charging_stations,
)
```

In this exemplary case, it's a simple program implemented in `simulation/operator/operations_management/algorithms/charging_station_allocation.py` which allocates vehicles to charging stations with the objective of minimizing fleet downtime (driving time + queueing time + charging time of all vehicles sent charging). As long as the algorithm class configured in `CHARGING_ALGORITHM_TYPE` exposes a public method `generate_charging_allocation` that takes vehicles and chargers as arguments and returns a list of allocation pairs {vehicle: V, charging_station: C}, it's as simple as pointing the [operator configuration](configuration.md#operatorspy) to your own program.
