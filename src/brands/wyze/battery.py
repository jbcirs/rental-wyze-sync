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
        
        # Get device info/status using property list to get battery (P8)
        try:
            # Try to get property list which contains battery info (P8)
            property_list = client.locks.get_property_list(device_mac=lock_device.mac, device_model=lock_device.product.model)
            
            if not property_list or 'property_list' not in property_list:
                error_msg = f"Unable to get property list for Wyze lock {lock_name} at {property_name}"
                logger.error(error_msg)
                return None
            
            # Look for battery property (P8)
            battery_level = None
            for prop in property_list['property_list']:
                if prop.get('pid') == 'P8':
                    battery_level = int(prop.get('value', 0))
                    break
            
            if battery_level is None:
                error_msg = f"Battery property (P8) not found in property list for Wyze lock {lock_name} at {property_name}"
                logger.error(error_msg)
                return None
            
            logger.info(f"Retrieved battery level for Wyze lock {lock_name} at {property_name}: {battery_level}%")
            return battery_level
            
        except AttributeError as e:
            # Fallback: try the old method if get_property_list doesn't exist
            error_msg = f"get_property_list method not available in Wyze SDK. Error: {str(e)}"
            logger.warning(error_msg)
            
            # Try alternative method
            try:
                device_info = client.locks.info(device_mac=lock_device.mac, device_model=lock_device.product.model)
                if not device_info:
                    error_msg = f"Unable to get device info for Wyze lock {lock_name} at {property_name}"
                    logger.error(error_msg)
                    return None
                
                # Extract battery level - try different possible attributes
                battery_level = None
                if hasattr(device_info, 'battery_percentage'):
                    battery_level = device_info.battery_percentage
                elif hasattr(device_info, 'battery'):
                    battery_level = device_info.battery
                elif hasattr(device_info, 'power_switch'):
                    battery_level = getattr(device_info, 'power_switch', None)
                
                if battery_level is None:
                    error_msg = f"Unable to find battery information for Wyze lock {lock_name} at {property_name}"
                    logger.error(error_msg)
                    return None
                
                logger.info(f"Retrieved battery level for Wyze lock {lock_name} at {property_name}: {battery_level}%")
                return int(battery_level)
                
            except Exception as fallback_e:
                error_msg = f"Error with fallback method for Wyze lock {lock_name} at {property_name}: {str(fallback_e)}"
                logger.error(error_msg)
                return None
            
        except Exception as e:
            error_msg = f"Error getting property list for Wyze lock {lock_name} at {property_name}: {str(e)}"
            logger.error(error_msg)
            return None
            
    except Exception as e:
        error_msg = f"Error retrieving Wyze lock battery level for {lock_config.get('name', 'Unknown')} at {property_name}: {str(e)}"
        logger.error(error_msg)
        return None
