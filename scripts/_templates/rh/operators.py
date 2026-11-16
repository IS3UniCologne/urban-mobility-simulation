"""Operator configuration."""

from __future__ import annotations

# SCAFFOLD:IMPORTS_START
from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    RideHailingAllocationEngineConfig,
    RideHailingBaseChargingOperationsConfig,
    RideHailingFleetConfig,
    RideHailingOperatorConfig,
    RideHailingSearchEngineConfig,
    RideHailingVehicleConfig,
    VehicleCostConfig,
)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine

# SCAFFOLD:IMPORTS_END


# Shared building blocks. Anything you want several operators to reuse (vehicle
# definitions, the availability curve, station locations) lives here as a named
# value; reference it from the operators below.
# SCAFFOLD:VEHICLE_DEFS_START
rh_car_autonomous = RideHailingVehicleConfig(
    VELOCITY_KMH=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.AUTONOMOUS,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    ENERGY_CAPACITY=50.0,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    ENERGY_RESERVE_RATIO=0.05,
    PRICE_PER_MIN=0.35,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_RATIO=0.50,
    COST_CONFIG=VehicleCostConfig(PER_KM=0.45, DAILY=29.0),
)

rh_car_human = RideHailingVehicleConfig(
    VELOCITY_KMH=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    ENERGY_CAPACITY=50.0,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    ENERGY_RESERVE_RATIO=0.05,
    PRICE_PER_MIN=0.35,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_RATIO=0.50,
    COST_CONFIG=VehicleCostConfig(PER_KM=0.45, DAILY=29.0, DRIVER_PAYMENT_SHARE=0.75),
)

RH_AVAILABILITY = [
    0.084238,
    0.058132,
    0.035717,
    0.024728,
    0.027128,
    0.043823,
    0.078576,
    0.128257,
    0.176352,
    0.214981,
    0.241122,
    0.255754,
    0.275117,
    0.293370,
    0.306846,
    0.318127,
    0.323715,
    0.326972,
    0.318448,
    0.290888,
    0.242649,
    0.187925,
    0.142973,
    0.111224,
]

DEFAULT_RECHARGE_THRESHOLD = [
    0.40,
    0.45,
    0.50,
    0.55,
    0.52,
    0.50,
    0.48,
    0.45,
    0.45,
    0.42,
    0.40,
    0.40,
    0.40,
    0.40,
    0.40,
    0.38,
    0.35,
    0.32,
    0.30,
    0.30,
    0.27,
    0.30,
    0.32,
    0.35,
]

RH_STATION_HEXES = ["872830828ffffff"]  # SCAFFOLD:STATION_HEXES
# SCAFFOLD:VEHICLE_DEFS_END


# One operator per list entry. Add an operator by copying an entry; remove one by
# deleting it. To run several operators off a shared fleet, pull the fleet out
# into a named value above and reference it here.
OPERATORS = [
    # SCAFFOLD:OPERATOR_START
    RideHailingOperatorConfig(
        FLEET_CONFIG=RideHailingFleetConfig(
            FLEET_TYPE=RideHailingFleet,
            VEHICLES={rh_car_autonomous: 125, rh_car_human: 125},
            RH_AVAILABILITY=RH_AVAILABILITY,
            SHIFT_CHECK_INTERVAL_MIN=15,
        ),
        CHARGING_INFRASTRUCTURE=ChargingInfrastructureConfig(
            NUMBER_OF_CHARGING_STATIONS=len(RH_STATION_HEXES),
            LOCATIONS=RH_STATION_HEXES,
            CHARGING_STATION_POWER=[50.0],
            CHARGING_STATION_CAPACITY=[20],
            CHARGING_STATION_QUEUE_SIZE=[99],
            CHARGING_STATION_PRICE_PROFILE=[0.43] * 24,
        ),
        OPERATIONS_CONFIG=RideHailingBaseChargingOperationsConfig(
            OPERATIONS_TYPE=RideHailingBaseChargingOperations,
            OPERATIONS_START=15,
            OPERATIONS_DURATION=50,
            TIME_BETWEEN_OPERATIONS=15,
            RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
            VEHICLE_RELOCATION_VELOCITY=9.54,
        ),
        SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
            SEARCH_ENGINE_TYPE=RideHailingSearchEngine,
            AV_PRICE_REDUCTION=0.90,
            MAX_PICKUP_DISTANCE=10000,
            ARRIVAL_LOOKAHEAD_MIN=5,
            PRICE_ENTERING=2.0,
            PRICE_PER_MINUTE=0.35,
            PRICE_PER_KM=1.3,
            MINIMUM_PRICE=5.0,
        ),
        ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
            VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
        ),
    )
    # SCAFFOLD:OPERATOR_END
]
