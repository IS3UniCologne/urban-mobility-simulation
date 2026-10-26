"""Operator configuration."""

from __future__ import annotations

# SCAFFOLD:IMPORTS_START
from rl.adapters import BrokeredAdmissionSearchEngine
from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    RideHailingAllocationEngineConfig,
    RideHailingFleetConfig,
    RideHailingGreedyChargingOperationsConfig,
    RideHailingOperatorConfig,
    RideHailingSearchEngineConfig,
    RideHailingVehicleConfig,
    VehicleCostConfig,
)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.operations_management.ridehailing_greedy_charging_operations import (
    RideHailingGreedyChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet

# SCAFFOLD:IMPORTS_END


# One autonomous electric fleet whose ride requests a learning agent offers or
# defers, one decision per search. Demand outruns the fleet and the pickup radius
# is wide, so a far pickup leg costs an hour of deadhead that a nearer request
# could have used. Charging is generous so that it stays out of the way.
# SCAFFOLD:VEHICLE_DEFS_START
admission_car_autonomous = RideHailingVehicleConfig(
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
    COST_CONFIG=VehicleCostConfig(PER_KM=0.45, CHARGING_PER_KWH=0.43, DAILY=29.0),
)

ADMISSION_AVAILABILITY = [
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

ADMISSION_RECHARGE_THRESHOLD = [
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

ADMISSION_STATION_HEXES = ["872830828ffffff"]  # SCAFFOLD:STATION_HEXES
# SCAFFOLD:VEHICLE_DEFS_END


# The learning agent settles exactly one operator, so keep this list at one entry.
OPERATORS = [
    # SCAFFOLD:OPERATOR_START
    RideHailingOperatorConfig(
        FLEET_CONFIG=RideHailingFleetConfig(
            FLEET_TYPE=RideHailingFleet,
            VEHICLES={admission_car_autonomous: 50},
            RH_AVAILABILITY=ADMISSION_AVAILABILITY,
        ),
        CHARGING_INFRASTRUCTURE=ChargingInfrastructureConfig(
            NUMBER_OF_CHARGING_STATIONS=len(ADMISSION_STATION_HEXES),
            LOCATIONS=ADMISSION_STATION_HEXES,
            CHARGING_STATION_POWER=[50.0],
            CHARGING_STATION_CAPACITY=[20],
            CHARGING_STATION_QUEUE_SIZE=[99],
            CHARGING_STATION_PRICE_PER_KWH=[0.43],
        ),
        OPERATIONS_CONFIG=RideHailingGreedyChargingOperationsConfig(
            OPERATIONS_TYPE=RideHailingGreedyChargingOperations,
            OPERATIONS_START=15,
            OPERATIONS_DURATION=50,
            TIME_BETWEEN_OPERATIONS=15,
            RECHARGE_THRESHOLD=ADMISSION_RECHARGE_THRESHOLD,
            VEHICLE_RELOCATION_VELOCITY=9.54,
        ),
        SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
            SEARCH_ENGINE_TYPE=BrokeredAdmissionSearchEngine,
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
