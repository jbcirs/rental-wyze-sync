"""
Light control logic for managing smart lights based on time of day,
sunrise/sunset, and reservation status.
"""
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
    """
    Determine if a light should be on based on its scheduled time window.
    
    Args:
        start_time_str: Start time string in format "HH:MM" or None
        stop_time_str: Stop time string in format "HH:MM" or None
        current_time: Current timezone-aware datetime
        
    Returns:
        Boolean indicating if the light should be on
    """
    # Case 1: Both start and stop times are defined
    if start_time_str is not None and stop_time_str is not None:
        start_time = parse_local_time(start_time_str, current_time.tzinfo.zone)
        stop_time = parse_local_time(stop_time_str, current_time.tzinfo.zone)
        return start_time <= current_time < stop_time
    # Case 2: Only start time is defined (turn on after start time)
    elif start_time_str is not None:
        start_time = parse_local_time(start_time_str, current_time.tzinfo.zone)
        return start_time <= current_time
    # Case 3: Only stop time is defined (turn on until stop time)
    elif stop_time_str is not None:
        stop_time = parse_local_time(stop_time_str, current_time.tzinfo.zone)
        return current_time < stop_time
    # Case 4: No time constraints defined
    return False

def determine_light_state(light, current_time, is_night, is_day):
    """
    Determine the desired state of a light based on its configuration and current conditions.
    
    Args:
        light: Light configuration dictionary
        current_time: Current timezone-aware datetime
        is_night: Boolean indicating if it's nighttime (considering offset - after sunset_offset/before sunrise_offset)
        is_day: Boolean indicating if it's daytime (considering offset - after sunrise_offset/before sunset_offset)
        
    Returns:
        Boolean indicating desired light state (True = on, False = off)
    """
    # Check if we're past the stop time (highest priority)
    if light.get('stop_time') is not None:
        stop_time = parse_local_time(light['stop_time'], current_time.tzinfo.zone)
        if current_time >= stop_time:
            return False

    # Priority 1: Explicit start/stop time window
    if light.get('start_time') is not None or light.get('stop_time') is not None:
        if should_light_be_on(light.get('start_time'), light.get('stop_time'), current_time):
            return True
    
    # Priority 2: Sunrise/sunset with offsets (if no explicit times or they don't apply)
    # Light should be on if:
    # - It's after (sunset - minutes_before_sunset) AND before (sunrise + minutes_after_sunrise)
    # - OR if explicit times override this
    if light.get('minutes_before_sunset') is not None or light.get('minutes_after_sunrise') is not None:
        # If we have sunrise/sunset settings, use the calculated is_night (which includes offsets)
        return is_night
    
    # Default: Light should be off
    return False

def get_light_settings(light, location, reservations, current_time):
    """
    Calculate the desired light state based on reservation status, time, and location.
    
    Args:
        light: Light configuration dictionary
        location: Property location with latitude and longitude
        reservations: List of reservation data
        current_time: Current timezone-aware datetime
        
    Returns:
        Tuple of (light_state, change_state, errors)
    """
    logger.info(f'Processing {Device.LIGHT.value} reservations.')
    errors = []
    light_state = False
    change_state = False

    try:
        # Configure sunrise/sunset offsets for this light
        minutes_before_sunset = light.get('minutes_before_sunset', 0)
        minutes_after_sunrise = light.get('minutes_after_sunrise', 0)
        
        logger.info(f"Light offsets - Before sunset: {minutes_before_sunset} min, After sunrise: {minutes_after_sunrise} min")
        
        set_offset_minutes(minutes_before_sunset, minutes_after_sunrise)
        
        # Check current day/night status based on location and time with offsets
        is_night_time = is_sunset(location['latitude'], location['longitude'], current_time)
        is_day_time = is_sunrise(location['latitude'], location['longitude'], current_time)

        logger.info(f"is_night_time (with offsets): {is_night_time}")
        logger.info(f"is_day_time (with offsets): {is_day_time}")
        
        # Process based on when this light should operate
        if light['when'] == When.RESERVATIONS_ONLY.value:
            # Only consider turning on light during active reservations
            if reservations:
                for reservation in reservations:
                    checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                    checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

                    # Check if current time falls within this reservation
                    if checkin_time <= current_time < checkout_time:
                        light_state = determine_light_state(light, current_time, is_night_time, is_day_time)
                        change_state = True
                        logger.info(f"During reservation: light should be {'ON' if light_state else 'OFF'}")
                        break
                if not change_state:
                    logger.info("No active reservations - light should be OFF")
            else:
                logger.info("No reservations - light should be OFF")
        elif light['when'] == When.NON_RESERVATIONS.value:
            # Light operates during vacant periods (check if NOT in reservation)
            in_reservation = False
            if reservations:
                for reservation in reservations:
                    checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                    checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)
                    if checkin_time <= current_time < checkout_time:
                        in_reservation = True
                        break
            
            if not in_reservation:
                light_state = determine_light_state(light, current_time, is_night_time, is_day_time)
                change_state = True
                logger.info(f"Non-reservation period: light should be {'ON' if light_state else 'OFF'}")
            else:
                logger.info("During reservation - light should be OFF (non_reservations mode)")
        
        return light_state, change_state, errors

    except Exception as e:
        error = f"Error in {Device.LIGHT.value} function: {str(e)}"
        logger.error(error)
        errors.append(error)
        send_slack_message(f"Error in {Device.LIGHT.value} function: {str(e)}")

    return light_state, False, errors
