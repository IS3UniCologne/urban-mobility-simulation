import numpy as np

from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    OperatorConfig,
    RideHailingAllocationEngineConfig,
    RideHailingFleetConfig,
    RideHailingSearchEngineConfig,
    RideHailingSharedChargingOperationsConfig,
    RideHailingVehicleConfig,
    SharedChargingAuctionConfig,
)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.operations_management.ridehailing_shared_charging_operations import (
    RideHailingSharedChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.world.markets.shared_charging_auction import SharedChargingAuction

# initial_soc_distribution_rng = RandomManager().get_rng("SOC_DISTRIBUTION")

rh_car_autonomous = RideHailingVehicleConfig(
    VELOCITY_KMH=32.16,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.AUTONOMOUS,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    ENERGY_CAPACITY=50.0,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    CHARGING_COST_PER_KWH=0.43,
    ENERGY_RESERVE_RATIO=0.05,
    PRICE_PER_MIN=0.35,
    DAILY_TOTAL_COST=29.0,
    COST_PER_KM=0.45,
    PRICE_PER_KM=1.3,
    # INITIAL_CHARGE_RATIO=min(
    #     max(0.1, initial_soc_distribution_rng.normal(loc=0.5, scale=0.2), 0.9)
    # ),
    INITIAL_CHARGE_RATIO=0.5,
)
RH_AVAILABILITY = np.zeros(24)

fleet = RideHailingFleetConfig(
    FLEET_TYPE=RideHailingFleet,
    VEHICLES={rh_car_autonomous: 500},
    RH_AVAILABILITY=RH_AVAILABILITY,
)

charging_infrastructure_1 = ChargingInfrastructureConfig(
    # If lists are provided, heterogeneous charging stations are possible
    # If single value lists are provided, we assume the same values for all locations
    # Number of charging stations can be used to cut down on the number of charging stations without modifying the locations
    NUMBER_OF_CHARGING_STATIONS=9,
    ##### chicago
    LOCATIONS=[
        "872664c1effffff",
        "872664c1affffff",
        "87275934effffff",
        "872664ca9ffffff",
        "872664521ffffff",
        "872664cf5ffffff",
        "872664cacffffff",
        "872664c10ffffff",
        "872664d89ffffff",
    ],
    # If single value, all stations have the same power
    CHARGING_STATION_POWER=[22.0],
    # How many plugs / slots a charging station has. If single value, all stations have the same capacity
    CHARGING_STATION_CAPACITY=[10],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[0],
    AUCTION_CONFIG=SharedChargingAuctionConfig(
        AUCTION_TYPE=SharedChargingAuction,
        AUCTION_START=10,
        AUCTION_END=20_160,
        AUCTION_INTERVAL=10,
        TIMESLOT_DURATION=90,
        AUCTION_LOOKAHEAD=20,
    ),
)
DEFAULT_RECHARGE_THRESHOLD = [
    0.32,
    0.36,
    0.40,
    0.44,
    0.42,
    0.40,
    0.38,
    0.36,
    0.36,
    0.34,
    0.32,
    0.32,
    0.32,
    0.32,
    0.32,
    0.30,
    0.28,
    0.26,
    0.24,
    0.24,
    0.22,
    0.24,
    0.26,
    0.28,
]

operator_1 = OperatorConfig(
    FLEET_CONFIG=fleet,
    OPERATOR_TYPE=RideHailingOperator,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    # OPERATIONS_CONFIG=OperationsConfig(
    #     OPERATIONS_START=10,
    #     OPERATIONS_DURATION=50,
    #     TIME_BETWEEN_OPERATIONS=10,
    #     RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
    #     VEHICLE_RELOCATION_VELOCITY=32.16,
    #     ALLOW_QUEUE=True,
    # ),
    OPERATIONS_CONFIG=RideHailingSharedChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingSharedChargingOperations,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOWED_QUEUE_SIZE=0,
        AV_PRICE_REDUCTION=1.0,
        MAX_PICKUP_DISTANCE=5000,
        PRICE_ENTERING=2.0,  # doesnt apply
        PRICE_PER_MINUTE=0.35,  # TODO: should be in the car?
        PRICE_PER_KM=1.3,  # TODO: should be in the car?
        MINIMUM_PRICE=5.0,  # doesn't apply?
        DRIVER_PAYMENT_SHARE=0.75,  # doesn't apply
        BID_DEFAULT=1,
        BID_DECAY=0.0001,
        RANDOM_OVERBIDDING=True,
        OVERBID_PROB=0.3,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)

operator_2 = OperatorConfig(
    FLEET_CONFIG=fleet,
    OPERATOR_TYPE=RideHailingOperator,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingSharedChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingSharedChargingOperations,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOWED_QUEUE_SIZE=0,
        AV_PRICE_REDUCTION=1.0,
        MAX_PICKUP_DISTANCE=10000,
        PRICE_ENTERING=2.0,  # doesnt apply
        PRICE_PER_MINUTE=0.35,  # TODO: should be in the car?
        PRICE_PER_KM=1.3,  # TODO: should be in the car?
        MINIMUM_PRICE=5.0,  # doesn't apply?
        DRIVER_PAYMENT_SHARE=0.75,  # doesn't apply
        BID_DEFAULT=1,
        BID_DECAY=0.0001,
        RANDOM_OVERBIDDING=True,
        OVERBID_PROB=0.3,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)
