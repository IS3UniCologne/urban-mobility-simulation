from simulation.helper.configuration.configuration import RideHailingOperatorConfig

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

ride_hailing_operator_1 = RideHailingOperatorConfig(
    RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
    OPERATIONS_START=15,  # Operations Start Time (e.g., 1440 => 00:00am) !!! 20.000 --> quasi no operations !!!
    OPERATIONS_DURATION=50,  # Operations Duration (e.g., 8 working hours => 8*60 => 480)
    # Velocity of Relocation Vehicle (i.e., car/van velocity) in km/h
    # Feature-based selection of carsharing relocation modes: 15-20 km/h for Munich, Milan and Toronto https://www.sciencedirect.com/science/article/pii/S1366554521000466
    VEHICLE_RELOCATION_VELOCITY=9.54,
)
ride_hailing_operator_2 = RideHailingOperatorConfig(
    RECHARGE_THRESHOLD=DEFAULT_RECHARGE_THRESHOLD,
    OPERATIONS_START=15,
    OPERATIONS_DURATION=50,
    VEHICLE_RELOCATION_VELOCITY=9.54,
)
