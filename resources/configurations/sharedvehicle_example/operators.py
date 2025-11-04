from simulation.helper.configuration.configuration import (
    IntegratedSharedMobilityOperationsConfig,
    OperatorConfig,
    SharedVehicleAllocationEngineConfig,
    SharedVehicleConfig,
    SharedVehicleFleetConfig,
    SharedVehicleSearchEngineConfig,
)
from simulation.helper.configuration.enums import (
    AutonomyType,
    PropulsionType,
    VehicleType,
)
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine

shared_bike = SharedVehicleConfig(
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    CONVENIENCE=1,
    COST_PER_KM=0.1,
    DAILY_TOTAL_COST=11.51,
    ENERGY_CONSUMPTION=0.0,
    INITIAL_SOC=1.0,
    KG_CO2_PER_KM=0.046,
    MAX_AVAILABLE_SEATS=1,
    MAX_STATE_OF_CHARGE=1.0,
    PRICE_PER_MIN=0.08,
    PROPULSION_TYPE=PropulsionType.HUMAN_POWERED,
    VEHICLE_TYPE=VehicleType.BIKE,
    VELOCITY=2.82,
    WALKING_DISTANCE=200,
)

shared_kick_scooter = SharedVehicleConfig(
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=1,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=11.51,
    ENERGY_CONSUMPTION=0.0072,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.8,
    KG_CO2_PER_KM=0.105,
    MAX_AVAILABLE_SEATS=1,
    MAX_STATE_OF_CHARGE=0.288,
    PRICE_PER_MIN=0.19,
    PRICE_PER_TRIP=1.0,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    VEHICLE_TYPE=VehicleType.KICK_SCOOTER,
    VELOCITY=2.82,
    WALKING_DISTANCE=200,
)

shared_scooter = SharedVehicleConfig(
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=2,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=7.66,
    ENERGY_CONSUMPTION=0.048,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.8,
    KG_CO2_PER_KM=0.051,
    MAX_AVAILABLE_SEATS=1,
    MAX_STATE_OF_CHARGE=4.8,
    PRICE_PER_MIN=0.23,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    VEHICLE_TYPE=VehicleType.SCOOTER,
    VELOCITY=8.04,
    WALKING_DISTANCE=350,
)

shared_car = SharedVehicleConfig(
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    CHARGING_COST_PER_KWH=0.23,
    CONVENIENCE=3,
    COST_PER_KM=0.53,
    DAILY_TOTAL_COST=29.86,
    ENERGY_CONSUMPTION=0.20,
    EV_RELATIVE_ENERGY_CONSUMPTION=0.8,
    INITIAL_SOC=0.50,
    KG_CO2_PER_KM=0.236,
    MAX_AVAILABLE_SEATS=4,
    MAX_STATE_OF_CHARGE=50.0,
    PRICE_PER_KM=1.3,
    PRICE_PER_MIN=0.35,
    PROPULSION_TYPE=PropulsionType.INTERNAL_COMBUSTION,
    VEHICLE_TYPE=VehicleType.CAR,
    VELOCITY=9.54,
    WALKING_DISTANCE=500,
)

fleet = SharedVehicleFleetConfig(
    VEHICLES={
        shared_bike: 200,
        shared_kick_scooter: 200,
        shared_scooter: 100,
        shared_car: 50,
    }
)

operations = IntegratedSharedMobilityOperationsConfig(
    OPERATIONS_TYPE=IntegratedSharedMobilityOperations,
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
)

operator_1 = OperatorConfig(
    FLEET_CONFIG=fleet,
    OPERATOR_TYPE=SharedMobilityOperator,
    OPERATIONS_CONFIG=operations,
    SEARCH_ENGINE_CONFIG=SharedVehicleSearchEngineConfig(
        SEARCH_ENGINE_TYPE=SharedVehicleSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=SharedVehicleAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=SharedVehicleAllocationEngine
    ),
)
