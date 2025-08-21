from simulation.helper.configuration.configuration import (
    ChargingInfrastructureConfig,
    OperationsConfig,
    OperatorConfig,
)
from simulation.operator.operations_management.ridehailing_uncoordinated_charging_operations import (
    RideHailingUncoordinatedChargingOperations,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator

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
    CHARGING_STATION_CAPACITY=[10],
    # How many spaces without plugs (queue for plugs) a charging station has, if single value, all stations have the same capacity
    CHARGING_STATION_QUEUE_SIZE=[0],
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
    OPERATOR_TYPE=RideHailingOperator,
    OPERATIONS_TYPE=RideHailingUncoordinatedChargingOperations,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=OperationsConfig(
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOW_QUEUE=True,
    ),
)

operator_2 = OperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    OPERATIONS_TYPE=RideHailingUncoordinatedChargingOperations,
    CHARGING_INFRASTRUCTURE=charging_infrastructure_1,
    OPERATIONS_CONFIG=OperationsConfig(
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOW_QUEUE=True,
    ),
)
