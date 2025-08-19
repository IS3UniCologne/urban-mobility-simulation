from simulation.helper.configuration.configuration import RideHailingOperatorConfig
from simulation.operator.operations_management.ridehailing_uncoordinated_charging_operations import (
    RideHailingUncoordinatedChargingOperations,
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

ridehailing_operator_1 = RideHailingOperatorConfig(
    RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
    OPERATIONS_START=10,
    OPERATIONS_DURATION=50,
    VEHICLE_RELOCATION_VELOCITY=32.16,
    OPERATIONS_TYPE=RideHailingUncoordinatedChargingOperations,
)

ridehailing_operator_2 = RideHailingOperatorConfig(
    RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
    OPERATIONS_START=10,
    OPERATIONS_DURATION=50,
    VEHICLE_RELOCATION_VELOCITY=32.16,
    OPERATIONS_TYPE=RideHailingUncoordinatedChargingOperations,
)
