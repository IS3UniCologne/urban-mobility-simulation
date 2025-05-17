# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""
# Cython implementation of geodesic distance calculation
"""

from libc.math cimport cos, sqrt

def cy_euclidean_distance(double lat1, double lng1, double lat2, double lng2) -> double:
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
    cdef double lat_to_meters = 111320.0
    cdef double lat1_rad = lat1 * (3.141592653589793 / 180.0)
    cdef double lng_to_meters = 111320.0 * cos(lat1_rad)
    cdef double dlat = (lat1 - lat2) * lat_to_meters
    cdef double dlng = (lng1 - lng2) * lng_to_meters
    return sqrt(dlat * dlat + dlng * dlng)
