"""Operator configuration."""

from __future__ import annotations

# SCAFFOLD:IMPORTS_START
from simulation.helper.configuration.configuration import (
    IntegratedSharedMobilityOperationsConfig,
    SharedVehicleAllocationEngineConfig,
    SharedVehicleConfig,
    SharedVehicleFleetConfig,
    SharedVehicleOperatorConfig,
    SharedVehicleSearchEngineConfig,
)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.shared_mobility_operator import SharedMobilityOperator

# SCAFFOLD:IMPORTS_END


# Shared building blocks. Anything you want several operators to reuse (vehicle
# definitions, station locations) lives here as a named value; reference it from
# the operators below.
# SCAFFOLD:VEHICLE_DEFS_START
sv_car = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.INTERNAL_COMBUSTION,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=3,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=29.86,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    INITIAL_CHARGE_RATIO=0.50,
    KG_CO2_PER_KM=0.236,
    MAX_AVAILABLE_SEATS=4,
    ENERGY_CAPACITY=50.0,
    PRICE_PER_MIN=0.35,
    VELOCITY_KMH=9.54,
    WALKING_DISTANCE=500,
)

sv_scooter = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.SCOOTER,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=2,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=7.66,
    ENERGY_CONSUMPTION_PER_KM=0.048,
    INITIAL_CHARGE_RATIO=0.50,
    KG_CO2_PER_KM=0.051,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=4.8,
    PRICE_PER_MIN=0.23,
    VELOCITY_KMH=8.04,
    WALKING_DISTANCE=350,
)

sv_kick_scooter = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.KICK_SCOOTER,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=1,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=11.51,
    ENERGY_CONSUMPTION_PER_KM=0.0072,
    INITIAL_CHARGE_RATIO=0.5,
    KG_CO2_PER_KM=0.105,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=0.288,
    PRICE_PER_MIN=0.19,
    PRICE_PER_TRIP=1.0,
    VELOCITY_KMH=2.82,
    WALKING_DISTANCE=200,
)

sv_bike = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.BIKE,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.HUMAN_POWERED,
    CONVENIENCE=1,
    COST_PER_KM=0.10,
    DAILY_TOTAL_COST=11.51,
    ENERGY_CONSUMPTION_PER_KM=0.0,
    INITIAL_CHARGE_RATIO=1.0,
    KG_CO2_PER_KM=0.046,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=1.0,
    PRICE_PER_MIN=0.08,
    VELOCITY_KMH=2.82,
    WALKING_DISTANCE=200,
)

SM_STATION_HEXES = ["872830828ffffff"]  # SCAFFOLD:STATION_HEXES
# SCAFFOLD:VEHICLE_DEFS_END


# One operator per list entry. Add an operator by copying an entry; remove one by
# deleting it. To run several operators off a shared fleet, pull the fleet out
# into a named value above and reference it here.
OPERATORS = [
    # SCAFFOLD:OPERATOR_START
    SharedVehicleOperatorConfig(
        OPERATOR_TYPE=SharedMobilityOperator,
        FLEET_CONFIG=SharedVehicleFleetConfig(
            VEHICLES={sv_car: 100, sv_scooter: 100, sv_kick_scooter: 150, sv_bike: 50}
        ),
        SEARCH_ENGINE_CONFIG=SharedVehicleSearchEngineConfig(),
        ALLOCATION_ENGINE_CONFIG=SharedVehicleAllocationEngineConfig(),
        OPERATIONS_CONFIG=IntegratedSharedMobilityOperationsConfig(
            CHARGING_STATION_POWER=50.0,
            NUMBER_OF_BASE_REGIONS=len(SM_STATION_HEXES),
            BASE_CAPACITY=100000,
            BASE_REGIONS=SM_STATION_HEXES,
            OPERATIONS_START=15,
            OPERATIONS_DURATION=50,
            TIME_BETWEEN_OPERATIONS=15,
            RECHARGE_THRESHOLD=0.3,
            VEHICLE_RELOCATION_VELOCITY=9.54,
            NUMBER_OF_SERVICE_WORKERS=20,
        ),
    )
    # SCAFFOLD:OPERATOR_END
]
