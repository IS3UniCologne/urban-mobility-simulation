import random


class CandidateFactory:
    _num = 0

    # TODO: MAX fleet size as parameter
    # Function that returns distributions of shared vehicles
    def get_ind(self):
        self._num = self._num + 1

        if self._num == 1:
            return [2000, 0, 0, 0]
        elif self._num == 2:
            return [0, 2000, 0, 0]
        elif self._num == 3:
            return [0, 0, 2000, 0]
        elif self._num == 4:
            return [0, 0, 0, 2000]
        else:
            return self.create_individual()

    # TODO: MAX fleet size as parameter
    # Function that returns a random distribution of shared vehicles
    def create_individual(self):
        parts = random.sample(range(2001), 3)
        parts.sort()

        print(f'Create individual: {[parts[0], parts[1] - parts[0], parts[2] - parts[1], 2000 - parts[2]]}')
        return [parts[0], parts[1] - parts[0], parts[2] - parts[1], 2000 - parts[2]]
