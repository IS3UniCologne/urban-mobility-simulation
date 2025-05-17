"""
Environment module with geodesic operations and position handling.
"""

# Import Cython functions to expose them at the package level
try:
    from .cython_ext.cy_geodesic import cy_euclidean_distance
except ImportError:
    # Fallback implementation for when Cython extension is not built
    import math

    def cy_euclidean_distance(
        lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """
        Fallback pure Python implementation of cy_euclidean_distance when Cython is not available.

        Parameters
        ----------
        lat1 : float
            Latitude of the first point (degrees)
        lng1 : float
            Longitude of the first point (degrees)
        lat2 : float
            Latitude of the second point (degrees)
        lng2 : float
            Longitude of the second point (degrees)

        Returns
        -------
        float
            Euclidean distance in meters
        """
        lat_to_meters = 111320.0
        lat1_rad = lat1 * (math.pi / 180.0)
        lng_to_meters = 111320.0 * math.cos(lat1_rad)
        dlat = (lat1 - lat2) * lat_to_meters
        dlng = (lng1 - lng2) * lng_to_meters
        return math.sqrt(dlat * dlat + dlng * dlng)
