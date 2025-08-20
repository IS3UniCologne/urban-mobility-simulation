from simulation.helper.configuration.configuration import (
    OperationsConfig,
    OperatorConfig,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator

operator_1 = OperatorConfig(
    OPERATOR_TYPE=RideHailingOperator,
    OPERATIONS_TYPE=RideHailingBaseChargingOperations,
    OPERATIONS_CONFIG=OperationsConfig(
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
    ),
)
