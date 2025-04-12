import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


def haversine_np(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    All args must be of equal length.

    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2

    c = 2 * np.arcsin(np.sqrt(a))
    meters = 6378137 * c
    return float(meters)


def reverse_geocode(lat, lon, language="ru", user_agent="my_geocoder"):
    """
    This function performs reverse geocoding by converting coordinates (lat, lon)
    into a human-readable address.

    :param lat: Latitude of the point.
    :param lon: Longitude of the point.
    :param language: The language in which the address should be returned (default is 'ru').
    :param user_agent: The application identifier for the geocoding service.
    :return: A human-readable address or an error message.
    """
    geolocator = Nominatim(user_agent=user_agent)
    try:
        # Execute a reverse geocoding request.
        # The language parameter can be set to return the address in the desired language.
        location = geolocator.reverse((lat, lon), language=language)
        if location:
            return location.address
        else:
            return "Address not found"
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        # Handle errors, for example, in case of timeout or other service issues.
        print("Geocoding error:", e)
        return None
