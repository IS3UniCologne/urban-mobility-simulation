from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    RideHailingAllocationEngineConfig,
    RideHailingFleetConfig,
    RideHailingGreedyChargingOperationsConfig,
    RideHailingOperatorConfig,
    RideHailingSearchEngineConfig,
    RideHailingVehicleConfig,
    SharedChargingAuctionConfig,
    RideHailingSharedChargingOperationsConfig,
    ChargingStrategy,

)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.operations_management.ridehailing_shared_charging_operations import (
    RideHailingSharedChargingOperations,
)

from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.world.markets.shared_charging_auction import SharedChargingAuction
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine

rh_car_autonomous = RideHailingVehicleConfig(
    VELOCITY_KMH=9.54,
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
    INITIAL_CHARGE_RATIO=0.50,
)
rh_car_human = RideHailingVehicleConfig(
    VELOCITY_KMH=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    ENERGY_CAPACITY=50.0,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    CHARGING_COST_PER_KWH=0.43,
    ENERGY_RESERVE_RATIO=0.05,
    PRICE_PER_MIN=0.35,
    DAILY_TOTAL_COST=29.0,
    COST_PER_KM=0.45,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_RATIO=0.50,
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

fleet1 = RideHailingFleetConfig(
    FLEET_TYPE=RideHailingFleet,
    VEHICLES={rh_car_autonomous: 10,},
    RH_AVAILABILITY=RH_AVAILABILITY,
)

charging_infrastructure_1 = ChargingInfrastructureConfig(
    # If lists are provided, heterogeneous charging stations are possible
    # If single value lists are provided, we assume the same values for all locations
    # Number of charging stations can be used to cut down on the number of charging stations without modifying the locations
    NUMBER_OF_CHARGING_STATIONS=5,
    ##### berlin
    LOCATIONS=[
        '871f18b6effffff',
        '871f1d4f1ffffff',
        '871f1d413ffffff',
        '871f18863ffffff',
        '871f1d7a6ffffff'
         ],
    # If single value, all stations have the same power
    # Analysis of electric vehicle charging station usage and profitability in Germany based on empirical data -> Analysis of electric vehicle charging station usage and profitability in Germany based on empirical data / https://www.iea.org/reports/global-ev-outlook-2025/electric-vehicle-charging
    # Representative empirical, real-world charging station usage characteristics and data in Germany -> https://www.sciencedirect.com/science/article/pii/S2590116820300369
    CHARGING_STATION_POWER=[50.0],
    # How many plugs / slots a charging station has. If single value, all stations have the same capacity
    CHARGING_STATION_CAPACITY=[1],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[1],

    AUCTION_CONFIG=SharedChargingAuctionConfig(
        AUCTION_TYPE=SharedChargingAuction,
        AUCTION_START=0,
        AUCTION_END=1440,
        AUCTION_INTERVAL=60,
        TIMESLOT_DURATION=60,
        AUCTION_LOOKAHEAD=60,
    ),
)

# When vehicles drop below RECHARGE_THRESHOLD => cannot be rented and needs to be recharged
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

operator_1 = RideHailingOperatorConfig(
    FLEET_CONFIG=fleet1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingSharedChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingSharedChargingOperations,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=10,
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
        STRATEGY=ChargingStrategy.RL,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)
operator_2 = RideHailingOperatorConfig(
    FLEET_CONFIG=fleet1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingSharedChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingSharedChargingOperations,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=10,
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
        STRATEGY=ChargingStrategy.RL,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)