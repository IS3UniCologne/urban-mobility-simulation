from simulation.infrastructure.route import Route  # noqa: D100
from simulation.operator.data_transfer_object.transport_request import TransportRequest
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.vehicle.walking import Walking


class WalkingSearchEngine(SearchEngineInterface):  # noqa: D101
    __slots__ = ("_env", "_walking")

    def __init__(self, env):  # noqa: ANN001, ANN204
        self._env = env
        self._walking = Walking(env)

    def search_for_transportation_alternatives(
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param transport_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """  # noqa: D205, D400
        browser = TransportationAlternativeBrowser()

        origin = transport_task.origin
        destination = transport_task.destination

        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Calc Duration
        duration = self._walking.calculate_travel_time(distance)

        # Calc Price
        price = 0

        # Put together
        transportation_alternative = TransportationAlternative(
            self._walking, route, price, duration, distance, 3
        )

        browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201, D102
        self,
        user,  # noqa: ANN001
        transportation_task: TransportRequest,
        selected_transportation_alternative: TransportationAlternative,
    ):
        pass
