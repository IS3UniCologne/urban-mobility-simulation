from simulation.helper.configuration.configuration import (
    OperationsConfig,
    OperatorConfig,
)
from simulation.operator.operations_management.ridehailing_uncoordinated_charging_operations import (
    RideHailingUncoordinatedChargingOperations,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator

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
    OPERATIONS_CONFIG=OperationsConfig(
        OPERATIONS_START=10,
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=10,
        RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
        VEHICLE_RELOCATION_VELOCITY=32.16,
        ALLOW_QUEUE=True,
    ),
)
