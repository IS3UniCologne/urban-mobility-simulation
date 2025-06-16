from simulation.helper.configuration.enums import VehicleState
from simulation.infrastructure.route import Route
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle


class TransportationAlternativeRideHailing:
    __slots__ = (
        "_autonomous_vehicle",
        "_convenience",
        "_distance",
        "_distance_to_pickup",
        "_duration",
        "_electric_vehicle",
        "_energy_consumed",
        "_environment",
        "_pick_up_time",
        "_price",
        "_route",
        "_route_to_pickup",
        "_technology_skeptical",
        "_utility",
        "_vehicle",
        "_vehicle_type",
        "_waiting_time",
    )

    def __init__(  # noqa: ANN204
        self,
        vehicle: RideHailingVehicle,
        route: Route,
        price: float,  # noqa: ANN001
        duration: float,  # noqa: ANN001
        distance: float,  # noqa: ANN001
        convenience: float,  # noqa: ANN001
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

    def set_pick_up_time(self) -> float:
        if self.vehicle.state == VehicleState.PARKING:
            return self._distance_to_pickup / self.vehicle.velocity

        elif self.vehicle.state == VehicleState.DRIVING:
            return (
                self._distance_to_pickup / self.vehicle.velocity
                + self.vehicle.estimated_completion_time
                - self.vehicle._env.now  # noqa: SLF001
            )

    def set_environment(self) -> int:  # noqa: ANN201
        if self._vehicle.is_electric:
            return 1
        else:
            return 0

    def set_technology_skeptical(self) -> int:  # noqa: ANN201
        if self._vehicle_type == "AutonomousCar":
            return 0
        else:
            return 1

    def set_autonomous_vehicle(self) -> int:  # noqa: ANN201
        if self._vehicle_type == "AutonomousCar":
            return 1
        else:
            return 0

    @property
    def environment(self) -> int:
        return self._environment

    @property
    def electric_vehicle(self) -> int:
        return self._electric_vehicle

    @property
    def autonomous_vehicle(self) -> int:
        return self._autonomous_vehicle

    @property
    def utility(self) -> float:
        return self._utility

    @property
    def technology_skeptical(self) -> int:
        return self._technology_skeptical

    @property
    def vehicle(self) -> RideHailingVehicle: 
        return self._vehicle

    @property
    def vehicle_type(self) -> str:
        return self._vehicle_type

    @property
    def price(self) -> float:
        return self._price

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def distance(self) -> float:
        return self._distance

    @property
    def route(self) -> Route:
        return self._route

    @property
    def convenience(self) -> float:
        return self._convenience

    @property
    def route_to_pickup(self) -> Route:
        return self._route_to_pickup

    @property
    def distance_to_pickup(self) -> float:
        return self._distance_to_pickup

    @property
    def pick_up_time(self) -> float:
        return self._pick_up_time

    # Perhaps it makes sense to encapsulate TransportationAlternative
    #  around a "SuccessfulTrip" where we store this object along with
    #  variables pertaining the to trip (as energy consumed, (real) travelled distance)
    @property
    def energy_consumed(self) -> float:
        return self._energy_consumed

    def set_energy_consumed(self, energy_consumption: float) -> None:
        # energy_consumption: in kWh
        self._energy_consumed += energy_consumption

    @property
    def waiting_time(self) -> float:
        return self._waiting_time

    def set_waiting_time(self, waiting_time: float) -> None:
        self._waiting_time += waiting_time

    def __str__(self) -> str:
        return f"Vehicle {self._vehicle}, Price {self._price}, Duration {self._duration}, Distance {self._distance}, Convenience {self._convenience}, Distance to pickup {self._distance_to_pickup}, Pick up time {self._pick_up_time}"

    def __repr__(self) -> str:
        return self.__str__()
