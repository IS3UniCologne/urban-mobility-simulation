from simulation.helper.configuration.configuration import (
    OperationsConfig,
    OperatorConfig,
)
from simulation.helper.configuration.enums import VehicleType
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.shared_mobility_operator import SharedMobilityOperator

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
    OPERATOR_TYPE=SharedMobilityOperator,
    OPERATIONS_TYPE=IntegratedSharedMobilityOperations,
    # Installed Charging Station Power
    # kW (slow charger), or 7 kW or 22 kW (fast charger)
    # Representative empirical, real-world charging station usage characteristics and data in Germany -> https://www.sciencedirect.com/science/article/pii/S2590116820300369
    CHARGING_STATION_POWER=50.0,
    NUMBER_OF_BASE_REGIONS=10,
    # Base vehicle capacity (i.e.g, how many vehicle can we provide services)
    BASE_CAPACITY=100000,
    # berlin
    BASE_REGIONS=[
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
    N_VEHICLES={
        VehicleType.BIKE: 200,
        VehicleType.CAR: 500,
        VehicleType.KICK_SCOOTER: 700,
        VehicleType.SCOOTER: 500,
    },
    OPERATIONS_CONFIG=OperationsConfig(
        # Operations Start Time (e.g., 1440 => 00:00am) !!! 20.000 --> quasi no operations !!!
        OPERATIONS_START=15,
        # Operations Duration (e.g., 8 working hours => 8*60 => 480)
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=15,
        # When vehicles drop below RECHARGE_THRESHOLD => cannot be rented and needs to be recharged
        # Optimal Deployment of Charging Stations for Electric Vehicular Networks https://dl.acm.org/doi/pdf/10.1145/2413236.2413238 -> SOC threshold: 0.05
        RECHARGE_THRESHOLD=0.1,
        # Velocity of Relocation Vehicle (i.e., car/van velocity) in kilometer/hour
        # Free-floating carsharing vehicle placement and relocation -> Takes 40 km/h but says that this is probably too fast for the city center.
        # Feature-based selection of carsharing relocation modes: 15-20 km/h for Munich, Milan and Toronto https://www.sciencedirect.com/science/article/pii/S1366554521000466
        VEHICLE_RELOCATION_VELOCITY=9.54,
        # Number of Service Workers
        NUMBER_OF_SERVICE_WORKERS=100,
    ),
)
