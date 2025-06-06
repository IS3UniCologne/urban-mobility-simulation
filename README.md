# urban-mobility-simulation

[![ruff-fix.yml](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml/badge.svg)](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml)
[![ci.yml](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ci.yml/badge.svg)](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ci.yml)

We provide a simulation platform considering shared mobility (ride sharing, vehicle sharing) services along with infrastructure services (e.g., charging)

## Setup

> We use [uv](https://github.com/astral-sh/uv) for dependency management.

- To create a virtual environment and install all dependencies simply run `uv sync`
- Optional notebook specific dependencies can be installed using `uv sync --extra notebooks`
- Optional machine learning and optimization dependencies can be installed using `uv sync --extra ml`
- Use `uv sync --all-extras` to install all optional dependencies simultaneously

## Running an experiment

> We provide templates (`*_template.py`) for most common use cases, please refer to these!
> At the moment, `template_all_modes.py` is not working, we first need to fix several issues for true multi-modal users.

Provide configuration files as the first argument after the experiment file name such as `uv run experiment_template.py ./resources/configurations/template.toml`

> You can also activate the virtual environment that `uv sync` creates in `.venv` manually and use `python experiment_template.py ./resources/configurations/template.toml`.

## Simulation Components

> The simulation consists of three different types of mobility services:

- _public transport (currently only busses)_
- _ride-hailing fleet (autonomous vehicles and ride-hailing cars)_
- _shared mobility fleet (Cars, scooters, kickscooters and bikes)_

The configurations of these fleets and their operator modules together with other components such as the charging infrastructure, spatial/temporal resolution and world are initialized with the information set in the `template.toml`

This file is used to set various parameters in the following blocks that are required in every simulation:

- **Experiment Management**:
  Contains the **start and end time** of the simulation and additionally a **seed**.

- **World Resolution**:
  Contains the **spatial, temporal and daily resolution** and the city to be simulated.

- **Input Files**:
  Loads files regarding **demand, supply, supply probability, transit timetable (for the busses) and environment** (layers for different resolutions).

- **Public Operator Configuration**:
  Initializes the **User and TransitOperator** configurations with variables such as the **max number of busses** and **maximum waiting time** of a user.

- **Shared Vehicle Fleet Configuration**:
  Initializes the **Shared Vehicle and Shared Vehicle Operator** configuratons with variables such as **energy consumptions, prices and initial SoCs** belonging to different vehicle types and the **base regions** in which **service workers** of the Operator are active.

- **RideHailing Fleet Configuration**:
  Initializes RideHailing Operator and several other configurations with variables such as **energy consumptions, prices and initial SoCs** belonging to different vehicle types and the **base regions** in which **service workers** of the Operator are active. There are also only ridehailing specific variables such as the **driver payment share**.

- **Charging Infrastructure**:
  Contains charging configurations such as the **charging power and capacity of the charging stations**. Initializes the Charging Infrastructure configuration.

- **Output Configuration**:
  Initiliazes the Global configuration with parameters required for output management such as the path for the **output/transactions files**

- **Logging**:
  Initializes a **basic configuration** for logging outputs and adds **custom filters** to these.

- **Loading Demand Data and Distance Matrix**:
  Estimates demand regarding arrival times and origin destinations in spatio-temporal resolution and calculates a matrix with the distances between hexagons.

- **Simulation Modules**:
  - Initialize the **search** (helps users search for vehicles), **payment** (manages the transactions at the end of each trip) and **vehicle assignment** (assigns the chosen vehicle to the user) engines. Currently all fleets use their own engines.
  - Generate the fleets and their respective configuration files.
  - Initialize the respective **operators** of the fleets (PublicTransitOperator,OperationsRideHailing and Operations).
  - Ridehailing and shared mobility fleets also get **scheduler modules** for the planning of their charging schedules and the relocations of the vehicles (RebalancingScheduler and RelocationScheduler).
  - Initiliaze **task queues** and **service workers** for ridehailing and shared mobility fleets. Service workers are assigned these tasks to move the vehicles to the charging stations or relocate them.
  - Initialize **world** with the engines, charging infrastructure and **population factory**.
  - Start spawning demand processes with the **demand factory**.
  - Run the simulation until _end_time_.

## Development

We mostly try to adhere to [trunk-based development](https://trunkbaseddevelopment.com/) with `develop` being our "trunk".
What this means is that we do issues that translate to feature branches that should be short-lived, but if they stick around for longer, you need to make sure to be up-to-date with `develop` by merging it to this branch from time to time.
All active feature branches should have an active pull request associated to track progress.

### Ruff linter and formatter

All pull requests must conform in formatting and linting to the interpretation of _ruff_ on _blacks_ code style and to the PEP definitions and their interpretation. In case a pull request's check of the _ruff_ style fails, you have to run ruff locally. Simply use the following command:

```
uv run ruff check .
```

In the output, you can see what exactly is causing the problems. In order for the pull request to pass, you need to fix all issues and commit the changes to your pull request. After that, the code checks should complete successfully.

You can use ruff to format your code as well. In that case, use the following command:

```
uv run ruff format
```

### Handling Ruff Noqa Statements

Our codebase currently contains numerous `#noqa` comments that suppress ruff warnings. While these were necessary to maintain compatibility during the transition to ruff, we would like to gradually reduce and eliminate them.

#### Example Noqa Comments

```python
# Suppress specific rule
def example():  # noqa: ANN201
    pass

# Suppress multiple rules
variable = value  # noqa: ANN001, SLF001

# Suppress all rules (please don't do this :) )
problematic_code()  # noqa
```

#### Ruff rules explanation

All ruff rules can be looked up via their code here: https://docs.astral.sh/ruff/rules/

This includes examples with suggested fixes.


#### Gradual Cleanup Strategy

If you are modifying an existing class or function containing `#noqa`  statements, please take the opportunity to fix them. Ruff will automatically remove the `#noqa` statement once it is no longer necessary.

### Task automation with Nox

> We use [nox](https://nox.thea.codes/) for task automation and testing across multiple Python environments. This ensures that all tasks run in a clean and reproducible environment. The CI pipeline also uses the same nox sessions.

#### Available Nox Sessions:

```bash
# Run type checking with mypy
nox -rs mypy

# Run pre-commit hooks (linting, formatting, etc.)
nox -rs pre-commit

# Run all tests
nox -rs pytest

# Run only unit tests
nox -rs pytest -- -m unit

# Run only integration tests
nox -rs pytest -- -m integration
```
