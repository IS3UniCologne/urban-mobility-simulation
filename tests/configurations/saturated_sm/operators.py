from simulation.helper.configuration.configuration import (
    VehicleCostConfig,
    WorkerCostConfig,
    IntegratedSharedMobilityOperationsConfig,
    SharedVehicleAllocationEngineConfig,
    SharedVehicleConfig,
    SharedVehicleFleetConfig,
    SharedVehicleOperatorConfig,
    SharedVehicleSearchEngineConfig,
)
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine

sv_car = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.CAR,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    CONVENIENCE=3,
    ENERGY_CONSUMPTION_PER_KM=0.20,
    INITIAL_CHARGE_RATIO=0.50,
    KG_CO2_PER_KM=0.236,
    VELOCITY_KMH=9.54,
    MAX_AVAILABLE_SEATS=4,
    ENERGY_CAPACITY=50.0,
    PRICE_PER_KM=1.3,
    PRICE_PER_MIN=0.35,
    WALKING_DISTANCE=500,
    COST_CONFIG=VehicleCostConfig(
        PER_KM=0.53, CHARGING_PER_KWH=0.23, DAILY_ONLINE=29.86, DAILY_OFFLINE=0.0
    ),
)
sv_scooter = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.SCOOTER,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    CONVENIENCE=2,
    ENERGY_CONSUMPTION_PER_KM=0.048,
    KG_CO2_PER_KM=0.051,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=4.8,
    PRICE_PER_MIN=0.23,
    VELOCITY_KMH=8.04,
    WALKING_DISTANCE=350,
    COST_CONFIG=VehicleCostConfig(
        PER_KM=0.53, CHARGING_PER_KWH=0.23, DAILY_ONLINE=7.66, DAILY_OFFLINE=0.0
    ),
)

sv_kickscooter = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.KICK_SCOOTER,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
    CONVENIENCE=1,
    ENERGY_CONSUMPTION_PER_KM=0.0072,
    KG_CO2_PER_KM=0.105,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=0.288,
    PRICE_PER_MIN=0.19,
    VELOCITY_KMH=2.82,
    WALKING_DISTANCE=200,
    COST_CONFIG=VehicleCostConfig(
        PER_KM=0.53, CHARGING_PER_KWH=0.23, DAILY_ONLINE=11.51, DAILY_OFFLINE=0.0
    ),
)
sv_bike = SharedVehicleConfig(
    VEHICLE_TYPE=VehicleType.BIKE,
    AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
    PROPULSION_TYPE=PropulsionType.HUMAN_POWERED,
    CONVENIENCE=1,
    ENERGY_CONSUMPTION_PER_KM=0.0,
    KG_CO2_PER_KM=0.046,
    MAX_AVAILABLE_SEATS=1,
    ENERGY_CAPACITY=1.0,
    PRICE_PER_MIN=0.08,
    VELOCITY_KMH=2.82,
    WALKING_DISTANCE=200,
    COST_CONFIG=VehicleCostConfig(PER_KM=0.1, DAILY_ONLINE=11.51, DAILY_OFFLINE=0.0),
)


operator_1 = SharedVehicleOperatorConfig(
    OPERATOR_TYPE=SharedMobilityOperator,
    FLEET_CONFIG=SharedVehicleFleetConfig(
        VEHICLES={sv_car: 50, sv_scooter: 50, sv_kickscooter: 70, sv_bike: 20}
    ),
    OPERATIONS_CONFIG=IntegratedSharedMobilityOperationsConfig(
        OPERATIONS_TYPE=IntegratedSharedMobilityOperations,
        # Operations Start Time (e.g., 1440 => 00:00am) !!! 20.000 --> quasi no operations !!!
        OPERATIONS_START=15,
        # Operations Duration (e.g., 8 working hours => 8*60 => 480)
        OPERATIONS_DURATION=50,
        TIME_BETWEEN_OPERATIONS=80,
        # When vehicles drop below RECHARGE_THRESHOLD => cannot be rented and needs to be recharged
        # Optimal Deployment of Charging Stations for Electric Vehicular Networks https://dl.acm.org/doi/pdf/10.1145/2413236.2413238 -> SOC threshold: 0.05
        RECHARGE_THRESHOLD=0.4,
        # Velocity of Relocation Vehicle (i.e., car/van velocity) in kilometer/hour
        # Free-floating carsharing vehicle placement and relocation -> Takes 40 km/h but says that this is probably too fast for the city center.
        # Feature-based selection of carsharing relocation modes: 15-20 km/h for Munich, Milan and Toronto https://www.sciencedirect.com/science/article/pii/S1366554521000466
        VEHICLE_RELOCATION_VELOCITY=9.54,
        # Number of Service Workers
        NUMBER_OF_SERVICE_WORKERS=100,
        WORKER_COST_CONFIG=WorkerCostConfig(HOURLY=1.0),
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
    ),
    SEARCH_ENGINE_CONFIG=SharedVehicleSearchEngineConfig(
        SEARCH_ENGINE_TYPE=SharedVehicleSearchEngine
    ),
    ALLOCATION_ENGINE_CONFIG=SharedVehicleAllocationEngineConfig(
        VEHICLE_ALLOCATION_ENGINE_TYPE=SharedVehicleAllocationEngine
    ),
)
