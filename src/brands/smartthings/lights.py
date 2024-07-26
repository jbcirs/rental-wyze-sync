import logging
import os
import time
import pytz
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from utilty import format_datetime
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

def switch_light(light_id,state,light_name,property_name,updates,errors):
    if switch(light_id, state):
        logging.info(f"Switched light: {light_name} at {property_name}; ")
        updates.append(f"{Device.LIGHT} - {property_name} - {light_name}")
    else:
        errors.append(f"Switching {Device.LIGHT} for {light_name} at {property_name}")
    
    return updates, errors

def sync(light, sunset, sunrise, property_name, location, reservations, current_time):
    logging.info(f'Processing SmartThings {Device.Lights} reservations.')
    updates = []
    errors = []

    try:
        light_name = light['name']
        location_id = find_location_by_name(location)
        if location_id is None:
            send_slack_message(f"Unable to fetch location ID for {light_name} at {property_name}.")
            return
        
        light_id = get_device_id_by_name(location_id,light_name)
        if light_id is None:
            send_slack_message(f"Unable to fetch {Device.Lights} for {light_name} at {property_name}.")
            return

        if light['reservations_only']:
            # Process reservations
            for reservation in reservations:
                checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

                if checkin_time <= current_time < checkout_time:
                    if (light['start_time'] is not None and light['start_time'] >= current_time) or sunset:
                        switch_light(light_id, True, light_name, property_name, updates, errors)
                    elif (light['stop_time'] is not None and light['stop_time'] >= current_time) or sunrise:
                        switch_light(light_id, False, light_name, property_name, updates, errors)
                else:
                    switch_light(light_id, False, light_name, property_name, updates, errors)
        else:
            if (light['start_time'] is not None and light['start_time'] >= current_time) or sunset:
                switch_light(light_id, True, light_name, property_name, updates, errors)
            elif (light['stop_time'] is not None and light['stop_time'] >= current_time) or sunrise:
                switch_light(light_id, False, light_name, property_name, updates, errors)

    except Exception as e:
        error = f"Error in SmatThings {Device.LIGHT} function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmatThings {Device.LIGHT} function: {str(e)}")

    return updates, errors