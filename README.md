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

We use a directory-based configuration system. Each experiment requires a configuration directory containing at least:
- `config.toml`: General settings (logging, experiment management, world resolution, paths).
- `operators.py`: Configuration of mobility service operators and fleets.
- `population.py`: Configuration of the simulated population and their behavior.

We provide a default template for running simulations:

```bash
uv run default_template.py resources/configurations/ridehailing_example
```

> You can also activate the virtual environment that `uv sync` creates in `.venv` manually and use `python default_template.py resources/configurations/ridehailing_example`.

## Simulation Components

The simulation consists of three different types of mobility services:
- **Public transport** (currently only buses)
- **Ride-hailing fleet** (autonomous vehicles and human-driven cars)
- **Shared mobility fleet** (cars, scooters, kickscooters, and bikes)

Configurations are spread across several files in the configuration directory:

### `config.toml`
This file contains the foundational simulation settings:
- **Experiment Management**: Start and end times, and random seeds.
- **World Resolution**: Spatial, temporal, and daily resolution, and the target city.
- **Input Paths**: Paths to demand, supply, transit timetables, and environment data.
- **Logging**: Configurable log levels for different simulation components.

### `operators.py`
This Python file configures the mobility service operators:
- **Fleet Configuration**: Number and types of vehicles, their characteristics (e.g., speed, capacity, energy consumption).
- **Charging Infrastructure**: Location, power, and capacity of charging stations.
- **Operations Management**: Pricing, pickup distance constraints, and recharging thresholds.
- **Search & Allocation Engines**: Strategies for matching users with vehicles.

### `population.py`
This Python file defines the simulated population:
- **Population Segments**: Proportions of different user groups.
- **User Behavior**: Maximum waiting times, walking speeds, and choice models for selecting transportation modes.

### Simulation Execution Flow

Once initialized, the simulation follows these high-level steps:
1. **Data Preparation**: Estimates demand (arrival times, origins, destinations) based on spatio-temporal resolution and calculates distance matrices between hexagons.
2. **Component Initialization**:
   - Initializes search, payment, and vehicle assignment engines for each fleet.
   - Generates fleets and their operators (PublicTransitOperator, RideHailingOperator, etc.).
   - Sets up scheduler modules for charging and relocations.
   - Initializes task queues and service workers.
3. **World Setup**: Integrates engines, infrastructure, and the population factory into the simulation world.
4. **Execution**: Spawns demand processes and runs the simulation until the specified `END_TIME`.

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
# Run everything below
nox -rs

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
