import requests
import logging
from datetime import datetime, timedelta
import pytz

def get_utc_offset(timezone):
    local_timezone = pytz.timezone(timezone)
    utc_offset = datetime.now(local_timezone).utcoffset()
    return int(utc_offset.total_seconds() / 3600)

def get_data(lat, lng, timezone):
    utc_offset = get_utc_offset(timezone)
    url = "https://aa.usno.navy.mil/api/rstt/oneday"
    params = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'coords': f'{lat},{lng}',
        'tz': utc_offset
    }
    response = requests.get(url, params=params)
    data = response.json()

    if 'error' in data:
        logging.error("Error fetching data from USNO API")
    
    return data

def parse_time(time_str, timezone):
    local_timezone = pytz.timezone(timezone)
    time_parts = time_str.split(':')
    now = datetime.now()
    parsed_time = local_timezone.localize(datetime(now.year, now.month, now.day, int(time_parts[0]), int(time_parts[1])))
    return parsed_time

def is_before_sunset(lat, lng, minutes, timezone):
    try:
        data = get_data(lat, lng, timezone)

        if not data:
            logging.error("No data from USNO API")
            return False, 0

        sunset_str = data['properties']['data']['sundata'][3]['time']  # Assuming 'Set' is the fourth entry in 'sundata'
        sunset_time_local = parse_time(sunset_str, timezone)
        current_time_local = datetime.now(pytz.timezone(timezone))
        
        if current_time_local < sunset_time_local - timedelta(minutes=minutes):
            return True, max(0, (sunset_time_local - current_time_local).total_seconds() / 60)
        else:
            next_sunrise_str = data['properties']['data']['sundata'][1]['time']  # Assuming 'Rise' is the second entry in 'sundata'
            next_sunrise_time_local = parse_time(next_sunrise_str, timezone) + timedelta(days=1)
            return current_time_local < next_sunrise_time_local, max(0, (sunset_time_local - current_time_local).total_seconds() / 60)
    except Exception as e:
        logging.error(f"Error in is_before_sunset: {e}")
        return False, 0

def is_past_sunrise(lat, lng, minutes, timezone):
    try:
        data = get_data(lat, lng, timezone)

        if not data:
            logging.error("No data from USNO API")
            return False

        sunrise_str = data['properties']['data']['sundata'][1]['time']  # Assuming 'Rise' is the second entry in 'sundata'
        sunrise_time_local = parse_time(sunrise_str, timezone)
        current_time_local = datetime.now(pytz.timezone(timezone))
        time_after_sunrise = sunrise_time_local + timedelta(minutes=minutes)

        before_sunset, _ = is_before_sunset(lat, lng, minutes, timezone)

        return current_time_local >= time_after_sunrise and not before_sunset
    except Exception as e:
        logging.error(f"Error in is_past_sunrise: {e}")
        return False