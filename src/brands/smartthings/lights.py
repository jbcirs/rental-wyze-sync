import logging
import os
import time
import pytz
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from utilty import format_datetime, parse_local_time
from brands.smartthings.smartthings import *
import utilty

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'


def get_switch_value(data):
    try:
        return data["components"]["main"]["switch"]["switch"]["value"]
    except KeyError:
        return None

def switch_light(light_id,state,light_name,property_name,updates,errors):
    light_status = 'on' if state else 'off'
    light = get_device_status(light_id)
    current_status = get_switch_value(light)

    if current_status is None or current_status != light_status:
        if switch(light_id, state):
            logging.info(f"Switched {Device.LIGHT.value} {light_status}: {light_name} at {property_name}")
            updates.append(f"{Device.LIGHT.value} {light_status} - {property_name} - {light_name}")
        else:
            errors.append(f"Switching {Device.LIGHT.value} for {light_name} at {property_name}")
    else:
        logging.info(f"Switch {Device.LIGHT.value} already {light_status}: {light_name} at {property_name}, no change required")
    
    return updates, errors

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

def sync(light, sunset, sunrise, property_name, location, reservations, current_time):
    logging.info(f'Processing SmartThings {Device.LIGHT.value} reservations.')
    updates = []
    errors = []
    light_state = False

    try:
        logging.info(f"sunset: {sunset}")
        logging.info(f"sunrise: {sunrise}")
        
        light_name = light['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            send_slack_message(f"Unable to fetch location ID for {light_name} at {property_name}.")
            return

        light_id = get_device_id_by_label(location_id,light_name)

        if light_id is None:
            send_slack_message(f"Unable to fetch {Device.LIGHT.value} for {light_name} at {property_name}.")
            return
        
        if light['reservations_only']:
            for reservation in reservations:
                checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

                if checkin_time <= current_time < checkout_time:
                    light_state = determine_light_state(light, current_time, sunset, sunrise)
                    break
            else:
                light_state = False
        else:
            light_state = determine_light_state(light, current_time, sunset, sunrise)

        
        switch_light(light_id, light_state, light_name, property_name, updates, errors)


    except Exception as e:
        error = f"Error in SmatThings {Device.LIGHT.value} function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmatThings {Device.LIGHT.value} function: {str(e)}")

    return updates, errors