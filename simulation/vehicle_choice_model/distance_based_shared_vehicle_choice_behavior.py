from statsmodels.iolib.smpickle import load_pickle

from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)


class DistanceBasedSharedVehicleVehicleChoiceBehavior(VehicleChoiceBehaviorInterface):
    __slots__ = (
        "_available_vehicles",
        "_choice_model",
        "_class_mapping",
        "_substitution_boundary",
    )

    def __init__(self, path_to_choice_model, substitution_boundary, available_vehicles):  # noqa: ANN001, ANN204
        # Load Choice Model
        self._choice_model = load_pickle(path_to_choice_model)

        self._substitution_boundary = substitution_boundary

        # derived order through: sm.MNLogit(Y, X)._ynames_map
        self._class_mapping = {0: "Bike", 1: "Car", 2: "KickScooter", 3: "Scooter"}

        self._available_vehicles = available_vehicles

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):  # noqa: ANN201
        # Predict single outcome (1, distance) (1 = constant)
        # (Car, Kick Scooter, Scooter)
        # (p_car, p_ks, p_scooter)

        choice_probabilities = self._choice_model.predict(
            (1, trip_characteristics.distance)
        )
        choice_probabilities = choice_probabilities.reshape(
            -1
        )  # Transform 2D array to 1D array
        result = {}

        for i in range(len(choice_probabilities)):
            result[self._class_mapping[i]] = choice_probabilities[i]

        # Get Choice Index
        choice = choice_probabilities.argmax()

        # Calculate Substitution Bounds
        lower_bound = choice_probabilities[choice] - self._substitution_boundary

        # Set Candidate Vehicle Choices to 1 based on given Trip Chars
        for key, value in result.items():
            result[key] = 1 if value >= lower_bound else 0

        return result
