import os
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from brands.wyze.wyze import *
from wyze_sdk import Client

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'

def get_current_device_settings_from_config(thermostat, wyze_client, target_mode, target_cool, target_heat):
    """
    Get current Wyze thermostat settings with client management.
    This function handles Wyze client setup and routes to the device communication function.
    
    Args:
        thermostat: Thermostat configuration dictionary
        wyze_client: Optional Wyze client to avoid re-authentication
        target_mode: Target mode (used for comparison)
        target_cool: Target cooling temperature (used for comparison)
        target_heat: Target heating temperature (used for comparison)
        
    Returns:
        Tuple of (current_mode, current_cool_temp, current_heat_temp) or (target_mode, target_cool, target_heat) if unable to read
    """
    try:
        # Use provided client or create new one
        if wyze_client is None:
            wyze_token = get_wyze_token()
            if not wyze_token:
                logger.warning(f"Could not get Wyze token for {thermostat.get('name', 'Unknown')}")
                return target_mode, target_cool, target_heat
            wyze_client = Client(token=wyze_token)
        
        return get_current_device_settings(
            thermostat, wyze_client.thermostats, target_mode, target_cool, target_heat
        )
        
    except Exception as e:
        logger.warning(f"Error reading Wyze device settings for {thermostat.get('name', 'Unknown')}: {str(e)}")
        return target_mode, target_cool, target_heat

def get_current_device_settings(thermostat, wyze_client, target_mode, target_cool, target_heat):
    """
    Get current Wyze thermostat settings from the physical device.
    
    Args:
        thermostat: Thermostat configuration dictionary
        wyze_client: Wyze API client
        target_mode: Target mode (used for comparison)
        target_cool: Target cooling temperature (used for comparison)
        target_heat: Target heating temperature (used for comparison)
        
    Returns:
        Tuple of (current_mode, current_cool_temp, current_heat_temp) or (target_mode, target_cool, target_heat) if unable to read
    """
    try:
        wyze_device = wyze_client.info(
            device_mac=thermostat['mac'], device_model=thermostat['model']
        )
        
        if not wyze_device:
            logger.warning(f"Could not get Wyze device info for {thermostat.get('name', 'Unknown')}")
            return target_mode, target_cool, target_heat
        
        status_result = thermostat_needs_updating(
            wyze_client, wyze_device, target_mode, target_cool, target_heat, 'home'
        )
        
        if status_result and len(status_result) >= 8:
            needs_update, current_temperature, thermostat_humidity, thermostat_mode, thermostat_fan_mode, heating_setpoint, cooling_setpoint, thermostat_scenario = status_result
            if heating_setpoint is not None and cooling_setpoint is not None:
                current_mode = thermostat_mode.value[1] if hasattr(thermostat_mode, 'value') else str(thermostat_mode)
                logger.info(f"Read Wyze device settings for {thermostat['name']}: Mode={current_mode}, Cool={cooling_setpoint}°F, Heat={heating_setpoint}°F")
                return current_mode, cooling_setpoint, heating_setpoint
        
        return target_mode, target_cool, target_heat
        
    except Exception as e:
        logger.warning(f"Error reading Wyze device settings for {thermostat.get('name', 'Unknown')}: {str(e)}")
        return target_mode, target_cool, target_heat

