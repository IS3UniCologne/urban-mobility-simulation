# Configuration

A run reads two folders:

- **Dataset** (`data/datasets/<name>/`): input data for one area, created with `umosim new-dataset`.
- **Project** (`data/projects/<name>/`): the setup of one experiment on a dataset, created with `umosim new-project <name> --dataset <dataset>`.

Several projects can use the same dataset.
Git ignores both folders, so your projects and datasets stay out of the repository.

## How a run loads a project

1. `umosim run <name>` runs `data/projects/<name>/run.py` with `uv run`. You can also run that file directly.
2. `run.py` creates `Configuration(project_dir)`. It reads `config.toml` and imports `operators.py` and `population.py`.
3. `Simulation(config)` sets up the simulation and `run_simulation()` runs it until `END_TIME`.

## Project files

### `config.toml`

General settings: log levels, start and end time, random seeds, world resolution and paths.
`umosim new-project` writes it from this template:

```{literalinclude} ../scripts/_templates/config.toml
:language: toml
```

`__DATASET_NAME__` stands for the dataset passed with `--dataset`.

- Each table loads into one model of the [reference](#reference) below, e.g. `[WORLD]` into `WorldConfig`.
- Top-level table names ignore case. Keys and sub-tables such as `[RANDOM_MANAGER.COMPONENT_SEEDS]` must match the model's field names exactly.
- Unknown keys inside a table raise an error. A misspelled table name is ignored, so the run fails later when it needs that table.
- Tables are validated when the simulation first reads them, not when `Configuration` is created.
- `SPATIAL_RESOLUTION` and `TEMPORAL_RESOLUTION` in `[WORLD]` must match the dataset's demand file. The template always writes 7 and 4, so update them for a dataset created with other resolutions.
- Relative `DATASET_DIR` and `OUTPUT_FOLDER` paths resolve against the project folder.
- `umosim run <name> --log-level DEBUG` overrides `LOG_LEVEL` and `FILE_LOG_LEVEL` for one run.

### `operators.py`

The operators, each with its fleet, charging infrastructure, operations, search engine and allocation engine.
The file is plain Python, so several operators can share one vehicle definition or one list of station hexes.

- `Configuration` collects every `OperatorConfig` at module level, alone or inside a list or tuple. The templates put them in one `OPERATORS` list.
- Each collected `OperatorConfig` becomes one operator. An operator assigned to a variable and also listed in `OPERATORS` is collected twice.
- Names that start with an underscore are skipped, so `_shared = RideHailingOperatorConfig(...)` plus `OPERATORS = [_shared]` gives one operator.
- Pydantic validates a config when the file creates it, so an invalid value fails at import.
- A fleet takes its supply distribution from the first source that exists: its `SUPPLY_DISTRIBUTION_FILE` in the project folder, the dataset's `supply.parquet` or a distribution derived from the demand. The run stops at start if a `SUPPLY_DISTRIBUTION_FILE` is missing.
- `umosim new-project --operators rh sm` picks the starting templates: ride hailing (`rh`) and shared mobility (`sm`).

### `population.py`

The users and their behavior.

- The file defines exactly one `PopulationConfig`. None or several raise an error.
- Each `PopulationSegmentConfig` gives a `PROPORTION` of the users one `UserConfig`: walking speed, waiting and search limits and the choice model.
- The proportions must sum to 1.0. On Python 3.11 the check compares floats exactly for now, so proportions like 0.7, 0.2 and 0.1 fail.
- The number of users is random. Users arrive per hexagon with the Poisson rates of the demand file, from `START_TIME` to `END_TIME`.

### `run.py`

The entry point. Pre-run and post-run code goes here, e.g. extra plots or metric logs.

### Optional project files

- `demand_modifiers/*.geojson`: polygons with a `demandMultiplier` property. A modifier scales the arrival rate of every hexagon it covers. A multiplier of 0 removes that hexagon's demand. Files load in name order and where modifiers overlap the last one wins.

## Dataset files

- `demand.parquet` (required): the demand profile with arrival rates per hexagon and time bucket.
- `bounding_box.geojson`: the simulated area. `umosim new-project` needs it. A run infers the area when it is missing.
- `supply.parquet`: the supply distribution for fleets without their own file.
- `transit_timetable.parquet` and `transit_shapes.parquet`: public transport input. No run reads them at the moment, since public transport does not work yet.
- `.cache/`: derived data the simulation computes once and reuses.

## Reference

```{eval-rst}
.. automodule:: simulation.helper.configuration.configuration
```
