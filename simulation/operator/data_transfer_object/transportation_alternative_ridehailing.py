from simulation.helper.configuration.enums import VehicleState
from simulation.infrastructure.route import Route
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class TransportationAlternativeRideHailing:
    __slots__ = (
        "_vehicle",
        "_vehicle_type",
        "_price",
        "_duration",
        "_distance",
        "_route",
        "_convenience",
        "_energy_consumed",
        "_waiting_time",
        "_environment",
        "_technology_skeptical",
        "_electric_vehicle",
        "_autonomous_vehicle",
        "_route_to_pickup",
        "_distance_to_pickup",
        "_pick_up_time",
        "_utility",
    )

    def __init__(
        self,
        vehicle: RideHailingVehicle,
        route: Route,
        price,
        duration,
        distance,
        convenience,
        route_to_pickup: Route,
    ):
        self._vehicle = vehicle
        self._vehicle_type = vehicle.__class__.__name__
        self._price = price
        self._duration = duration
        self._distance = distance
        self._route = route
        self._convenience = convenience  # the ranking (the lower, the better)
        self._environment = self.set_environment()
        self._technology_skeptical = self.set_technology_skeptical()
        self._electric_vehicle = self.set_environment()
        self._autonomous_vehicle = self.set_autonomous_vehicle()
        self._route_to_pickup = route_to_pickup
        self._distance_to_pickup = route_to_pickup.distance
        self._pick_up_time = self.set_pick_up_time()
        self._utility = 0.0

        self._waiting_time = 0.0  # Is set after successful allocation
        self._energy_consumed = 0.0  # Is set after successful trip

    def set_pick_up_time(self):
        if self.vehicle.state == VehicleState.PARKING:
            return self._distance_to_pickup / self.vehicle.velocity

        elif self.vehicle.state == VehicleState.DRIVING:
            return (
                self._distance_to_pickup / self.vehicle.velocity
                + self.vehicle.estimated_completion_time
                - self.vehicle._env.now
            )

    def set_environment(self):
        if self._vehicle.is_electric:
            return 1
        else:
            return 0

    def set_technology_skeptical(self):
        if self._vehicle_type == "AutonomousCar":
            return 0
        else:
            return 1

    def set_autonomous_vehicle(self):
        if self._vehicle_type == "AutonomousCar":
            return 1
        else:
            return 0

    @property
    def environment(self):
        return self._environment

    @property
    def electric_vehicle(self):
        return self._electric_vehicle

    @property
    def autonomous_vehicle(self):
        return self._autonomous_vehicle

    @property
    def utility(self):
        return self._utility

    @property
    def technology_skeptical(self):
        return self._technology_skeptical

    @property
    def vehicle(self):
        return self._vehicle

    @property
    def vehicle_type(self):
        return self._vehicle_type

    @property
    def price(self):
        return self._price

    @property
    def duration(self):
        return self._duration

    @property
    def distance(self):
        return self._distance

    @property
    def route(self):
        return self._route

    @property
    def convenience(self):
        return self._convenience

    @property
    def route_to_pickup(self):
        return self._route_to_pickup

    @property
    def distance_to_pickup(self):
        return self._distance_to_pickup

    @property
    def pick_up_time(self):
        return self._pick_up_time

    # Perhaps it makes sense to encapsulate TransportationAlternative
    #  around a "SuccessfulTrip" where we store this object along with
    #  variables pertaining the to trip (as energy consumed, (real) travelled distance)
    @property
    def energy_consumed(self):
        return self._energy_consumed

    def set_energy_consumed(self, energy_consumption):
        # energy_consumption: in kWh
        self._energy_consumed += energy_consumption

    @property
    def waiting_time(self):
        return self._waiting_time

    def set_waiting_time(self, waiting_time):
        # energy_consumption: in kWh
        self._waiting_time += waiting_time

    def __str__(self) -> str:
        return f"Vehicle {self._vehicle}, Price {self._price}, Duration {self._duration}, Distance {self._distance}, Convenience {self._convenience}, Distance to pickup {self._distance_to_pickup}, Pick up time {self._pick_up_time}"

    def __repr__(self) -> str:
        return self.__str__()
