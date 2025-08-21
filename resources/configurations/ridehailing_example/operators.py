from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    OperationsConfig,
    OperatorConfig,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator

charging_infrastructure_1 = ChargingInfrastructureConfig(
    # If lists are provided, heterogeneous charging stations are possible
    # If single value lists are provided, we assume the same values for all locations
    # Number of charging stations can be used to cut down on the number of charging stations without modifying the locations
    NUMBER_OF_CHARGING_STATIONS=16,
    ##### berlin
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
    # If single value, all stations have the same power
    # Analysis of electric vehicle charging station usage and profitability in Germany based on empirical data -> Analysis of electric vehicle charging station usage and profitability in Germany based on empirical data / https://www.iea.org/reports/global-ev-outlook-2025/electric-vehicle-charging
    # Representative empirical, real-world charging station usage characteristics and data in Germany -> https://www.sciencedirect.com/science/article/pii/S2590116820300369
    CHARGING_STATION_POWER=[50.0],
    # How many plugs / slots a charging station has. If single value, all stations have the same capacity
    CHARGING_STATION_CAPACITY=[20],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[99],
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

operator_1 = OperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    OPERATIONS_TYPE=RideHailingBaseChargingOperations,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=OperationsConfig(
        OPERATIONS_START=15,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=15,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=9.54,
    ),
)
operator_2 = OperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    OPERATIONS_TYPE=RideHailingBaseChargingOperations,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=OperationsConfig(
        OPERATIONS_START=15,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=15,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=9.54,
    ),
)
