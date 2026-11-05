# urban-mobility-simulation

[![ruff-fix.yml](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml/badge.svg)](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml)
[![ci.yml](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ci.yml/badge.svg)](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ci.yml)

<!-- docs/README.md includes this file from here on -->

We provide a simulation platform considering shared mobility (ride sharing, vehicle sharing) services along with infrastructure services (e.g., charging) and the markets (e.g., Mobility-as-a-Service) that link them to users.

## Installation

> We use [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Create a virtual environment and install all dependencies
uv sync

# Optional extras
uv sync --extra ml    # optimization dependencies
uv sync --extra rl    # Gymnasium environment for reinforcement learning
uv sync --extra viz   # visualization dependencies
uv sync --all-extras  # all the things
```

To also install the git hooks and development tooling, see
[CONTRIBUTING.md](CONTRIBUTING.md#development-setup).

## Quickstart & CLI

The `umosim` CLI scaffolds and runs simulations:

```bash
# Generate a synthetic demo: a berlin_synthetic dataset plus one demo project per mode
uv run umosim demo

# Run the ride-hailing demo project
uv run umosim run ridehailing_demo
```

> With the virtual environment activated (`source .venv/bin/activate`), you can drop the
> `uv run` prefix and call `umosim` directly.

Available subcommands:

| Command | Description |
| --- | --- |
| `demo` | Generate a synthetic demo (`berlin_synthetic` dataset + one project per mode). |
| `new-dataset` | Create a dataset: `bounding_box.geojson` + synthetic `demand.parquet`. |
| `new-project` | Scaffold project files against an existing dataset. |
| `run <name>` | Run a project from `data/projects/`. |
| `doctor` | Report orphan or malformed datasets and projects. |
| `clean-demos` | Remove demo and test datasets/projects. |
| `clean-logs` | Prune simulation output logs, keeping the newest entries. |

Run `uv run umosim <command> -h` for additional help.

Useful flags for `run`:

```bash
# Verbose console/file logging (-v = --log-level DEBUG, -q for near-silent), this overrules the config.toml
uv run umosim run ridehailing_demo --verbose

# Live visualization dashboard (requires the viz extra: uv sync --extra viz)
uv run umosim run ridehailing_demo --viz
```

## Simulation components

The simulation supports three types of mobility services:

- **Public transport** (currently not working)
- **Ride-hailing fleet** (autonomous vehicles and human-driven cars)
- **Shared mobility fleet** (cars, scooters, kickscooters, and bikes)

Simulations are organized into **datasets** (`data/datasets/<name>/`) holding the input
data (bounding box, demand), and **projects** (`data/projects/<name>/`) holding the
scenario configuration:

### `config.toml`

Foundational simulation settings:

- **Experiment management**: start and end times, and random seeds.
- **World resolution**: spatial, temporal, and daily resolution.
- **Paths**: dataset directory and output locations.
- **Logging**: configurable log levels for different simulation components.

### `operators.py`

Configuration of service operators:

- **Fleet configuration**: number and types of vehicles, their characteristics (e.g.,
  speed, capacity, energy consumption).
- **Charging infrastructure**: location, power, and capacity of charging stations.
- **Operations management**: pricing, pickup distance constraints, and recharging
  thresholds.
- **Search & allocation engines**: strategies for matching users with vehicles.

### `population.py`

Definition of the simulated population:

- **Population segments**: proportions of different user groups, totals are determined by the demand file.
- **User behavior**: maximum waiting times, walking speeds, and choice models for selecting transportation modes.

### `run.py`

Entry point that wires the project configuration together and starts the simulation (invoked by `umosim run <name>` or directly). Additional pre-, or post-simulation code goes here.

The [configuration guide](docs/configuration.md) explains how a run loads these files and lists every config field.

## Using this project for your own research

If you want to build your own experiments on top of the simulation without contributing
back, fork the repository and work directly on your fork:

- Create your own scenarios with `uv run umosim new-dataset` and `uv run umosim new-project`.
  Everything under `data/datasets/` and `data/projects/` is gitignored, so your scenarios
  and input data never conflict with upstream changes.
- To version your own scenarios, either force-add them (`git add -f data/projects/<name>`)
  or adjust the `.gitignore` files in your fork.
- Keep your fork up to date by adding this repository as a remote:

  ```bash
  git remote add upstream https://github.com/IS3UniCologne/urban-mobility-simulation.git
  ```

  For a stable base, pull in [tagged releases](https://github.com/IS3UniCologne/urban-mobility-simulation/releases)
  as they are published:

  ```bash
  git fetch upstream --tags
  git merge v0.1.0  # or whichever release you want to move to
  ```

  If you prefer the latest development state instead, merge `develop` periodically. Don't complain if something breaks :)

  ```bash
  git fetch upstream
  git merge upstream/develop
  ```

- The commit conventions and CI checks described in [CONTRIBUTING.md](CONTRIBUTING.md)
  only apply to pull requests against this repository, in your own fork you are free to work however you like.

If your work produces improvements that could be generally useful (bug fixes, new
operators, performance work), we would be happy to receive them back, see below.
If you want to share the research in which you have used this project, see [Research](research.md).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the development
setup, workflow, and code standards.
