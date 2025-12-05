from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    RideHailingAllocationEngineConfig,
    RideHailingFleetConfig,
    RideHailingMPChargingOperationsConfig,
    RideHailingOperatorConfig,
    RideHailingSearchEngineConfig,
    RideHailingVehicleConfig,
    SharedChargingAuctionConfig,
)
from simulation.helper.configuration.enums import (
    AutonomyType,
    PropulsionType,
    VehicleType,
)
from simulation.operator.operations_management.algorithms.charging_station_allocation import (
    DowntimeMinWithoutLookahead,
)

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
    INITIAL_CHARGE_RATIO=0.50,
)

charging_infrastructure_1 = ChargingInfrastructureConfig(
    # If lists are provided, heterogeneous charging stations are possible
    # If single value lists are provided, we assume the same values for all locations
    # Number of charging stations can be used to cut down on the number of charging stations without modifying the locations
    NUMBER_OF_CHARGING_STATIONS=9,
    ##### chicago AAMAS
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
    CHARGING_STATION_CAPACITY=[5],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[5],
    AUCTION_CONFIG=SharedChargingAuctionConfig(
        AUCTION_START=10,
        AUCTION_END=20_160,
        AUCTION_INTERVAL=10,
        TIMESLOT_DURATION=90,
        AUCTION_LOOKAHEAD=20,
    ),
)

charging_infrastructure_2 = ChargingInfrastructureConfig(
    # If lists are provided, heterogeneous charging stations are possible
    # If single value lists are provided, we assume the same values for all locations
    # Number of charging stations can be used to cut down on the number of charging stations without modifying the locations
    NUMBER_OF_CHARGING_STATIONS=9,
    ##### chicago AAMAS
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
    CHARGING_STATION_CAPACITY=[5],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[5],
    AUCTION_CONFIG=SharedChargingAuctionConfig(
        AUCTION_START=10,
        AUCTION_END=20_160,
        AUCTION_INTERVAL=10,
        TIMESLOT_DURATION=90,
        AUCTION_LOOKAHEAD=20,
    ),
)


fleet_1 = RideHailingFleetConfig(
    VEHICLES={rh_car_autonomous: 500},
    RH_AVAILABILITY=[
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
    ],
)

# When vehicles drop below RECHARGE_THRESHOLD => cannot be rented and needs to be recharged
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

operator_1 = RideHailingOperatorConfig(
    FLEET_CONFIG=fleet_1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingMPChargingOperationsConfig(
        CHARGING_ALGORITHM_TYPE=DowntimeMinWithoutLookahead,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOW_QUEUE=True,
        LOW_SOC_PENALTY=500_000,
        DRIVER_PAYMENT_SHARE=0.75,
        AV_PRICE_REDUCTION=0.9,
        MAX_PICKUP_DISTANCE=10000,
        PRICE_ENTERING=2,
        PRICE_PER_MINUTE=0.35,
        PRICE_PER_KM=1.3,
        MINIMUM_PRICE=5,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(),
)

operator_2 = RideHailingOperatorConfig(
    FLEET_CONFIG=fleet_1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_2,
    OPERATIONS_CONFIG=RideHailingMPChargingOperationsConfig(
        CHARGING_ALGORITHM_TYPE=DowntimeMinWithoutLookahead,
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOW_QUEUE=True,
        LOW_SOC_PENALTY=500_000,
        DRIVER_PAYMENT_SHARE=0.75,
        AV_PRICE_REDUCTION=0.9,
        MAX_PICKUP_DISTANCE=10000,
        PRICE_ENTERING=2,
        PRICE_PER_MINUTE=0.35,
        PRICE_PER_KM=1.3,
        MINIMUM_PRICE=5,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(),
)
