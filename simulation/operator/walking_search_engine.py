from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.walking import Walking


class WalkingSearchEngine(SearchEngineInterface, PaymentInterface):
    __slots__ = ("_env", "_walking")

    def __init__(self, env):  # noqa: ANN001, ANN204
        PaymentInterface.__init__(self)
        self._env = env
        self._walking = Walking(env)

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Calc Duration
        duration = distance / self._walking.velocity

        # Calc Price
        price = 0

        # Put together
        transportation_alternative = TransportationAlternative(
            self._walking, route, price, duration, distance, 3
        )

        browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(  # noqa: ANN201
        self,
        user,  # noqa: ANN001
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        pass

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):  # noqa: ANN001, ANN201
        pass
