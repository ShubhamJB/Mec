"""
Geographic utilities: coordinates, PostGIS WKT formatting, and timezone derivation.
"""
from __future__ import annotations

from timezonefinder import TimezoneFinder
from geoalchemy2.elements import WKTElement

_tf: TimezoneFinder | None = None


def get_timezone_finder() -> TimezoneFinder:
    global _tf
    if _tf is None:
        _tf = TimezoneFinder()
    return _tf


def derive_timezone(latitude: float, longitude: float) -> str:
    """
    Derive the IANA timezone string (e.g. 'Asia/Kathmandu', 'America/New_York')
    from latitude and longitude coordinates. Falls back to 'UTC' if not found.
    """
    tf = get_timezone_finder()
    tz = tf.timezone_at(lat=latitude, lng=longitude)
    return tz or "UTC"


def point_from_coords(latitude: float, longitude: float) -> WKTElement:
    """
    Convert (latitude, longitude) into a PostGIS WKT POINT geometry with SRID 4326.
    Note: PostGIS WKT order is POINT(longitude latitude).
    """
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)

