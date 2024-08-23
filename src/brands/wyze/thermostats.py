import os
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from brands.wyze.wyze import *

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'


def sync(client, thermostat, mode, cool_temp, heat_temp, property_name):
    logger.info(f'Processing SmartThings {Device.THERMOSTAT.value} reservations.')
    updates = []
    errors = []

    try:
        thermostat_name = thermostat['name']
        thermostat_device = get_device_by_name(client,thermostat_name)

        if thermostat_device is None:
            send_slack_message(f"Unable to fetch {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}.")
            return

        needs_update = thermostat_needs_updating(client, thermostat_device, mode, cool_temp, heat_temp)

        if needs_update:
            update_successful = False #set_thermostat(thermostat_id, thermostat_name, mode, cool_temp, heat_temp)
            if update_successful:
                logger.info(f"Set {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")
                updates.append(f"{Device.THERMOSTAT.value} {property_name} - {thermostat_name}")
            else:
                errors.append(f"Updating {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}")
        else:
            logger.info(f"No update needed for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")

    except Exception as e:
        error = f"Error in Wyze {Device.THERMOSTAT.value} function: {str(e)}"
        logger.error(error)
        errors.append(error)
        send_slack_message(error)

    return updates, errors

def thermostat_needs_updating(client, device, mode, cool_temp, heat_temp, fan_mode="auto"):
    status = get_thermostat_status(client,device)

    thermostat_mode = status._system_mode
    thermostat_fan_mode = status._fan_mode
    current_temperature = status._temperature
    heating_setpoint = status._heating_setpoint
    cooling_setpoint = status._cooling_setpoint

    logger.info(f"Current Temp: {current_temperature}")
    logger.info(f"Current Mode: {thermostat_mode} Should Be: {mode}")
    logger.info(f"Current Fan Mode: {thermostat_fan_mode} Should Be: {fan_mode}")
    logger.info(f"Current Heating Setpoint: {heating_setpoint}°F Should Be: {heat_temp}°F")
    logger.info(f"Current Cooling Setpoint: {cooling_setpoint}°F Should Be: {cool_temp}°F")

    if (thermostat_mode.value[1] == mode and
        thermostat_fan_mode.value[1] == fan_mode and
        heating_setpoint == heat_temp and
        cooling_setpoint == cool_temp):
        return False
    
    return True