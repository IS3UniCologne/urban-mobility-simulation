from simpy import Environment
import datetime

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


class SimulationTime:
    """
    Implements easy access to simpy's environment time.
    While simpy's time is unitless, we assume it to be minutes.
    """
    def __init__(self, env: Environment):
        self._env = env

    def now(self):
        return self._env.now

    def minutes(self):
        return int(self._env.now % 60)

    def hours(self):
        return int((self._env.now / 60) % 60)

    def dayofweek(self):
        return int((self._env.now % (24*60*7)) / (24*60))

    def dayofweek_as_str(self) -> str:
        return WEEKDAYS[self.dayofweek()]

    def next_dayofweek_as_str(self) -> str:
        return WEEKDAYS[(self.dayofweek() + 1) % 7]

    def now_as_str(self, strf: str = '%H:%M:%S'):
        time = datetime.time(self.hours(), self.minutes())
        return time.strftime(strf)

    def convert_to_day_of_week_bucket(self):
        if self.dayofweek() < 5:
            return False # Non_Working_Day? No => weekday
        else:
            return True  # Non_Working_Day? Yes (i.e., holidays, weekends)
