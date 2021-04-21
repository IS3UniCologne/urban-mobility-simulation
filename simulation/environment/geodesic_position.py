from .position import Position

class GeodesicPosition(Position):

    def __init__(self, latitude, longitude):
        self._lat = latitude
        self._lng = longitude

    def getExactLocation(self):
        return (self._lat, self._lng)


    def __str__(self):
        return f'Latitude {self._lat} : Longitude {self._lng}'