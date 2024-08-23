from logger import Logger
import os
from devices import Device
from slack_notify import send_slack_message
from utilty import format_datetime, parse_local_time
from usno import is_sunset, is_sunrise, set_offset_minutes
from when import When

# Configuration
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
TIMEZONE = os.environ['TIMEZONE']

logger = Logger()

def should_light_be_on(start_time_str, stop_time_str, current_time):
    if start_time_str is not None and stop_time_str is not None:
        start_time = parse_local_time(start_time_str, current_time.tzinfo.zone)
        stop_time = parse_local_time(stop_time_str, current_time.tzinfo.zone)
        return start_time <= current_time < stop_time
    elif start_time_str is not None:
        start_time = parse_local_time(start_time_str, current_time.tzinfo.zone)
        return start_time <= current_time
    elif stop_time_str is not None:
        stop_time = parse_local_time(stop_time_str, current_time.tzinfo.zone)
        return current_time < stop_time
    return False

def determine_light_state(light, current_time, before_sunset, past_sunrise):
    if light['stop_time'] is not None:
        stop_time = parse_local_time(light['stop_time'], current_time.tzinfo.zone)
        if current_time >= stop_time:
            return False

    if should_light_be_on(light['start_time'], light['stop_time'], current_time):
        return True
    elif before_sunset:
        return True
    elif past_sunrise:
        return False
    return False

def get_light_settings(light, location, reservations, current_time):
    logger.info(f'Processing {Device.LIGHT.value} reservations.')
    errors = []
    light_state = False
    change_state = False

    try:
        if light['minutes_before_sunset'] is None and  light['minutes_after_sunrise'] is None:
            set_offset_minutes(light['minutes_before_sunset'],light['minutes_after_sunrise'])

        if light['minutes_before_sunset'] is None:
            sunset = False
        else:
            sunset = is_sunset(location['latitude'], location['longitude'], current_time)
        
        if light['minutes_after_sunrise'] is None:
            sunrise = False
        else:
            sunrise = is_sunrise(location['latitude'], location['longitude'], current_time)

        logger.info(f"sunset: {sunset}")
        logger.info(f"sunrise: {sunrise}")
        
        if light['when'] == When.RESERVATIONS_ONLY.value:
            if reservations:
                for reservation in reservations:
                    checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                    checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

                    if checkin_time <= current_time < checkout_time:
                        light_state = determine_light_state(light, current_time, sunset, sunrise)
                        change_state = True
                        break
        elif light['when'] == When.NON_RESERVATIONS.value:
            light_state = determine_light_state(light, current_time, sunset, sunrise)
            change_state = True
        
        return light_state, change_state, errors

    except Exception as e:
        error = f"Error in {Device.LIGHT.value} function: {str(e)}"
        logger.error(error)
        errors.append(error)
        send_slack_message(f"Error in {Device.LIGHT.value} function: {str(e)}")

    return light_state, errors