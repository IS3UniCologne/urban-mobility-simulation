from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative


class TransportationAlternativeBrowser:

    def __init__(self):
        self._transportation_alternatives = []

    def add_transportation_alternative(self, transportation_alternative: TransportationAlternative):
        self._transportation_alternatives.append(transportation_alternative)

    @property
    def transportation_alternatives(self):
        return self._transportation_alternatives

    @transportation_alternatives.setter
    def transportation_alternatives(self, transportation_alternatives):
        self._transportation_alternatives = transportation_alternatives

