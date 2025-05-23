"""
Interface with the US Naval Observatory API to get sunrise and sunset data.
Used to determine natural lighting conditions for controlling smart lights.
"""
import os
import requests
from logger import Logger
from datetime import datetime, timedelta
import pytz

# Default offset minutes (can be overridden)
MINUTES_OFFSET_SUNSET = 0
MINUTES_OFFSET_SUNRISE = 0
TIMEZONE = os.environ['TIMEZONE']

logger = Logger()

def set_offset_minutes(sunset_minutes, sunrise_minutes):
    """
    Set global offset minutes for sunset and sunrise times.
    
    Args:
        sunset_minutes: Minutes to offset sunset time (positive = later)
        sunrise_minutes: Minutes to offset sunrise time (positive = later)
    """
    global MINUTES_OFFSET_SUNSET
    global MINUTES_OFFSET_SUNRISE
    # Make sure we handle None values properly
    MINUTES_OFFSET_SUNSET = sunset_minutes if sunset_minutes is not None else 0
    MINUTES_OFFSET_SUNRISE = sunrise_minutes if sunrise_minutes is not None else 0
    logger.info(f"Set sunset offset to {MINUTES_OFFSET_SUNSET} minutes and sunrise offset to {MINUTES_OFFSET_SUNRISE} minutes")

def get_utc_offset():
    """
    Get the UTC offset for the configured timezone in hours.
    
    Returns:
        Integer representing hours offset from UTC
    """
    local_timezone = pytz.timezone(TIMEZONE)
    utc_offset = datetime.now(local_timezone).utcoffset()
    return int(utc_offset.total_seconds() / 3600)

def get_data(lat, lng):
    """
    Fetch sunrise/sunset data from the USNO API for a specific location.
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        
    Returns:
        Dictionary of astronomical data including sunrise and sunset times
    """
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
    """
    Parse a time string (HH:MM) into a timezone-aware datetime for today.
    
    Args:
        time_str: Time string in format "HH:MM"
        
    Returns:
        Timezone-aware datetime for today with the specified time
    """
    local_timezone = pytz.timezone(TIMEZONE)
    time_parts = time_str.split(':')
    now = datetime.now()
    parsed_time = local_timezone.localize(datetime(now.year, now.month, now.day, int(time_parts[0]), int(time_parts[1])))
    return parsed_time

def sunset(data):
    """
    Extract and adjust the sunset time from USNO data.
    
    Args:
        data: USNO API response data
        
    Returns:
        Timezone-aware datetime representing sunset with configured offset
    """
    sunset_str = data['properties']['data']['sundata'][3]['time']
    sunset = parse_time(sunset_str)
    sunset = sunset + timedelta(minutes=MINUTES_OFFSET_SUNSET)
    return sunset

def sunrise(data):
    """
    Extract and adjust the sunrise time from USNO data.
    
    Args:
        data: USNO API response data
        
    Returns:
        Timezone-aware datetime representing sunrise with configured offset
    """
    sunrise_str =  data['properties']['data']['sundata'][1]['time']
    sunrise = parse_time(sunrise_str)
    sunrise = sunrise + timedelta(minutes=MINUTES_OFFSET_SUNRISE)
    return sunrise

def is_sunset(lat, lng, current_time_local):
    """
    Check if the current time is after sunset or before sunrise (nighttime).
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        current_time_local: Current timezone-aware datetime
        
    Returns:
        True if it's nighttime, False otherwise
    """
    try:
        data = get_data(lat, lng)

        if not data:
            logger.error("No data from USNO API")
            return False

        sunset_time = sunset(data)
        sunrise_time = sunrise(data)

        # It's night if we're after sunset or before sunrise
        if current_time_local >= sunset_time or current_time_local < sunrise_time:
            return True
        return False

    except Exception as e:
        logger.error(f"Error in is_sunset: {e}")
        return False

def is_sunrise(lat, lng, current_time_local):
    """
    Check if the current time is after sunrise and before sunset (daytime).
    
    Args:
        lat: Latitude coordinate
        lng: Longitude coordinate
        current_time_local: Current timezone-aware datetime
        
    Returns:
        True if it's daytime, False otherwise
    """
    try:
        data = get_data(lat, lng)

        if not data:
            logger.error("No data from USNO API")
            return False

        sunset_time = sunset(data)
        sunrise_time = sunrise(data)

        # It's day if we're after sunrise and before sunset
        if current_time_local >= sunrise_time and current_time_local < sunset_time:
            return True
        return False
    except Exception as e:
        logger.error(f"Error in is_sunrise: {e}")
        return False
