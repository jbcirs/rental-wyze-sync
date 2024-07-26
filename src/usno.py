import requests
import logging
from datetime import datetime, timedelta
import pytz

def get_data(lat, lng):
    url = "https://api.usno.navy.mil/rstt/oneday"
    params = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'coords': f'{lat},{lng}',
        'tz': 'auto'
    }
    response = requests.get(url, params=params)
    data = response.json()

    if 'error' in data:
        logging.error("Error fetching data from USNO API")
    
    return data

def is_sun_going_down(lat, lng, minutes, timezone):
    data = get_data(lat, lng)

    if not data:
        logging.error("No data from USNO API")
        return False

    sunset_str = data['sundata'][-1]['time']  # Assuming the last entry in 'sundata' is the sunset
    sunset_time_utc = datetime.strptime(sunset_str, '%I:%M %p').replace(
        year=datetime.now().year,
        month=datetime.now().month,
        day=datetime.now().day
    )
    local_timezone = pytz.timezone(timezone)
    sunset_time_local = pytz.utc.localize(sunset_time_utc).astimezone(local_timezone)

    current_time_local = datetime.now(local_timezone)
    time_from_now = current_time_local + timedelta(minutes=minutes)

    return current_time_local <= sunset_time_local <= time_from_now

def is_sun_risen(lat, lng, minutes, timezone):
    data = get_data(lat, lng)

    if not data:
        logging.error("No data from USNO API")
        return False

    sunrise_str = data['sundata'][0]['time']  # Assuming the first entry in 'sundata' is the sunrise
    sunrise_time_utc = datetime.strptime(sunrise_str, '%I:%M %p').replace(
        year=datetime.now().year,
        month=datetime.now().month,
        day=datetime.now().day
    )
    local_timezone = pytz.timezone(timezone)
    sunrise_time_local = pytz.utc.localize(sunrise_time_utc).astimezone(local_timezone)

    current_time_local = datetime.now(local_timezone)
    time_before_now = current_time_local - timedelta(minutes=minutes)

    return time_before_now <= sunrise_time_local <= current_time_local

# Example usage
# latitude = 32.7767  # Latitude for Dallas, TX
# longitude = -96.7970  # Longitude for Dallas, TX
# minutes_to_check = 30  # Check if the sun is going down or has risen within the next/past 30 minutes
# timezone = 'America/Chicago'  # Local timezone

# if is_sun_going_down(latitude, longitude, minutes_to_check, timezone):
#     print("The sun is going down within the next 30 minutes.")
# else:
#     print("The sun is not going down within the next 30 minutes.")

# if is_sun_risen(latitude, longitude, minutes_to_check, timezone):
#     print("The sun has risen within the past 30 minutes.")
# else:
#     print("The sun has not risen within the past 30 minutes.")
