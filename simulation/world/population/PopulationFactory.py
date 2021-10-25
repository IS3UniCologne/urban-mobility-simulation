from enum import Enum
import numpy

class PopulationType(Enum):
    PRICE_SENSITIVE = 0
    CONVENIENCE_SEEKER = 1 # or Sustainanble

class PopulationFactory():

    def __init__(self, prob, seed):
        # Random Number Generator
        self._random = numpy.random.RandomState(seed)

        # Probability (for price sensitive user)
        self._prob = 1-prob

    def generatePopulationType(self):

        pop_type = self._random.binomial(1, self._prob, 1)

        if pop_type == 0:
            return PopulationType.PRICE_SENSITIVE
        else:
            return PopulationType.CONVENIENCE_SEEKER