from typing import List

import numpy

from simulation.helper.configuration.enums import PopulationType
from simulation.helper.random.random_manager import RandomManager


class PopulationFactory:
    def __init__(self, prob: List[float]) -> None:
        # Random Number Generator
        self._rng = RandomManager().get_rng(component_name="POPULATIONFACTORY")

        # Probability (for price sensitive user)
        self._prob = prob

    def generatePopulationType(self) -> PopulationType:
        pop_type = self._rng.binomial(1, self._prob, 1)

        if pop_type == 0:
            return PopulationType.PRICE_SENSITIVE
        else:
            return PopulationType.CONVENIENCE_SEEKER

    def generatePopulationTypeRideHailing(self) -> PopulationType:
        pop_type = self._rng.multinomial(1, self._prob)
        if pop_type.argmax() == 0:
            return PopulationType.CLUSTER_0
        elif pop_type.argmax() == 1:
            return PopulationType.CLUSTER_1
        elif pop_type.argmax() == 2:
            return PopulationType.CLUSTER_2
        else:
            return PopulationType.CLUSTER_3
