from enum import Enum

import numpy


class PopulationType(Enum):
    CLUSTER_0 = 0
    CLUSTER_1 = 1
    CLUSTER_2 = 2
    CLUSTER_3 = 3
    PRICE_SENSITIVE = 4
    CONVENIENCE_SEEKER = 5


class PopulationFactory:
    def __init__(self, prob, seed):
        # Random Number Generator
        self._random = numpy.random.RandomState(seed)

        # Probability (for price sensitive user)
        self._prob = prob

    def generatePopulationType(self):
        pop_type = self._random.binomial(1, self._prob, 1)

        if pop_type == 0:
            return PopulationType.PRICE_SENSITIVE
        else:
            return PopulationType.CONVENIENCE_SEEKER

    def generatePopulationTypeRideHailing(self):
        pop_type = self._random.multinomial(1, self._prob)
        if pop_type.argmax() == 0:
            return PopulationType.CLUSTER_0
        elif pop_type.argmax() == 1:
            return PopulationType.CLUSTER_1
        elif pop_type.argmax() == 2:
            return PopulationType.CLUSTER_2
        else:
            return PopulationType.CLUSTER_3
