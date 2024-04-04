import h3
import simpy
from shapely.geometry import shape


class ChargingStation:
    def __init__(self, id, env, location, power, capacity):
        self.env = env
        self.capacity = capacity
        location = location.split("'")[1].split("'")[0]
        self.polygon = shape(
            {
                "type": "Polygon",
                "coordinates": [h3.h3_to_geo_boundary(location, geo_json=True)],
                "properties": "",
            }
        )
        self.centre = [self.polygon.centroid.y, self.polygon.centroid.x]
        self.plugs = simpy.PriorityResource(self.env, capacity=capacity)
        self.id = id
        self.location = location
        self.power = power  # kwh/hr
        self.queue = []
        # self.position = self.location.find_zone(zones)
