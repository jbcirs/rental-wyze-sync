from typing import Optional, Dict
from logger import Logger
from brands.smartthings.smartthings import find_location_by_name, get_device_id_by_label, get_device_status_with_refresh

logger = Logger()

def get_battery_level(lock_config: Dict, property_name: str) -> Optional[int]:
    """
    Get battery level for a SmartThings lock.
    
    Args:
        lock_config: Lock configuration dictionary
        property_name: Property name for logging
        
    Returns:
        int: Battery level percentage, or None if unable to retrieve
    """
    try:
        lock_name = lock_config['name']
        location = lock_config.get('location')
        
        if not location:
            error_msg = f"No location specified for SmartThings lock {lock_name} at {property_name}"
            logger.error(error_msg)
            return None
        
        # Get location ID
        location_id = find_location_by_name(location)
        if not location_id:
            error_msg = f"Unable to find SmartThings location '{location}' for lock {lock_name} at {property_name}"
            logger.error(error_msg)
            return None
        
        # Get device ID
        device_id = get_device_id_by_label(location_id, lock_name)
        if not device_id:
            error_msg = f"Unable to find SmartThings lock '{lock_name}' at {property_name}"
            logger.error(error_msg)
            return None
        
        # Get device status with refresh to ensure latest data
        status = get_device_status_with_refresh(device_id, force_refresh=True)
        if not status:
            error_msg = f"Unable to get status for SmartThings lock {lock_name} at {property_name}"
            logger.error(error_msg)
            return None
        
        # Extract battery level
        try:
            battery_level = status['components']['main']['battery']['battery']['value']
            logger.info(f"Retrieved battery level for SmartThings lock {lock_name} at {property_name}: {battery_level}%")
            return int(battery_level)
        except (KeyError, ValueError) as e:
            error_msg = f"Unable to extract battery level from SmartThings lock {lock_name} status at {property_name}: {str(e)}"
            logger.error(error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Error retrieving SmartThings lock battery level for {lock_config.get('name', 'Unknown')} at {property_name}: {str(e)}"
        logger.error(error_msg)
        return None
