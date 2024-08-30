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


def sync(client, thermostat, mode, cool_temp, heat_temp, scenario, property_name):
    logger.info(f'Processing SmartThings {Device.THERMOSTAT.value} reservations.')
    updates = []
    errors = []

    try:
        thermostat_name = thermostat['name']
        thermostat_device = get_device_by_name(client,thermostat_name)

        if thermostat_device is None:
            send_slack_message(f"Unable to fetch {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}.")
            return

        needs_update, current_temperature, thermostat_humidity, thermostat_mode, thermostat_fan_mode, heating_setpoint, cooling_setpoint, thermostat_scenario = thermostat_needs_updating(client, thermostat_device, mode, cool_temp, heat_temp, scenario)

        if needs_update:
            if thermostat_scenario != map_to_thermostat_scenario(scenario):
                logger.info("Update Scenario")
                update_successful_scenario = set_thermostat_scenario(client, thermostat_device, scenario)
            else:
                logger.info("Scenario already set")
                update_successful_scenario = True

            if thermostat_mode != map_to_thermostat_mode(mode):
                logger.info("Update Thermostat mode")
                update_successful_mode = set_thermostat_system_mode(client, thermostat_device, mode)
            else:
                logger.info("Thermostat mode already set")
                update_successful_mode = True
            
            if int(heat_temp) != int(heating_setpoint) or int(cool_temp) != int(cooling_setpoint):
                logger.info("Update tempetures")
                update_successful_temp = set_thermostat_temperature(client, thermostat_device, heat_temp, cool_temp)
            else:
                logger.info("Tempeture already set")
                update_successful_temp = True
            
            if thermostat_fan_mode != map_to_fan_mode("auto"):
                logger.info("Update fan mode")
                update_successful_fan = set_thermostat_fan_mode(client, thermostat_device)
            else:
                logger.info("Fan mode already set")
                update_successful_fan = True
                
            if update_successful_mode and update_successful_temp and update_successful_fan and update_successful_scenario:
                logger.info(f"Set {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")
                updates.append(f"{Device.THERMOSTAT.value} {property_name} - {thermostat_name}")
            else:
                logger.error(f"update_successful_mode: {update_successful_mode} ; update_successful_temp: {update_successful_temp} ; update_successful_fan: {update_successful_fan}")
                errors.append(f"Updating {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}")
        else:
            logger.info(f"No update needed for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")

    except Exception as e:
        error = f"Error in Wyze {Device.THERMOSTAT.value} function: {str(e)}"
        logger.error(error)
        errors.append(error)
        send_slack_message(error)

    return updates, errors

def thermostat_needs_updating(client, device, mode, cool_temp, heat_temp, scenario, fan_mode="auto"):
    status = get_thermostat_status(client,device)

    thermostat_mode = status._system_mode
    thermostat_fan_mode = status._fan_mode
    current_temperature = status._temperature
    heating_setpoint = status._heating_setpoint
    cooling_setpoint = status._cooling_setpoint
    thermostat_scenario = status.current_scenario
    thermostat_humidity = status._humidity 

    logger.info(f"Current Temperature: {current_temperature}")
    logger.info(f"Current humidity: {thermostat_humidity}")
    logger.info(f"Current Mode: {thermostat_mode} Should Be: {mode}")
    logger.info(f"Current Fan Mode: {thermostat_fan_mode} Should Be: {fan_mode}")
    logger.info(f"Current Heating Setpoint: {heating_setpoint}°F Should Be: {heat_temp}°F")
    logger.info(f"Current Cooling Setpoint: {cooling_setpoint}°F Should Be: {cool_temp}°F")
    logger.info(f"Current Scenario : {thermostat_scenario } Should Be: {scenario}")
    #print(vars(status))


    if (thermostat_mode.value[1] == mode and
        thermostat_fan_mode.value[1] == fan_mode and
        heating_setpoint == heat_temp and
        cooling_setpoint == cool_temp and 
        thermostat_scenario == scenario):
        return False, None, None, None, None, None, None, None
    
    return True, current_temperature, thermostat_humidity, thermostat_mode, thermostat_fan_mode, heating_setpoint, cooling_setpoint, thermostat_scenario