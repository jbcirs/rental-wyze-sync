import logging
import os
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from brands.smartthings.smartthings import *

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'


def sync(thermostat, mode, cool_temp, heat_temp, property_name, location, reservations, current_time):
    logging.info(f'Processing SmartThings {Device.THERMOSTAT.value} reservations.')
    updates = []
    errors = []

    try:
        thermostat_name = thermostat['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            send_slack_message(f"Unable to fetch location ID for {thermostat_name} at {property_name}.")
            return

        thermostat_id = get_device_id_by_label(location_id,thermostat_name)

        if thermostat_id is None:
            send_slack_message(f"Unable to fetch {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}.")
            return

        if set_thermostat(thermostat_id,thermostat_name, mode, cool_temp, heat_temp):
            logging.info(f"Set {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")
            updates.append(f"{Device.THERMOSTAT.value} {property_name} - {thermostat_name}")
        else:
            errors.append(f"Switching {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}")
        


    except Exception as e:
        error = f"Error in SmatThings {Device.THERMOSTAT.value} function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmatThings {Device.THERMOSTAT.value} function: {str(e)}")

    return updates, errors