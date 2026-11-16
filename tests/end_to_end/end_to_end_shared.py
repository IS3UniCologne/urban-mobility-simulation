"""Shared utilities for end-to-end tests."""

from __future__ import annotations

from typing import Any, cast

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation
from tests.datasets import rebuild_datasets


def build_e2e_datasets() -> None:
    """Regenerate every dataset the test projects reference.

    benchmarks/compare.py calls this on both sides of a comparison, so it stays here
    while a base commit can predate tests/datasets.py.
    """
    rebuild_datasets()


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
        "cost_vehicle_holding": aggregate["cost_vehicle_holding"],
        "cost_driver_payment": aggregate["cost_driver_payment"],
        "cost_worker_labor": aggregate["cost_worker_labor"],
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
