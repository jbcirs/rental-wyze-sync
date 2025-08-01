import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from logger import Logger
from slack_notify import send_slack_message

# Configuration
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']

# Default battery monitoring settings
DEFAULT_BATTERY_THRESHOLD = 30  # Alert when battery is below 30%
DEFAULT_BATTERY_WARNING_OFFSET = 15  # Warning when battery is within 15% above threshold

logger = Logger()

class BatteryMonitor:
    """
    Battery monitoring system for SmartThings and Wyze locks.
    Generates comprehensive battery reports and sends alerts for low batteries.
    """
    
    def get_all_battery_levels(self, lock_configs: List[Dict], property_name: str) -> Tuple[List[Dict], List[str]]:
        """
        Get battery levels for all configured locks and generate comprehensive report.
        
        Args:
            lock_configs: List of lock configuration dictionaries
            property_name: Name of the property for logging purposes
            
        Returns:
            Tuple of (battery_data, errors) - battery_data contains all lock info
        """
        logger.info(f'Getting battery levels for all locks at {property_name}.')
        battery_data = []
        errors = []
        
        for lock_config in lock_configs:
            try:
                # Validate lock configuration
                if not lock_config or 'brand' not in lock_config or 'name' not in lock_config:
                    error_msg = f"Invalid lock configuration for battery monitoring at {property_name}."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                
                brand = lock_config['brand']
                lock_name = lock_config['name']
                battery_threshold = lock_config.get('battery_threshold', DEFAULT_BATTERY_THRESHOLD)
                battery_warning_offset = lock_config.get('battery_warning_offset', DEFAULT_BATTERY_WARNING_OFFSET)
                
                # Calculate warning threshold (threshold + offset)
                warning_threshold = battery_threshold + battery_warning_offset
                
                # Get battery level based on brand
                battery_level = self._get_battery_level(lock_config, property_name, brand)
                
                lock_data = {
                    'name': lock_name,
                    'brand': brand,
                    'battery_level': battery_level,
                    'battery_threshold': battery_threshold,
                    'warning_threshold': warning_threshold,
                    'is_low_battery': battery_level is not None and battery_level <= battery_threshold,
                    'is_warning': battery_level is not None and battery_level > battery_threshold and battery_level <= warning_threshold,
                    'property_name': property_name
                }
                
                battery_data.append(lock_data)
                
                if battery_level is None:
                    error_msg = f"Unable to retrieve battery level for {brand} lock {lock_name} at {property_name}."
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    if lock_data['is_low_battery']:
                        status = "LOW"
                    elif lock_data['is_warning']:
                        status = "WARNING"
                    else:
                        status = "OK"
                    logger.info(f"Battery level for {brand} lock {lock_name} at {property_name}: {battery_level}% ({status})")
                    
            except Exception as e:
                error_msg = f"Unexpected error checking battery for lock {lock_config.get('name', 'Unknown')} at {property_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
        
        return battery_data, errors
    
    def send_battery_report(self, all_battery_data: List[Dict], property_name: str) -> bool:
        """
        Send comprehensive battery report to Slack with alerts at the top.
        
        Args:
            all_battery_data: List of battery data for all locks
            property_name: Property name for the report
            
        Returns:
            bool: True if report was sent successfully, False otherwise
        """
        try:
            # Filter locks for this property
            property_locks = [lock for lock in all_battery_data if lock['property_name'] == property_name]
            
            if not property_locks:
                logger.info(f"No locks found for property {property_name}")
                return True
            
            # Separate low battery alerts and warnings from general status
            low_battery_locks = [lock for lock in property_locks if lock['is_low_battery'] and lock['battery_level'] is not None]
            warning_locks = [lock for lock in property_locks if lock['is_warning'] and lock['battery_level'] is not None]
            
            # Build Slack message
            message_parts = []
            
            # Add critical alerts at the top if any
            if low_battery_locks:
                message_parts.append(f"🚨 **LOW BATTERY ALERTS for {property_name}** 🚨")
                for lock in low_battery_locks:
                    alert_line = f"⚠️ {lock['brand'].title()} lock `{lock['name']}`: **{lock['battery_level']}%** (threshold: {lock['battery_threshold']}%)"
                    message_parts.append(alert_line)
                message_parts.append("")  # Empty line separator
            
            # Add warning alerts if any
            if warning_locks:
                message_parts.append(f"⚠️ **BATTERY WARNINGS for {property_name}** ⚠️")
                for lock in warning_locks:
                    warning_line = f"🟡 {lock['brand'].title()} lock `{lock['name']}`: **{lock['battery_level']}%** (warning at: {lock['warning_threshold']}%)"
                    message_parts.append(warning_line)
                message_parts.append("")  # Empty line separator
            
            # Add comprehensive battery status list
            message_parts.append(f"🔋 **Battery Status Report for {property_name}**")
            message_parts.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            message_parts.append("")
            
            for lock in property_locks:
                if lock['battery_level'] is not None:
                    if lock['is_low_battery']:
                        status_icon = "�"
                        status_text = "LOW"
                    elif lock['is_warning']:
                        status_icon = "🟡"
                        status_text = "WARNING"
                    else:
                        status_icon = "🟢"
                        status_text = "OK"
                    battery_line = f"{status_icon} {lock['brand'].title()} `{lock['name']}`: {lock['battery_level']}% ({status_text})"
                else:
                    battery_line = f"❌ {lock['brand'].title()} `{lock['name']}`: Unable to retrieve battery level"
                
                message_parts.append(battery_line)
            
            # Add summary footer
            total_locks = len(property_locks)
            low_battery_count = len(low_battery_locks)
            warning_count = len(warning_locks)
            message_parts.append("")
            message_parts.append(f"Summary: {total_locks} locks total, {low_battery_count} with low battery, {warning_count} with warnings")
            
            # Send the complete message
            full_message = "\n".join(message_parts)
            send_slack_message(full_message)
            
            logger.info(f"Sent battery report for {property_name}: {total_locks} locks, {low_battery_count} low battery alerts, {warning_count} warnings")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send battery report for {property_name}: {str(e)}")
            return False
    
    def _get_battery_level(self, lock_config: Dict, property_name: str, brand: str) -> Optional[int]:
        """
        Get battery level using brand-specific modules.
        
        Args:
            lock_config: Lock configuration dictionary
            property_name: Property name for logging
            brand: Lock brand (smartthings/wyze)
            
        Returns:
            int: Battery level percentage, or None if unable to retrieve
        """
        try:
            if brand.lower() == 'smartthings':
                from brands.smartthings.battery import get_battery_level
                return get_battery_level(lock_config, property_name)
            elif brand.lower() == 'wyze':
                from brands.wyze.battery import get_battery_level
                return get_battery_level(lock_config, property_name)
            else:
                error_msg = f"Unsupported brand '{brand}' for battery monitoring on lock {lock_config.get('name', 'Unknown')} at {property_name}."
                logger.error(error_msg)
                return None
                
        except ImportError as e:
            error_msg = f"Unable to import battery module for brand '{brand}': {str(e)}"
            logger.error(error_msg)
            return None
        except Exception as e:
            error_msg = f"Error getting battery level for {brand} lock {lock_config.get('name', 'Unknown')} at {property_name}: {str(e)}"
            logger.error(error_msg)
            return None


# Global battery monitor instance
battery_monitor = BatteryMonitor()


def get_all_lock_battery_levels(lock_configs: List[Dict], property_name: str) -> Tuple[List[Dict], List[str]]:
    """
    Convenience function to get all battery levels for locks.
    
    Args:
        lock_configs: List of lock configuration dictionaries
        property_name: Name of the property for logging purposes
        
    Returns:
        Tuple of (battery_data, errors) - battery_data contains all lock info
    """
    return battery_monitor.get_all_battery_levels(lock_configs, property_name)


def send_property_battery_report(all_battery_data: List[Dict], property_name: str) -> bool:
    """
    Convenience function to send battery report for a property.
    
    Args:
        all_battery_data: List of battery data for all locks
        property_name: Property name for the report
        
    Returns:
        bool: True if report was sent successfully, False otherwise
    """
    return battery_monitor.send_battery_report(all_battery_data, property_name)
