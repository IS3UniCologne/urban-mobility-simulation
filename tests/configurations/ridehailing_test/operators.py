from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    RideHailingAllocationEngineConfig,
    RideHailingBaseChargingOperationsConfig,
    RideHailingFleetConfig,
    RideHailingOperatorConfig,
    RideHailingSearchEngineConfig,
    RideHailingVehicleConfig,
)
from simulation.helper.configuration.enums import (
    AutonomyType,
    PropulsionType,
    VehicleType,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine

rh_car_autonomous = RideHailingVehicleConfig(
    VELOCITY=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.AUTONOMOUS,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    MAX_STATE_OF_CHARGE=50.0,
    ENERGY_CONSUMPTION=0.20,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.3,
    CHARGING_COST_PER_KWH=0.43,
    EMERGENCY_SOC_BUFFER=0.05,
    PRICE_PER_MIN=0.35,
    DAILY_TOTAL_COST=29.0,
    COST_PER_KM=0.45,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_PERCENT=0.50,
)
rh_car_human = RideHailingVehicleConfig(
    VELOCITY=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    MAX_STATE_OF_CHARGE=50.0,
    ENERGY_CONSUMPTION=0.20,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.3,
    CHARGING_COST_PER_KWH=0.43,
    EMERGENCY_SOC_BUFFER=0.05,
    PRICE_PER_MIN=0.35,
    DAILY_TOTAL_COST=29.0,
    COST_PER_KM=0.45,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_PERCENT=0.50,
)
rh_car_human_2 = RideHailingVehicleConfig(
    VELOCITY=9.54,
    MAX_AVAILABLE_SEATS=4,
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    MAX_STATE_OF_CHARGE=50.0,
    ENERGY_CONSUMPTION=0.20,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.3,
    CHARGING_COST_PER_KWH=0.43,
    EMERGENCY_SOC_BUFFER=0.05,
    PRICE_PER_MIN=0.35,
    DAILY_TOTAL_COST=29.0,
    COST_PER_KM=0.45,
    PRICE_PER_KM=1.3,
    INITIAL_CHARGE_PERCENT=0.50,
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
    VEHICLES={rh_car_human: 12, rh_car_human_2: 12, rh_car_autonomous: 25},
    RH_AVAILABILITY=RH_AVAILABILITY,
)


charging_infrastructure_1 = ChargingInfrastructureConfig(
    NUMBER_OF_CHARGING_STATIONS=16,
    LOCATIONS=[
        "871f18869ffffff",
        "871f18b0dffffff",
        "871f18b23ffffff",
        "871f18b26ffffff",
        "871f18b35ffffff",
        "871f1d483ffffff",
        "871f1d489ffffff",
        "871f1d48bffffff",
        "871f1d48effffff",
        "871f1d49cffffff",
        "871f1d4aaffffff",
        "871f1d4b3ffffff",
        "871f1d4d2ffffff",
        "871f1d4d3ffffff",
        "871f1d4f3ffffff",
        "871f1d4f6ffffff",
    ],
    CHARGING_STATION_POWER=[50.0],
    CHARGING_STATION_CAPACITY=[20],
    CHARGING_STATION_QUEUE_SIZE=[99],
)


operator_1 = RideHailingOperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    FLEET_CONFIG=fleet1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingBaseChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingBaseChargingOperations,
        OPERATIONS_START=15,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=15,
        RECHARGE_THRESHOLD=[
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
        ],
        VEHICLE_RELOCATION_VELOCITY=9.54,
        AV_PRICE_REDUCTION=0.90,
        MAX_PICKUP_DISTANCE=10000,
        PRICE_ENTERING=2.0,
        PRICE_PER_MINUTE=0.35,
        PRICE_PER_KM=1.3,
        MINIMUM_PRICE=5.0,
        DISCOUNT_RATE=0.0,
        DRIVER_PAYMENT_SHARE=0.75,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)

operator_2 = RideHailingOperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    FLEET_CONFIG=fleet1,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=RideHailingBaseChargingOperationsConfig(
        OPERATIONS_TYPE=RideHailingBaseChargingOperations,
        OPERATIONS_START=15,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=15,
        RECHARGE_THRESHOLD=[
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
        ],
        VEHICLE_RELOCATION_VELOCITY=9.54,
        AV_PRICE_REDUCTION=0.90,
        MAX_PICKUP_DISTANCE=10000,
        PRICE_ENTERING=2.0,
        PRICE_PER_MINUTE=0.35,
        PRICE_PER_KM=1.3,
        MINIMUM_PRICE=5.0,
        DISCOUNT_RATE=0.0,
        DRIVER_PAYMENT_SHARE=0.75,
    ),
    SEARCH_ENGINE_CONFIG=RideHailingSearchEngineConfig(
        SEARCH_ENGINE_TYPE=RideHailingSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=RideHailingAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=RideHailingAllocationEngine
    ),
)
