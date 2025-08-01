from typing import Optional, Dict
from logger import Logger
from brands.wyze.wyze import get_wyze_token, get_device_by_name
from wyze_sdk import Client

logger = Logger()

def get_battery_level(lock_config: Dict, property_name: str) -> Optional[int]:
    """
    Get battery level for a Wyze lock.
    
    Args:
        lock_config: Lock configuration dictionary
        property_name: Property name for logging
        
    Returns:
        int: Battery level percentage, or None if unable to retrieve
    """
    try:
        lock_name = lock_config['name']
        
        # Get Wyze client
        wyze_token = get_wyze_token()
        if not wyze_token:
            error_msg = f"Unable to get Wyze token for battery check on lock {lock_name} at {property_name}"
            logger.error(error_msg)
            return None
        
        client = Client(token=wyze_token)
        
        # Get lock device
        lock_device = get_device_by_name(client, lock_name)
        if not lock_device:
            error_msg = f"Unable to find Wyze lock '{lock_name}' at {property_name}"
            logger.error(error_msg)
            return None
        
        # Get device info/status
        try:
            device_info = client.locks.info(device_mac=lock_device.mac, device_model=lock_device.product.model)
            if not device_info:
                error_msg = f"Unable to get device info for Wyze lock {lock_name} at {property_name}"
                logger.error(error_msg)
                return None
            
            # Extract battery level - Wyze locks typically report battery as a percentage
            battery_level = None
            if hasattr(device_info, 'battery_percentage'):
                battery_level = device_info.battery_percentage
            elif hasattr(device_info, 'battery'):
                battery_level = device_info.battery
            else:
                # Try to get battery from device properties
                battery_level = getattr(device_info, 'power_switch', None)
                if battery_level is None:
                    error_msg = f"Unable to find battery information for Wyze lock {lock_name} at {property_name}"
                    logger.error(error_msg)
                    return None
            
            logger.info(f"Retrieved battery level for Wyze lock {lock_name} at {property_name}: {battery_level}%")
            return int(battery_level)
            
        except Exception as e:
            error_msg = f"Error getting device info for Wyze lock {lock_name} at {property_name}: {str(e)}"
            logger.error(error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Error retrieving Wyze lock battery level for {lock_config.get('name', 'Unknown')} at {property_name}: {str(e)}"
        logger.error(error_msg)
        return None
