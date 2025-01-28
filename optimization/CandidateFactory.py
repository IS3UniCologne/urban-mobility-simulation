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
        elif self._num == 5:
            return self.distribute_equally([1 / 2, 1 / 2, 0, 0])
        elif self._num == 6:
            return self.distribute_equally([1 / 2, 0, 1 / 2, 0])
        elif self._num == 7:
            return self.distribute_equally([1 / 2, 0, 0, 1 / 2])
        elif self._num == 8:
            return self.distribute_equally([0, 1 / 2, 1 / 2, 0])
        elif self._num == 9:
            return self.distribute_equally([0, 1 / 2, 0, 1 / 2])
        elif self._num == 10:
            return self.distribute_equally([0, 0, 1 / 2, 1 / 2])
        elif self._num == 11:
            return self.distribute_equally([0, 1 / 3, 1 / 3, 1 / 3])
        elif self._num == 12:
            return self.distribute_equally([1 / 3, 0, 1 / 3, 1 / 3])
        elif self._num == 13:
            return self.distribute_equally([1 / 3, 1 / 3, 0, 1 / 3])
        elif self._num == 14:
            return self.distribute_equally([1 / 3, 1 / 3, 1 / 3, 0])
        elif self._num == 15:
            return self.distribute_equally([1 / 4, 1 / 4, 1 / 4, 1 / 4])
        else:
            return self.create_individual(self._fleet_size)

    # Function to distribute fleet size according to ratios and ensure fleet size
    def distribute_equally(self, ratios):
        total = self._fleet_size
        raw_numbers = [total * ratio for ratio in ratios]
        integers = [int(num) for num in raw_numbers]
        difference = total - sum(integers)

        # Adjust the integers to make sure their sum equals total fleet size
        if difference != 0:
            # Find indices with non-zero ratios
            non_zero_indices = [i for i, ratio in enumerate(ratios) if ratio > 0]
            fractional_parts = [
                (raw_numbers[i] - integers[i]) for i in non_zero_indices
            ]

            if difference > 0:
                for _ in range(difference):
                    max_index = non_zero_indices[
                        fractional_parts.index(max(fractional_parts))
                    ]
                    integers[max_index] += 1
                    fractional_parts[non_zero_indices.index(max_index)] = 0
            elif difference < 0:
                for _ in range(-difference):
                    min_index = non_zero_indices[
                        fractional_parts.index(min(fractional_parts))
                    ]
                    integers[min_index] -= 1
                    fractional_parts[non_zero_indices.index(min_index)] = 0

        return integers

    # Function that returns a random distribution of shared vehicles
    def create_individual(self, fleet_size):
        parts = random.sample(range(fleet_size + 1), 3)
        parts.sort()

        print(
            f"Create individual: {[parts[0], parts[1] - parts[0], parts[2] - parts[1], fleet_size - parts[2]]}"
        )
        return [
            parts[0],
            parts[1] - parts[0],
            parts[2] - parts[1],
            fleet_size - parts[2],
        ]
