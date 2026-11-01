from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import exchange_calendars as xcals


def cutoff_timestamp(value=None):
    if value is None:return pd.Timestamp(datetime.now(ZoneInfo("America/Chicago"))).tz_convert("UTC")
    result=pd.Timestamp(value)
    if result.tzinfo is None:raise ValueError("--as-of requires an explicit timezone or UTC offset")
    return result.tz_convert("UTC")


def calendar():return xcals.get_calendar("XNYS")


def last_completed_session(cutoff):
    schedule=calendar().schedule
    eligible=schedule.loc[schedule["close"]<=cutoff]
    if eligible.empty:raise ValueError("No completed NYSE session in calendar range")
    return eligible.index[-1].date()


def completed_us_bar(day,cutoff):
    cal=calendar();timestamp=pd.Timestamp(day)
    if not cal.is_session(timestamp):return False
    return cal.session_close(timestamp)<=cutoff
