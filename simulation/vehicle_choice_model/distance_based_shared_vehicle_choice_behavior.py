from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import VehicleChoiceBehaviorInterface
from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from statsmodels.iolib.smpickle import load_pickle

class DistanceBasedSharedVehicleVehicleChoiceBehavior(VehicleChoiceBehaviorInterface):

    def __init__(self, path_to_choice_model, substitution_boundary, available_vehicles):
        # Load Choice Model
        self._choice_model = load_pickle(path_to_choice_model)

        self._substitution_boundary = substitution_boundary

        self._available_vehicles = available_vehicles

    def choose_vehicle(self, trip_characteristics: TripCharacteristics):
        # Predict single outcome (1, distance) (1 = constant)
        # (Car, Kick Scooter, Scooter)
        # (p_car, p_ks, p_scooter)
        choice_probabilities = self._choice_model.predict((1, trip_characteristics.distance))
        choice_probabilities = choice_probabilities.reshape((-1)) # Transform 2D array to 1D array

        # Get Choice Index
        choice = choice_probabilities.argmax()

        # Calculate Substitution Bounds
        lower_bound = choice_probabilities[choice] - self._substitution_boundary

        # Set Candidate Vehicle Choices to 1 based on given Trip Chars
        mode_choices = [1 if x >= lower_bound else 0 for x in choice_probabilities]

        # Return vehicles which are considered as viable means of transport
        result = {}
        for idx, mode_choice in enumerate(mode_choices):
            if mode_choices[idx]:
                result[self._available_vehicles[idx]] = 1
            else:
                result[self._available_vehicles[idx]] = 0
        return result