"""
Availability computation helper: derives OPEN, CLOSED, or TEMPORARILY_UNAVAILABLE
using the garage's IANA timezone and weekly schedule.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any


def calculate_garage_availability(
    *,
    is_temporarily_unavailable: bool,
    temporary_unavailability_message: str | None,
    timezone_str: str,
    operating_hours: list[Any],  # list of OperatingHours models or dicts with day_of_week, is_closed, opening_time, closing_time
) -> dict[str, Any]:
    """
    Derives real-time availability status for a garage.
    Returns:
    {
        "status": "OPEN" | "CLOSED" | "TEMPORARILY_UNAVAILABLE",
        "is_temporarily_unavailable": bool,
        "message": str | None,
        "timezone": str,
        "local_time": str (ISO 8601),
        "next_status_change": str | None
    }
    """
    try:
        tz = ZoneInfo(timezone_str)
    except Exception:
        tz = ZoneInfo("UTC")

    now_local = datetime.now(tz)
    local_time_str = now_local.isoformat()
    current_weekday = now_local.isoweekday()  # 1=Monday .. 7=Sunday
    current_time = now_local.time()

    # Index schedule by day_of_week
    schedule: dict[int, Any] = {}
    for h in operating_hours:
        day = h.day_of_week if hasattr(h, "day_of_week") else h["day_of_week"]
        schedule[day] = h

    if is_temporarily_unavailable:
        return {
            "status": "TEMPORARILY_UNAVAILABLE",
            "is_temporarily_unavailable": True,
            "message": temporary_unavailability_message,
            "timezone": timezone_str,
            "local_time": local_time_str,
            "next_status_change": None,
        }

    today_hours = schedule.get(current_weekday)
    if not today_hours:
        return {
            "status": "CLOSED",
            "is_temporarily_unavailable": False,
            "message": None,
            "timezone": timezone_str,
            "local_time": local_time_str,
            "next_status_change": None,
        }

    is_closed = today_hours.is_closed if hasattr(today_hours, "is_closed") else today_hours["is_closed"]
    opening_time = today_hours.opening_time if hasattr(today_hours, "opening_time") else today_hours.get("opening_time")
    closing_time = today_hours.closing_time if hasattr(today_hours, "closing_time") else today_hours.get("closing_time")

    if not is_closed and opening_time and closing_time and opening_time <= current_time < closing_time:
        # Currently OPEN
        close_dt = datetime.combine(now_local.date(), closing_time, tzinfo=tz)
        return {
            "status": "OPEN",
            "is_temporarily_unavailable": False,
            "message": None,
            "timezone": timezone_str,
            "local_time": local_time_str,
            "next_status_change": close_dt.isoformat(),
        }

    # Currently CLOSED -> calculate next opening time
    next_opening_dt: datetime | None = None

    # Check if opens later today
    if not is_closed and opening_time and current_time < opening_time:
        next_opening_dt = datetime.combine(now_local.date(), opening_time, tzinfo=tz)
    else:
        # Look ahead for up to 7 days
        for i in range(1, 8):
            next_date = now_local.date() + timedelta(days=i)
            day_num = next_date.isoweekday()
            day_entry = schedule.get(day_num)
            if not day_entry:
                continue
            entry_closed = day_entry.is_closed if hasattr(day_entry, "is_closed") else day_entry["is_closed"]
            entry_open = day_entry.opening_time if hasattr(day_entry, "opening_time") else day_entry.get("opening_time")
            if not entry_closed and entry_open:
                next_opening_dt = datetime.combine(next_date, entry_open, tzinfo=tz)
                break

    return {
        "status": "CLOSED",
        "is_temporarily_unavailable": False,
        "message": None,
        "timezone": timezone_str,
        "local_time": local_time_str,
        "next_status_change": next_opening_dt.isoformat() if next_opening_dt else None,
    }

