import os
from devices import Device
from slack_notify import send_slack_message
from brands.smartthings.smartthings import *

# Configuration
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']

def sync(light, property_name, location, desired_state):
    """
    Synchronize SmartThings light state with desired configuration.
    
    Args:
        light: Light configuration dictionary
        property_name: Name of the property for logging purposes
        location: Location name for SmartThings
        desired_state: Desired light state (True for on, False for off)
        
    Returns:
        Tuple of (updates, errors) lists tracking successful and failed operations
    """
    logger.info(f'Processing SmartThings {Device.LIGHTS.value} for {property_name}.')
    updates = []
    errors = []

    try:
        # Validate input data
        if not light or 'name' not in light:
            error_msg = f"🔍 Missing Data: Light configuration is missing or invalid for '{property_name}'."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        light_name = light['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            error_msg = f"❓ Location Not Found: Unable to fetch location ID for '{location}' when configuring light at '{property_name}'."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors

        light_id = get_device_id_by_label(location_id, light_name)

        if light_id is None:
            error_msg = f"❓ Device Not Found: Unable to fetch {Device.LIGHTS.value} '{light_name}' at '{property_name}'. Please verify the device is online and correctly named."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors

        # Get current light state to check if update is needed
        current_state = get_current_light_state(light_id)
        
        if current_state is None:
            error_msg = f"💡 Light Status Error: Unable to retrieve current status for '{light_name}' at '{property_name}'. The device may be offline or experiencing connectivity issues."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(error_msg)
            return updates, errors
            
        # Only update if the current state differs from desired state
        if current_state != desired_state:
            state_desc = "ON" if desired_state else "OFF"
            prev_state_desc = "ON" if current_state else "OFF"
            
            # Use the existing switch function from smartthings.py
            success = switch(light_id, desired_state)
            
            if success:
                update_msg = f"💡 Updated {Device.LIGHTS.value} '{light_name}' at '{property_name}': {prev_state_desc} → {state_desc}"
                logger.info(update_msg)
                updates.append(f"{Device.LIGHTS.value} {property_name} - {light_name}: {state_desc}")
                send_slack_message(update_msg)
            else:
                error_msg = f"⚠️ Failed to update {Device.LIGHTS.value} '{light_name}' at '{property_name}' to {state_desc}"
                logger.error(error_msg)
                errors.append(error_msg)
                send_slack_message(error_msg)
        else:
            state_desc = "ON" if desired_state else "OFF"
            logger.info(f"No update needed for {Device.LIGHTS.value} '{light_name}' at '{property_name}' - already {state_desc}")

    except Exception as e:
        error_msg = f"❌ Unexpected Error in SmartThings {Device.LIGHTS.value} function for '{property_name}': {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        send_slack_message(error_msg)

    return updates, errors

def get_current_light_state(light_id):
    """
    Get the current state of a light (on/off).
    
    Args:
        light_id: ID of the light device
        
    Returns:
        bool: True if light is on, False if off, None if error
    """
    try:
        status = get_device_status(light_id)
        if not status:
            logger.error(f"💡 Light Status Error: Failed to get status for device {light_id}.")
            return None
            
        # Extract current state
        try:
            switch_state = status['components']['main']['switch']['switch']['value']
            return switch_state == 'on'
        except KeyError as e:
            logger.error(f"🔍 Data Error: Missing attribute in light status. Error: {str(e)}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Unexpected Error checking light status: {str(e)}")
        return None
