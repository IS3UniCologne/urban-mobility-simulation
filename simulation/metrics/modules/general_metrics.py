class GeneralMetrics:

    def __init__(self, transactions):
        self._transactions = transactions

    def get_num_user_requests(self) -> int:
        return len(self._transactions)

    def get_fulfilled_trips(self):
        return self._transactions[self._transactions['state'] == 'Fulfilled']

    def get_missed_trips(self):
        return self._transactions[self._transactions['state'] == 'Missed']

    def get_num_fulfilled_trips(self):
        return len(self.get_fulfilled_trips())

    def get_num_missed_trips(self):
        return len(self.get_missed_trips())

    def get_fulfillment_rate(self):
        num_user_requests = self.get_num_user_requests()
        return self.get_num_fulfilled_trips() / num_user_requests if num_user_requests > 0 else 0

    def get_traveled_distance(self):
        return self._transactions['distance'].sum()

    def print_summary(self):
        print('')
        print(f'#--------General Metrics--------')
        print(' ')
        print(f'#  Num. Trips: {len(self._transactions)} ')
        print(f'#  Num. Ful. Trips: {self.get_num_fulfilled_trips()} ')
        print(f'#  Num. Miss. Trips: {self.get_num_missed_trips()} ')
        print(f'#  Num. Ful. Rate: {self.get_fulfillment_rate()} ')
        print(f'#  Distance: {self.get_traveled_distance()} ')
        print(' ')
        print('-' * 40)
