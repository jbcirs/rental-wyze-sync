from devices import Device
from slack_notify import send_slack_message
from brands.smartthings.smartthings import *

def sync(thermostat, mode, cool_temp, heat_temp, property_name, location):
    """
    Synchronize SmartThings thermostat settings with desired configuration.
    
    Args:
        thermostat: Thermostat configuration dictionary
        mode: Desired thermostat mode (heat, cool, auto)
        cool_temp: Desired cooling temperature setpoint
        heat_temp: Desired heating temperature setpoint
        property_name: Name of the property for logging purposes
        location: Location name for SmartThings
        
    Returns:
        Tuple of (updates, errors) lists tracking successful and failed operations
    """
    logger.info(f'Processing SmartThings {Device.THERMOSTAT.value} reservations.')
    updates = []
    errors = []
    # Skip flags to track if individual operations can be skipped
    skip_successful_mode = False 
    skip_successful_temp = False
    skip_successful_fan = False

    try:
        # Validate input data
        if not thermostat or 'name' not in thermostat:
            error_msg = f"🔍 Missing Data: Thermostat configuration is missing or invalid for `{property_name}`."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        thermostat_name = thermostat['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            error_msg = f"❓ Location Not Found: Unable to fetch location ID for `{location}` when configuring thermostat at `{property_name}`."
            send_slack_message(error_msg)
            errors.append(error_msg)
            return updates, errors

        thermostat_id = get_device_id_by_label(location_id, thermostat_name)

        if thermostat_id is None:
            error_msg = f"❓ Device Not Found: Unable to fetch {Device.THERMOSTAT.value} `{thermostat_name}` at `{property_name}`. Please verify the device is online and correctly named."
            send_slack_message(error_msg)
            errors.append(error_msg)
            return updates, errors

        # Check if thermostat needs updating by comparing current and desired settings
        # Using refresh to ensure we get the latest data from the physical thermostat (e.g., Ecobee)
        status_result = thermostat_needs_updating(thermostat_id, mode, cool_temp, heat_temp)
        
        if status_result is None:
            error_msg = f"🌡️ Thermostat Status Error: Unable to retrieve current status for `{thermostat_name}` at `{property_name}`. The device may be offline or experiencing connectivity issues."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        needs_update, current_settings = status_result

        # Create detailed status change messages for Slack
        status_changes = []

        if needs_update:
            current_temperature = current_settings.get('current_temp') if current_settings else 'Unknown'
            
            # Build change details for Slack notification
            if current_settings:
                current_mode = current_settings.get('mode')
                current_cool = current_settings.get('cool_temp')
                current_heat = current_settings.get('heat_temp')
                current_fan = current_settings.get('fan_mode')
                
                if current_mode != mode:
                    status_changes.append(f"Mode: {current_mode} → {mode}")
                if current_cool != cool_temp:
                    status_changes.append(f"Cool: {current_cool}°F → {cool_temp}°F")
                if current_heat != heat_temp:
                    status_changes.append(f"Heat: {current_heat}°F → {heat_temp}°F")
                if current_fan != "auto":
                    status_changes.append(f"Fan: {current_fan} → auto")
            
            update_successful, api_status_changes = set_thermostat(thermostat_id, thermostat_name, mode, cool_temp, heat_temp)
            
            if update_successful:
                update_msg = f"🌡️ Updated {Device.THERMOSTAT.value} `{thermostat_name}` at `{property_name}`"
                update_msg += f"\nCurrent Temperature: {current_temperature}°F"
                if status_changes:
                    update_msg += "\nChanges Made:\n• " + "\n• ".join(status_changes)
                logger.info(update_msg)
                updates.append(f"{Device.THERMOSTAT.value} {property_name} - {thermostat_name}")
                # Send detailed status change to Slack
                send_slack_message(update_msg)
            else:
                error_msg = f"⚠️ Failed to update {Device.THERMOSTAT.value} `{thermostat_name}` at `{property_name}`"
                logger.error(error_msg)
                errors.append(f"Updating {Device.THERMOSTAT.value} for {thermostat_name} at {property_name}")
                send_slack_message(error_msg)
        else:
            logger.info(f"No update needed for {Device.THERMOSTAT.value} {thermostat_name} at {property_name}")

    except Exception as e:
        error_msg = f"❌ Unexpected Error in SmartThings {Device.THERMOSTAT.value} function for `{property_name}`: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        send_slack_message(error_msg)

    return updates, errors

def thermostat_needs_updating(thermostat_id, mode, cool_temp, heat_temp, fan_mode="auto"):
    """
    Check if thermostat settings need to be updated by comparing current and desired states.
    Forces a refresh to ensure we get the latest data from the physical device.
    
    Args:
        thermostat_id: ID of the thermostat device
        mode: Desired thermostat mode
        cool_temp: Desired cooling temperature
        heat_temp: Desired heating temperature
        fan_mode: Desired fan mode (defaults to "auto")
        
    Returns:
        Tuple containing update status and current settings if update is needed,
        or None if there was an error retrieving the status
    """
    try:
        # Force refresh to get latest data from the physical thermostat (e.g., Ecobee)
        status = get_device_status_with_refresh(thermostat_id, force_refresh=True)
        if not status:
            logger.error(f"🌡️ Thermostat Status Error: Failed to get status for device {thermostat_id}.")
            return None
            
        # Extract current settings
        try:
            thermostat_mode = status['components']['main']['thermostatMode']['thermostatMode']['value']
            thermostat_fan_mode = status['components']['main']['thermostatFanMode']['thermostatFanMode']['value']
            current_temperature = status['components']['main']['temperatureMeasurement']['temperature']['value']
            heating_setpoint = status['components']['main']['thermostatHeatingSetpoint']['heatingSetpoint']['value']
            cooling_setpoint = status['components']['main']['thermostatCoolingSetpoint']['coolingSetpoint']['value']
            
            # Create current settings dictionary for comparison and reporting
            current_settings = {
                'mode': thermostat_mode,
                'cool_temp': cooling_setpoint,
                'heat_temp': heating_setpoint,
                'fan_mode': thermostat_fan_mode,
                'current_temp': current_temperature
            }
            
        except KeyError as e:
            logger.error(f"🔍 Data Error: Missing attribute in thermostat status for device {thermostat_id}. Error: {str(e)}")
            return None
        
        # Log current and desired settings for comparison
        logger.info(f"Current Temperature: {current_temperature}")
        logger.info(f"Current Mode: {thermostat_mode} Should Be: {mode}")
        logger.info(f"Current Fan Mode: {thermostat_fan_mode} Should Be: {fan_mode}")
        logger.info(f"Current Heating Setpoint: {heating_setpoint}°F Should Be: {heat_temp}°F")
        logger.info(f"Current Cooling Setpoint: {cooling_setpoint}°F Should Be: {cool_temp}°F")

        # Compare current and desired settings to determine if update is needed
        if (thermostat_mode == mode and
            thermostat_fan_mode == fan_mode and
            heating_setpoint == heat_temp and
            cooling_setpoint == cool_temp):
            return False, current_settings
        
        return True, current_settings
        
    except Exception as e:
        logger.error(f"❌ Unexpected Error checking thermostat status for device {thermostat_id}: {str(e)}")
        return None
