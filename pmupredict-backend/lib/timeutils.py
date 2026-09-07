from __future__ import annotations
import os
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Paris")
TZ = ZoneInfo(APP_TIMEZONE)

def now_local() -> datetime:
    return datetime.now(TZ)

def today_local() -> date:
    return now_local().date()

def iso_today() -> str:
    return today_local().isoformat()

def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt=value
    else:
        text=str(value).replace("Z", "+00:00")
        try:
            dt=datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)