def sync(client, thermostat, mode, cool_temp, heat_temp, scenario, property_name):
    """
    Synchronize Wyze thermostat settings with desired configuration.
    
    Args:
        client: Wyze API client
        thermostat: Thermostat device dictionary
        mode: Desired thermostat mode (heat, cool, auto)
        cool_temp: Desired cooling temperature setpoint
        heat_temp: Desired heating temperature setpoint
        scenario: Desired thermostat scenario (home, away, sleep)
        property_name: Name of the property for logging purposes
        
    Returns:
        Tuple of (updates, errors) lists tracking successful and failed operations
    """
    logger.info(f'Processing Wyze {Device.THERMOSTAT.value} reservations.')
    updates = []
    errors = []
    # Skip flags to track if individual operations can be skipped
    skip_successful_mode = False 
    skip_successful_temp = False
    skip_successful_fan = False
    skip_successful_scenario = False

    try:
        # Validate input data
        if not thermostat or 'name' not in thermostat:
            error_msg = f"🔍 Missing Data: Thermostat configuration is missing or invalid for `{property_name}`."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        # Retrieve the thermostat device from Wyze
        thermostat_name = thermostat['name']
        thermostat_device = get_device_by_name(client, thermostat_name)

        if thermostat_device is None:
            error_msg = f"❓ Device Not Found: Unable to fetch {Device.THERMOSTAT.value} `{thermostat_name}` at `{property_name}`. Please verify the device is online and correctly named."
            send_slack_message(error_msg)
            errors.append(error_msg)
            return updates, errors

        # Check if thermostat needs updating by comparing current and desired settings
        status_result = thermostat_needs_updating(client, thermostat_device, mode, cool_temp, heat_temp, scenario)
        
        if status_result is None:
            error_msg = f"🌡️ Thermostat Status Error: Unable to retrieve current status for `{thermostat_name}` at `{property_name}`. The device may be offline or experiencing connectivity issues."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        needs_update, current_temperature, thermostat_humidity, thermostat_mode, thermostat_fan_mode, heating_setpoint, cooling_setpoint, thermostat_scenario = status_result

        # Create detailed status change messages for Slack
        status_changes = []

        if needs_update:
            # Update scenario if needed
            if thermostat_scenario != map_to_thermostat_scenario(scenario):
                logger.info("Update Scenario")
                scenario_change = f"Scenario: {thermostat_scenario} → {scenario}"
                status_changes.append(scenario_change)
                update_successful_scenario = set_thermostat_scenario(client, thermostat_device, scenario)
            else:
                logger.info("Scenario already set")
                skip_successful_scenario = True
                update_successful_scenario = True

            # Update thermostat mode if needed
            if thermostat_mode != map_to_thermostat_mode(mode):
                logger.info("Update Thermostat mode")
                mode_change = f"Mode: {thermostat_mode.value[1]} → {mode}"
                status_changes.append(mode_change)
                update_successful_mode = set_thermostat_system_mode(client, thermostat_device, mode)
            else:
                logger.info("Thermostat mode already set")
                skip_successful_mode = True
                update_successful_mode = True
            
            # Update temperature setpoints if needed
            if int(heat_temp) != int(heating_setpoint) or int(cool_temp) != int(cooling_setpoint):
                logger.info("Update temperatures")
                temp_change = f"Temp: Heat {heating_setpoint}°F → {heat_temp}°F, Cool {cooling_setpoint}°F → {cool_temp}°F"
                status_changes.append(temp_change)
                update_successful_temp = set_thermostat_temperature(client, thermostat_device, heat_temp, cool_temp)
            else:
                logger.info("Temperature already set")
                skip_successful_temp = True
                update_successful_temp = True
            
            # Update fan mode if needed (always set to auto)
            if thermostat_fan_mode != map_to_fan_mode("auto"):
                logger.info("Update fan mode")
                fan_change = f"Fan: {thermostat_fan_mode.value[1]} → auto"
                status_changes.append(fan_change)
                update_successful_fan = set_thermostat_fan_mode(client, thermostat_device)
            else:
                logger.info("Fan mode already set")
                skip_successful_fan = True
                update_successful_fan = True

            # Log outcome based on operation results
            if skip_successful_mode and skip_successful_temp and skip_successful_fan and skip_successful_scenario:
                logger.info(f"Skipping, no update needed for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")
                
            elif update_successful_mode and update_successful_temp and update_successful_fan and update_successful_scenario:
                update_msg = f"🌡️ Updated {Device.THERMOSTAT.value} `{thermostat_name}` at `{property_name}`"
                update_msg += f"\nCurrent Temperature: {current_temperature}°F"
                if status_changes:
                    update_msg += "\nChanges Made:\n• " + "\n• ".join(status_changes)
                logger.info(update_msg)
                updates.append(f"{Device.THERMOSTAT.value} {property_name} - {thermostat_name}")
                # Send detailed status change to Slack
                send_slack_message(update_msg)
            else:
                error_msg = f"⚠️ Partial update failure for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}:"
                error_msg += f"\nMode update: {'✅' if update_successful_mode else '❌'}"
                error_msg += f"\nTemp update: {'✅' if update_successful_temp else '❌'}"
                error_msg += f"\nFan update: {'✅' if update_successful_fan else '❌'}"
                error_msg += f"\nScenario update: {'✅' if update_successful_scenario else '❌'}"
                logger.error(error_msg)
                errors.append(f"Updating {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}")
                send_slack_message(error_msg)
        else:
            logger.info(f"No update needed for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")

    except Exception as e:
        error_msg = f"❌ Unexpected Error in Wyze {Device.THERMOSTAT.value} function for `{property_name}`: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        send_slack_message(error_msg)

    return updates, errors

def thermostat_needs_updating(client, device, mode, cool_temp, heat_temp, scenario, fan_mode="auto"):
    """
    Check if thermostat settings need to be updated by comparing current and desired states.
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        mode: Desired thermostat mode
        cool_temp: Desired cooling temperature
        heat_temp: Desired heating temperature
        scenario: Desired thermostat scenario
        fan_mode: Desired fan mode (defaults to "auto")
        
    Returns:
        Tuple containing update status and current settings if update is needed,
        or None if there was an error retrieving the status
    """
    try:
        # Get current thermostat status
        status = get_thermostat_status(client, device)
        
        if status is None:
            logger.error(f"🌡️ Thermostat Status Error: Failed to get status for {device.nickname}.")
            return None

        # Extract current settings
        try:
            thermostat_mode = status._system_mode
            thermostat_fan_mode = status._fan_mode
            current_temperature = status._temperature
            heating_setpoint = status._heating_setpoint
            cooling_setpoint = status._cooling_setpoint
            thermostat_scenario = status.current_scenario
            thermostat_humidity = status._humidity
        except AttributeError as e:
            logger.error(f"🔍 Data Error: Missing attribute in thermostat status for {device.nickname}. Error: {str(e)}")
            return None
        
        # Log current and desired settings for comparison
        logger.info(f"Current Temperature: {current_temperature}")
        logger.info(f"Current humidity: {thermostat_humidity}")
        logger.info(f"Current Mode: {thermostat_mode} Should Be: {mode}")
        logger.info(f"Current Fan Mode: {thermostat_fan_mode} Should Be: {fan_mode}")
        logger.info(f"Current Heating Setpoint: {heating_setpoint}°F Should Be: {heat_temp}°F")
        logger.info(f"Current Cooling Setpoint: {cooling_setpoint}°F Should Be: {cool_temp}°F")
        logger.info(f"Current Scenario : {thermostat_scenario} Should Be: {scenario}")

        # Compare current and desired settings to determine if update is needed
        if (thermostat_mode.value[1] == mode and
            thermostat_fan_mode.value[1] == fan_mode and
            heating_setpoint == heat_temp and
            cooling_setpoint == cool_temp and 
            thermostat_scenario == scenario):
            return False, None, None, None, None, None, None, None
        
        return True, current_temperature, thermostat_humidity, thermostat_mode, thermostat_fan_mode, heating_setpoint, cooling_setpoint, thermostat_scenario
    
    except Exception as e:
        logger.error(f"❌ Unexpected Error checking thermostat status for {device.nickname}: {str(e)}")
        return None
