import datetime
from time import gmtime


def formatted_cet_date_time() -> str:
    t = gmtime()
    u = datetime.datetime(t[0], t[1], t[2], t[3], t[4], t[5])
    c = utc_to_cet(u)
    return f"{c.year}/{c.month:02}/{c.day:02}-{c.hour:02}:{c.minute:02}:{c.second:02}"


# DeepSeek wrote this
def get_last_sunday(y, month):
    # Returns the last Sunday of March/October for the given year
    if month == 3:
        last_day = datetime.date(y, 3, 31)  # March has 31 days
    elif month == 10:
        last_day = datetime.date(y, 10, 31)  # October has 31 days
    else:
        raise ValueError("Month must be 3 (March) or 10 (October)")
    # Calculate days to subtract to reach the last Sunday
    offset = (last_day.weekday() - 6) % 7  # weekday() is 0 (Mon) to 6 (Sun)
    return last_day - datetime.timedelta(days=offset)


def utc_to_cet(utc_time):
    # Ensure input is a naive datetime assumed to be in UTC
    year = utc_time.year

    # Get transition dates for the year (as naive UTC datetimes)
    last_sun_mar = get_last_sunday(year, 3)
    last_sun_oct = get_last_sunday(year, 10)

    # DST starts at 01:00 UTC on last Sunday of March
    start_dst = datetime.datetime(year, 3, last_sun_mar.day, 1, 0)
    # DST ends at 01:00 UTC on last Sunday of October
    end_dst = datetime.datetime(year, 10, last_sun_oct.day, 1, 0)
    # Check if the datetime is in DST period
    if start_dst <= utc_time < end_dst:
        return utc_time + datetime.timedelta(hours=2)  # CEST (UTC+2)
    else:
        return utc_time + datetime.timedelta(hours=1)  # CET (UTC+1)
