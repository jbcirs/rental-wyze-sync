import os
import time
from devices import Device
from slack_notify import send_slack_message
from brands.smartthings.smartthings import *
from typing import Tuple, List, Optional

# Configuration
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
SMARTTHINGS_API_DELAY_SECONDS = int(os.environ.get('SMARTTHINGS_API_DELAY_SECONDS', '2'))
LIGHT_VERIFY_MAX_ATTEMPTS = int(os.environ.get('LIGHT_VERIFY_MAX_ATTEMPTS', '3'))

def _handle_error(error_msg: str, errors: List[str], send_to_slack: bool = True) -> None:
    """
    Standardized error handling for SmartThings lights operations.
    
    Args:
        error_msg: Error message to log and potentially send to Slack
        errors: List to append the error to
        send_to_slack: Whether to send error to Slack (default: True)
    """
    logger.error(error_msg)
    errors.append(error_msg)
    if send_to_slack:
        send_slack_message(error_msg)

def sync(light: dict, property_name: str, location: str, desired_state: bool) -> Tuple[List[str], List[str]]:
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
    logger.info(f'Processing SmartThings {Device.LIGHT.value} for {property_name}.')
    updates = []
    errors = []

    try:
        # Validate input data
        if not light or 'name' not in light:
            _handle_error(f"🔍 Missing Data: Light configuration is missing or invalid for `{property_name}`.", errors)
            return updates, errors
            
        light_name = light['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            _handle_error(f"❓ Location Not Found: Unable to fetch location ID for `{location}` when configuring light at `{property_name}`.", errors)
            return updates, errors

        light_id = get_device_id_by_label(location_id, light_name)

        if light_id is None:
            _handle_error(f"❓ Device Not Found: Unable to fetch {Device.LIGHT.value} `{light_name}` at `{property_name}`. Please verify the device is online and correctly named.", errors)
            return updates, errors

        # Get current light state to check if update is needed
        current_state = get_current_light_state(light_id)
        
        if current_state is None:
            _handle_error(f"💡 Light Status Error: Unable to retrieve current status for `{light_name}` at `{property_name}`. The device may be offline or experiencing connectivity issues.", errors)
            return updates, errors
            
        # Only update if the current state differs from desired state
        if current_state != desired_state:
            state_desc = "ON" if desired_state else "OFF"
            prev_state_desc = "ON" if current_state else "OFF"
            
            # Try to set the light state with retry logic
            success = False
            for attempt in range(1, LIGHT_VERIFY_MAX_ATTEMPTS + 1):
                logger.info(f"💡 Attempt {attempt} of {LIGHT_VERIFY_MAX_ATTEMPTS} to set {Device.LIGHT.value} '{light_name}' to {state_desc}")
                
                # Use the existing switch function from smartthings.py
                api_success = switch(light_id, desired_state)
                
                if api_success:
                    # Wait a moment then verify the state change
                    time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
                    
                    # Verify the light actually changed state
                    new_state = get_current_light_state(light_id)
                    if new_state == desired_state:
                        success = True
                        update_msg = f"💡 Updated {Device.LIGHT.value} `{light_name}` at `{property_name}`: {prev_state_desc} → {state_desc}"
                        if attempt > 1:
                            update_msg += f" (verified on attempt {attempt})"
                        logger.info(update_msg)
                        updates.append(f"{Device.LIGHT.value} {property_name} - {light_name}: {state_desc}")
                        send_slack_message(update_msg)
                        break
                    else:
                        logger.warning(f"⚠️ Verification failed for {Device.LIGHT.value} '{light_name}' - state is {new_state}, expected {desired_state}")
                else:
                    logger.warning(f"⚠️ API call failed for {Device.LIGHT.value} '{light_name}' attempt {attempt}")
                
                # Wait before retry if not the last attempt
                if attempt < LIGHT_VERIFY_MAX_ATTEMPTS:
                    logger.info(f"Waiting {SMARTTHINGS_API_DELAY_SECONDS} seconds before retry...")
                    time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
            
            if not success:
                _handle_error(f"⚠️ Failed to update {Device.LIGHT.value} `{light_name}` at `{property_name}` to {state_desc} after {LIGHT_VERIFY_MAX_ATTEMPTS} attempts", errors)
        else:
            state_desc = "ON" if desired_state else "OFF"
            logger.info(f"No update needed for {Device.LIGHT.value} `{light_name}` at `{property_name}` - already {state_desc}")

    except Exception as e:
        _handle_error(f"❌ Unexpected Error in SmartThings {Device.LIGHT.value} function for `{property_name}`: {str(e)}", errors)

    return updates, errors

def get_current_light_state(light_id: str) -> Optional[bool]:
    """
    Get the current state of a light (on/off) with forced refresh to ensure latest data.
    
    Args:
        light_id: ID of the light device
        
    Returns:
        bool: True if light is on, False if off, None if error
    """
    try:
        # Force refresh to get latest data from the physical light switch/device
        status = get_device_status_with_refresh(light_id, force_refresh=True)
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
