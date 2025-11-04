from simulation.helper.configuration.enums import PopulationType  # noqa: D100
from simulation.helper.random.random_manager import RandomManager


class PopulationFactory:  # noqa: D101
    __slots__ = ("_prob", "_rng")

    def __init__(self, prob: list[float], random_manager: RandomManager) -> None:
        # Random Number Generator
        self._rng = random_manager.get_rng(component_name="POPULATIONFACTORY")

        # Probability (for price sensitive user)
        self._prob = prob

    def generatePopulationType(self) -> PopulationType:  # noqa: D102
        pop_type = self._rng.binomial(1, self._prob, 1)

        if pop_type == 0:
            return PopulationType.PRICE_SENSITIVE
        else:
            return PopulationType.CONVENIENCE_SEEKER

    def generatePopulationTypeRideHailing(self) -> PopulationType:  # noqa: D102
        pop_type = self._rng.multinomial(1, self._prob)
        if pop_type.argmax() == 0:
            return PopulationType.CLUSTER_0
        elif pop_type.argmax() == 1:
            return PopulationType.CLUSTER_1
        elif pop_type.argmax() == 2:
            return PopulationType.CLUSTER_2
        else:
            return PopulationType.CLUSTER_3
