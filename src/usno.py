import os
import requests
from logger import Logger
from datetime import datetime, timedelta
import pytz

MINUTES_OFFSET_SUNSET = 0
MINUTES_OFFSET_SUNRISE = 0
TIMEZONE = os.environ['TIMEZONE']

logger = Logger()

def set_offset_minutes(sunset_minutes,sunrise_minutes):
    global MINUTES_OFFSET_SUNSET
    global MINUTES_OFFSET_SUNRISE
    MINUTES_OFFSET_SUNSET = sunset_minutes
    MINUTES_OFFSET_SUNRISE = sunrise_minutes

def get_utc_offset():
    local_timezone = pytz.timezone(TIMEZONE)
    utc_offset = datetime.now(local_timezone).utcoffset()
    return int(utc_offset.total_seconds() / 3600)

def get_data(lat, lng):
    utc_offset = get_utc_offset()
    url = "https://aa.usno.navy.mil/api/rstt/oneday"
    params = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'coords': f'{lat},{lng}',
        'tz': utc_offset
    }
    response = requests.get(url, params=params)
    data = response.json()

    if 'error' in data:
        logger.error("Error fetching data from USNO API")
    
    return data

def parse_time(time_str):
    local_timezone = pytz.timezone(TIMEZONE)
    time_parts = time_str.split(':')
    now = datetime.now()
    parsed_time = local_timezone.localize(datetime(now.year, now.month, now.day, int(time_parts[0]), int(time_parts[1])))
    return parsed_time

def sunset(data):
    sunset_str = data['properties']['data']['sundata'][3]['time']
    sunset = parse_time(sunset_str)
    sunset = sunset + timedelta(minutes=MINUTES_OFFSET_SUNSET)
    return sunset

def sunrise(data):
    sunrise_str =  data['properties']['data']['sundata'][1]['time']
    sunrise = parse_time(sunrise_str)
    sunrise = sunrise + timedelta(minutes=MINUTES_OFFSET_SUNRISE)
    return sunrise

def is_sunset(lat, lng, current_time_local):
    try:
        data = get_data(lat, lng)

        if not data:
            logger.error("No data from USNO API")
            return False

        sunset_time = sunset(data)
        sunrise_time = sunrise(data)

        if current_time_local >= sunset_time or current_time_local < sunrise_time:
            return True
        return False

    except Exception as e:
        logger.error(f"Error in is_before_sunset: {e}")
        return False

def is_sunrise(lat, lng, current_time_local):
    try:
        data = get_data(lat, lng)

        if not data:
            logger.error("No data from USNO API")
            return False

        sunset_time = sunset(data)
        sunrise_time = sunrise(data)

        if current_time_local >= sunrise_time and current_time_local < sunset_time:
            return True
        return False
    except Exception as e:
        logger.error(f"Error in is_past_sunrise: {e}")
        return False