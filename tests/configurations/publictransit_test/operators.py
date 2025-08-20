from simulation.helper.configuration.configuration import (
    OperationsConfig,
    OperatorConfig,
)
from simulation.operator.operations_management.operations_public_transport import (
    OperationsPublicTransport,
)
from simulation.operator.public_transit_operator import PublicTransitOperator

operator_1 = OperatorConfig(
    OPERATOR_TYPE=PublicTransitOperator,
    OPERATIONS_TYPE=OperationsPublicTransport,
    # how many busses the transit operator is allowed to spawn
    MAX_BUSSES=3,
    OPERATIONS_CONFIG=OperationsConfig(
        # how many minutes the PublicTransitOperator plans ahead ==
        PLANNING_LOOKAHEAD=10
    ),
)
