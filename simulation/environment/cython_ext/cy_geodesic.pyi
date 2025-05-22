"""
Type stub for Cython-accelerated geodesic functions.
"""

def cy_euclidean_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the Euclidean distance between two lat/lng points.

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
    ...
