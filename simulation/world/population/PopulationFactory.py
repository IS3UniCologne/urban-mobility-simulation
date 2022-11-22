from enum import Enum
import numpy

class PopulationType(Enum):
    PRICE_SENSITIVE = 0
    # CONVENIENCE_SEEKER = 1 # or Sustainanble
    WAITING_TIME_SENSITIVE = 1
    ENVIRONMENTAL_CONSCIOUS = 2
    TECHNOLOGICALLY_SKEPTICAL = 3


class PopulationFactory():

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
            return PopulationType.PRICE_SENSITIVE
        elif pop_type.argmax() == 1:
            return PopulationType.WAITING_TIME_SENSITIVE
        elif pop_type.argmax() == 2:
            return PopulationType.ENVIRONMENTAL_CONSCIOUS
        else:
            return PopulationType.TECHNOLOGICALLY_SKEPTICAL
