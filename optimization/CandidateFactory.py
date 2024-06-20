import random


class CandidateFactory:
    _num = 0

    def __init__(self, max_fleet_size):
        self._fleet_size = max_fleet_size

    # Function that returns distributions of shared vehicles
    def get_ind(self):
        self._num = self._num + 1

        if self._num == 1:
            return [self._fleet_size, 0, 0, 0]
        elif self._num == 2:
            return [0, self._fleet_size, 0, 0]
        elif self._num == 3:
            return [0, 0, self._fleet_size, 0]
        elif self._num == 4:
            return [0, 0, 0, self._fleet_size]
        else:
            return self.create_individual(self._fleet_size)

    # Function that returns a random distribution of shared vehicles
    def create_individual(self, fleet_size):
        parts = random.sample(range(fleet_size+1), 3)
        parts.sort()

        print(f'Create individual: {[parts[0], parts[1] - parts[0], parts[2] - parts[1], fleet_size - parts[2]]}')
        return [parts[0], parts[1] - parts[0], parts[2] - parts[1], fleet_size - parts[2]]
