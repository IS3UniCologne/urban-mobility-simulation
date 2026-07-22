"""Shared utilities for end-to-end tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, cast

from scripts._cli.orchestrators import generate_demand, init_dataset
from scripts._cli.paths import project_dataset_dir
from scripts._cli.templates import load_preset_demand_params, load_presets
from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation

_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_ROOT = _ROOT / "tests" / "configurations"
DEMAND_SEED = 42


def _dataset_name(config_dir: Path) -> str:
    return project_dataset_dir(config_dir).name


def build_e2e_datasets(root: Path = _ROOT) -> None:
    """Regenerate every scenario dataset referenced by the e2e configs."""
    presets = load_presets()
    required = {
        _dataset_name(d)
        for d in _CONFIG_ROOT.iterdir()
        if d.is_dir() and (d / "config.toml").exists()
    }
    for name in sorted(required):
        if name not in presets:
            raise ValueError(
                f"Dataset '{name}' referenced by an e2e config has no preset in "
                f"scripts/_presets.toml."
            )
        dataset_dir = root / "data" / "datasets" / name
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        init_dataset(name, presets[name], root=root)
        generate_demand(
            name, root=root, seed=DEMAND_SEED, params=load_preset_demand_params(name)
        )


def run_simulation_and_extract_metrics(config_path: str) -> dict[str, Any]:
    """
    Run simulation for a given config path and extract relevant metrics.

    Parameters
    ----------
    config_path : str
        Path to the configuration directory.

    Returns
    -------
    dict[str, Any]
        A dictionary containing the structured metrics (operator, user, fleet).
    """
    # Initialize configuration
    config = Configuration(config_path)

    # Initialize simulation
    simulation = Simulation(config)

    # Run simulation
    simulation.run_simulation()

    # Extract metrics
    metrics = simulation.metrics.operator_metrics.to_dict()
    user_metrics = simulation.metrics.user_metrics.to_dict()
    fleet_metrics = simulation.metrics.fleet_metrics.to_dict()

    aggregate = cast("dict[str, Any]", metrics["aggregate"])
    user_aggregate = cast("dict[str, Any]", user_metrics["aggregate"])

    # Filter relevant metrics to avoid noise
    relevant_operator_metrics = {
        "total_revenue": aggregate["total_revenue"],
        "total_transaction_count": aggregate["total_transaction_count"],
        "total_fulfilled_trips": aggregate["total_fulfilled_trips"],
        "total_missed_allocations": aggregate["total_missed_allocations"],
        "total_missed_revenue": aggregate["total_missed_revenue"],
        "total_trip_duration": aggregate["total_trip_duration"],
        "total_trip_distance": aggregate["total_trip_distance"],
        "total_energy_consumption": aggregate["total_energy_consumption"],
        "total_cost": aggregate["total_cost"],
        "profit": aggregate["profit"],
        "cost_vehicle_distance": aggregate["cost_vehicle_distance"],
        "cost_vehicle_relocation_distance": aggregate[
            "cost_vehicle_relocation_distance"
        ],
        "cost_vehicle_charging": aggregate["cost_vehicle_charging"],
        "cost_vehicle_time_online": aggregate["cost_vehicle_time_online"],
        "cost_vehicle_time_offline": aggregate["cost_vehicle_time_offline"],
        "cost_driver_payment": aggregate["cost_driver_payment"],
        "cost_worker_time": aggregate["cost_worker_time"],
    }

    relevant_user_metrics = {
        "total_trip_requests": user_aggregate["total_trip_requests"],
        "total_fulfilled_trips": user_aggregate["total_fulfilled_trips"],
        "total_missed_trips": user_aggregate["total_missed_trips"],
        "fulfillment_rate": user_aggregate["fulfillment_rate"],
        "total_revenue": user_aggregate["total_revenue"],
        "average_price_paid": user_aggregate["average_price_paid"],
        "total_search_time": user_aggregate["total_search_time"],
        "average_search_time": user_aggregate["average_search_time"],
        "average_wait_time": user_aggregate["average_wait_time"],
        "total_trip_duration": user_aggregate["total_trip_duration"],
        "average_trip_duration": user_aggregate["average_trip_duration"],
        "total_energy_consumed": user_aggregate["total_energy_consumed"],
        "average_energy_consumed": user_aggregate["average_energy_consumed"],
    }

    relevant_fleet_metrics = {}
    for fleet_id, fleet_data in fleet_metrics.items():
        fleet_data = cast("dict[str, Any]", fleet_data)
        relevant_fleet_metrics[fleet_id] = {
            "standby_vehicles": fleet_data["standby_vehicles"],
            "charging_vehicles": fleet_data["charging_vehicles"],
            "transporting_vehicles": fleet_data["transporting_vehicles"],
            "avg_state_of_charge": fleet_data["avg_state_of_charge"],
        }

    return {
        "operator_metrics": relevant_operator_metrics,
        "user_metrics": relevant_user_metrics,
        "fleet_metrics": relevant_fleet_metrics,
    }
