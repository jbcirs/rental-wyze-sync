"""
Thermostat control logic for managing temperature settings based on weather,
reservation status, and property configuration.

This module serves as the main coordination layer for thermostat operations with
a clean, brand-agnostic architecture:

Core Functions:
- Determines optimal thermostat settings based on weather forecasts and reservations
- Routes device communication to brand-specific modules in brands/ folders  
- Handles temperature alert checking and Slack notifications
- Manages frequency controls and freeze protection logic
- Provides generic business logic while delegating brand-specific complexity

Architecture:
- Generic coordination layer with zero brand-specific configuration logic
- Clean router that dynamically imports and calls brand-specific modules
- Brand modules handle all device communication and authentication
- Template system for easy addition of new thermostat brands

Alert System:
- Monitors actual device settings (not target settings) for cost control
- Runs during reservations to catch extreme guest temperature changes
- Supports nested configuration with flexible threshold detection
- Sends formatted Slack notifications with violation details

Brand-specific device communication is handled by:
- brands/smartthings/thermostats.py - SmartThings API integration with location-based device lookup
- brands/wyze/thermostats.py - Wyze SDK integration with MAC address identification
- brands/__template__/thermostats.py - Template for implementing new brands

Functions by Category:
- Core Logic: determine_thermostat_mode(), get_comfortable_temperatures(), get_thermostat_scenario()
- Freeze Protection: check_and_override_for_freezing() 
- Frequency Control: should_process_thermostat_for_frequency()
- Brand Routing: get_current_device_settings() (generic router)
- Alert System: check_temperature_alerts_with_current_device(), check_temperature_alerts()
- Main Entry: get_thermostat_settings() (complete thermostat configuration)

Module Structure (~470 lines):
- Configuration Constants (lines 40-55)
- Core Temperature Logic (lines 60-145) 
- Frequency Control (lines 150-175)
- Brand Router (lines 180-225)
- Alert System (lines 230-430)
- Main Settings Function (lines 435-470)
"""
from weather import get_weather_forecast
from logger import Logger
from datetime import datetime, timedelta
from slack_notify import send_slack_message
from typing import List, Tuple, Optional
import os

# === Configuration Constants ===
# Global constants for thermostat operations

logger = Logger()

# Get timezone from environment variable for proper time calculations
TIMEZONE = os.environ.get('TIMEZONE', 'UTC')

# Default frequency for thermostat processing if not specified in configuration
DEFAULT_FREQUENCY = 'first_day'

# Emoji constants for Slack alert messages to improve readability and visual impact
ALERT_EMOJI_COOL = '🔵'    # Blue circle for cooling alerts
ALERT_EMOJI_HEAT = '🔴'    # Red circle for heating alerts  
ALERT_EMOJI_THERMOSTAT = '🌡️'  # Thermometer for main alert header

# === Core Temperature Logic Functions ===
# Business logic functions for determining HVAC modes, temperature settings, and scenarios
# These functions contain the core thermostat intelligence independent of any specific brand

def determine_thermostat_mode(max_temp, min_temp):
    """
    Determine the appropriate HVAC mode based on forecast temperatures.
    
    Args:
        max_temp: Maximum forecast temperature
        min_temp: Minimum forecast temperature
        
    Returns:
        String representing mode: 'cool', 'heat', or 'auto'
    """
    # Hot conditions - use cooling
    if (max_temp > 80 and min_temp > 68) or max_temp > 90:
        return 'cool'
    # Cold conditions - use heating
    elif (min_temp < 64 and max_temp < 70) or min_temp < 40:
        return 'heat'
    # Moderate conditions - use auto mode
    else:
        return 'auto'

def get_comfortable_temperatures(mode, reservation=False, temperatures=None):
    """
    Get appropriate temperature settings based on mode and reservation status.
    
    Args:
        mode: HVAC mode ('cool', 'heat', or 'auto')
        reservation: Whether there's an active reservation
        temperatures: Custom temperature settings from configuration
        
    Returns:
        Tuple of (cool_temp, heat_temp) setpoints
    """
    # Set default temperature ranges based on reservation status
    if reservation:
        # More comfortable settings when guests are present
        default_temperatures = {
            'heat': {'cool_temp': 79, 'heat_temp': 74},
            'cool': {'cool_temp': 74, 'heat_temp': 68},
            'auto': {'cool_temp': 74, 'heat_temp': 69}
        }
    else:
        # Energy-saving settings when property is vacant
        default_temperatures = {
            'heat': {'cool_temp': 85, 'heat_temp': 50},
            'cool': {'cool_temp': 85, 'heat_temp': 50},
            'auto': {'cool_temp': 85, 'heat_temp': 50}
        }

    # Override defaults with custom settings if provided
    if temperatures:
        mode_temps = next((temp for temp in temperatures if temp.get('mode') == mode), None)
        if mode_temps:
            cool_temp = mode_temps.get('cool_temp', default_temperatures[mode]['cool_temp'])
            heat_temp = mode_temps.get('heat_temp', default_temperatures[mode]['heat_temp'])
        else:
            cool_temp = default_temperatures[mode]['cool_temp']
            heat_temp = default_temperatures[mode]['heat_temp']
    else:
        cool_temp = default_temperatures[mode]['cool_temp']
        heat_temp = default_temperatures[mode]['heat_temp']
    
    return cool_temp, heat_temp

def get_thermostat_scenario(reservation):
    """
    Determine the thermostat scenario based on reservation status.
    
    Args:
        reservation: Whether there's an active reservation
        
    Returns:
        String representing scenario: 'home' or 'away'
    """
    if reservation:
        thermostat_scenario = 'home'
    else:
        thermostat_scenario = 'away'

    return thermostat_scenario

def check_and_override_for_freezing(min_temp, freeze_protection):
    """
    Check if the minimum temperature is below the freezing threshold
    and override the thermostat to heat mode to protect water pipes.
    
    Args:
        min_temp: Minimum forecast temperature
        freeze_protection: Configuration dict with freeze_temp and heat_temp settings
        
    Returns:
        Tuple of (mode, cool_temp, heat_temp) if freeze protection is needed,
        or (None, None, None) if no override is necessary
    """
    if not freeze_protection:
        return None, None, None  # No freeze protection defined; skip checking

    freezing_threshold = freeze_protection.get('freeze_temp', 32)  # Default to 32°F
    pipe_protection_heat_temp = freeze_protection.get('heat_temp', 50)  # Default to 50°F

    if min_temp <= freezing_threshold:
        logger.warning(f"Temperature is below freezing threshold of {freezing_threshold}°F. Overriding to 'heat' mode at {pipe_protection_heat_temp}°F to protect water pipes.")
        return 'heat', pipe_protection_heat_temp, pipe_protection_heat_temp

    return None, None, None

# === Frequency and Processing Control Functions ===
# Functions for controlling when thermostats should be processed based on reservation timing
# Supports 'daily' processing or 'first_day' processing to optimize API calls and energy management

def should_process_thermostat_for_frequency(temperature_config: dict, reservation_start_date: datetime.date, current_date: datetime.date) -> bool:
    """
    Determine if thermostat should be processed based on frequency setting.
    
    Args:
        temperature_config: Temperature configuration dictionary with frequency setting
        reservation_start_date: Date when the reservation started
        current_date: Current date
        
    Returns:
        Boolean indicating whether thermostat should be processed
    """
    frequency = temperature_config.get('frequency', DEFAULT_FREQUENCY)
    
    if frequency == 'daily':
        return True
    elif frequency == DEFAULT_FREQUENCY:
        # Only process on the first day of the reservation
        return current_date == reservation_start_date
    else:
        # Default to first_day behavior for unknown frequency values
        logger.warning(f"Unknown frequency value: {frequency}, defaulting to '{DEFAULT_FREQUENCY}'")
        return current_date == reservation_start_date

# === Brand Router Functions ===
# Generic routing functions for brand-agnostic device communication
# Routes calls to appropriate brand-specific modules without containing brand-specific logic
# Maintains clean separation between coordination and device communication

def get_current_device_settings(thermostat, property_config, target_mode, target_cool, target_heat, wyze_client=None):
    """
    Generic router for reading current thermostat settings from physical devices.
    Routes to brand-specific implementations without containing brand-specific logic.
    
    This function maintains clean architecture by:
    - Dynamically importing brand modules only when needed
    - Delegating all configuration parsing to brand modules  
    - Providing consistent interface regardless of brand
    - Handling errors gracefully with fallback to target settings
    
    Args:
        thermostat: Thermostat configuration dictionary with 'brand' and 'name' keys
        property_config: Property configuration with brand settings (for config-based brands)
        target_mode: Target mode for comparison/fallback ('cool', 'heat', 'auto')
        target_cool: Target cooling temperature for comparison/fallback
        target_heat: Target heating temperature for comparison/fallback
        wyze_client: Optional Wyze client to avoid re-authentication (for client-based brands)
        
    Returns:
        Tuple of (current_mode, current_cool_temp, current_heat_temp) from device,
        or (target_mode, target_cool, target_heat) if unable to read device state
        
    Brand Support:
        - 'smartthings': Routes to brands.smartthings.thermostats.get_current_device_settings_from_config()
        - 'wyze': Routes to brands.wyze.thermostats.get_current_device_settings_from_config()
        - Other brands: Returns target settings with warning (graceful degradation)
    """
    try:
        brand = thermostat.get('brand', '').lower()
        thermostat_name = thermostat.get('name', 'Unknown')
        
        if brand == 'smartthings':
            import brands.smartthings.thermostats as smartthings_thermostats
            return smartthings_thermostats.get_current_device_settings_from_config(
                thermostat, property_config, target_mode, target_cool, target_heat
            )
            
        elif brand == 'wyze':
            import brands.wyze.thermostats as wyze_thermostats
            return wyze_thermostats.get_current_device_settings_from_config(
                thermostat, wyze_client, target_mode, target_cool, target_heat
            )
            
        else:
            logger.warning(f"Unknown thermostat brand '{brand}' for {thermostat_name} - using target settings for alerts")
            return target_mode, target_cool, target_heat
            
    except Exception as e:
        logger.warning(f"Error reading current device settings for {thermostat.get('name', 'Unknown')}: {str(e)} - using target settings for alerts")
        return target_mode, target_cool, target_heat

# === Alert System Functions ===
# Temperature monitoring and notification system for cost control during guest stays
# Checks actual device settings (not target settings) to catch extreme guest temperature changes
# Supports flexible threshold configuration and sends formatted Slack notifications

def check_temperature_alerts_with_current_device(thermostat_name: str, property_name: str, thermostat: dict, property_config: dict, target_mode: str, target_cool: int, target_heat: int, temperature_config: dict, wyze_client=None) -> list:
    """
    Main entry point for temperature alert checking with actual device state reading.
    Coordinates reading current device settings and checking against alert thresholds.
    
    This function is crucial for cost control during guest stays by:
    - Reading actual device state (not target settings) to catch guest changes
    - Detecting extreme temperature settings that increase energy costs
    - Only running during reservations to avoid false alerts
    - Providing detailed violation information for property management
    
    Flow:
    1. Routes to brand-specific module to read current device settings
    2. Compares current settings against configured alert thresholds  
    3. Generates and sends Slack notifications for violations
    4. Returns list of alerts sent for logging/tracking
    
    Args:
        thermostat_name: Name of the thermostat for identification
        property_name: Name of the property for alert context
        thermostat: Thermostat configuration dictionary with brand info
        property_config: Property configuration with brand settings
        target_mode: Target thermostat mode we would set (for comparison)
        target_cool: Target cooling setpoint we would set (for comparison)
        target_heat: Target heating setpoint we would set (for comparison)
        temperature_config: Temperature configuration with alert thresholds and settings
        wyze_client: Optional Wyze client to avoid re-authentication
        
    Returns:
        List of alert messages sent to Slack (empty list if no violations)
        
    Example Usage:
        alerts = check_temperature_alerts_with_current_device(
            "Living Room", "Beach House", thermostat_config, property_config,
            "cool", 74, 68, temp_config
        )
        if alerts:
            logger.info(f"Sent {len(alerts)} temperature alerts")
    """
    # Get current device settings (not target settings) by routing to brand-specific implementation
    current_mode, current_cool, current_heat = get_current_device_settings(
        thermostat, property_config, target_mode, target_cool, target_heat, wyze_client
    )
    
    # Check alerts against the CURRENT device settings
    return check_temperature_alerts(
        thermostat_name, property_name, current_mode, current_cool, current_heat, temperature_config
    )

def check_temperature_alerts(thermostat_name: str, property_name: str, current_mode: str, current_cool_temp: int, current_heat_temp: int, temperature_config: dict) -> list:
    """
    Check if current thermostat settings violate alert thresholds and send Slack notifications.
    This helps identify when guests set extreme temperatures that could increase energy costs.
    
    Args:
        thermostat_name: Name of the thermostat
        property_name: Name of the property
        current_mode: Current thermostat mode
        current_cool_temp: Current cooling setpoint
        current_heat_temp: Current heating setpoint
        temperature_config: Temperature configuration with alert settings
        
    Returns:
        List of alert messages sent
    """
    alerts_sent = []
    alerts = temperature_config.get('alerts', {})
    
    # Check if alerts should be enabled - True if alerts section exists OR if any alert thresholds are defined
    has_alert_thresholds = any(key in temperature_config for key in ['cool_below', 'cool_above', 'heat_below', 'heat_above']) or \
                          any(key in alerts for key in ['cool_below', 'cool_above', 'heat_below', 'heat_above'])
    alerts_enabled = alerts.get('enabled', True) if (alerts or has_alert_thresholds) else False
    logger.info(f"check_temperature_alerts: {thermostat_name} - alerts enabled: {alerts_enabled}, has_thresholds: {has_alert_thresholds}")
    
    if not alerts_enabled:
        logger.info(f"check_temperature_alerts: {thermostat_name} - alerts disabled, returning early")
        return alerts_sent
    
    logger.info(f"check_temperature_alerts: {thermostat_name} - checking thresholds for mode '{current_mode}', cool={current_cool_temp}°F, heat={current_heat_temp}°F")
    logger.info(f"check_temperature_alerts: {thermostat_name} - alert thresholds: {alerts}")
    
    alert_messages = []
    
    # Get alert thresholds - check both in alerts section and at temperature_config level
    def get_threshold(key):
        return alerts.get(key) or temperature_config.get(key)
    
    # Check cooling temperature alerts
    if current_mode in ['cool', 'auto']:
        cool_below = get_threshold('cool_below')
        cool_above = get_threshold('cool_above')
        
        logger.info(f"check_temperature_alerts: {thermostat_name} - checking cool alerts: below={cool_below}, above={cool_above}")
        
        if cool_below is not None and current_cool_temp < cool_below:
            alert_msg = f"{ALERT_EMOJI_COOL} Cool setpoint {current_cool_temp}°F is below threshold {cool_below}°F"
            alert_messages.append(alert_msg)
            logger.warning(f"check_temperature_alerts: {thermostat_name} - COOL BELOW violation: {alert_msg}")
            
        if cool_above is not None and current_cool_temp > cool_above:
            alert_msg = f"{ALERT_EMOJI_COOL} Cool setpoint {current_cool_temp}°F is above threshold {cool_above}°F"
            alert_messages.append(alert_msg)
            logger.warning(f"check_temperature_alerts: {thermostat_name} - COOL ABOVE violation: {alert_msg}")
    
    # Check heating temperature alerts
    if current_mode in ['heat', 'auto']:
        heat_below = get_threshold('heat_below')
        heat_above = get_threshold('heat_above')
        
        logger.info(f"check_temperature_alerts: {thermostat_name} - checking heat alerts: below={heat_below}, above={heat_above}")
        
        if heat_below is not None and current_heat_temp < heat_below:
            alert_msg = f"{ALERT_EMOJI_HEAT} Heat setpoint {current_heat_temp}°F is below threshold {heat_below}°F"
            alert_messages.append(alert_msg)
            logger.warning(f"check_temperature_alerts: {thermostat_name} - HEAT BELOW violation: {alert_msg}")
            
        if heat_above is not None and current_heat_temp > heat_above:
            alert_msg = f"{ALERT_EMOJI_HEAT} Heat setpoint {current_heat_temp}°F is above threshold {heat_above}°F"
            alert_messages.append(alert_msg)
            logger.warning(f"check_temperature_alerts: {thermostat_name} - HEAT ABOVE violation: {alert_msg}")
    
    # Send alerts if any violations found
    if alert_messages:
        alert_header = f"{ALERT_EMOJI_THERMOSTAT} Thermostat Alert - {property_name}\n"
        alert_header += f"Thermostat: {thermostat_name}\n"
        alert_header += f"Current Mode: {current_mode}\n"
        alert_header += f"Current Settings: Cool {current_cool_temp}°F, Heat {current_heat_temp}°F\n"
        alert_header += "Violations:\n"
        
        full_message = alert_header + "\n".join([f"• {msg}" for msg in alert_messages])
        
        # Use custom Slack channel if specified, otherwise use default
        slack_channel = alerts.get('slack_channel')
        try:
            send_slack_message(full_message, channel=slack_channel)
            alerts_sent.append(full_message)
            logger.warning(f"Temperature alert sent for {thermostat_name} at {property_name}")
        except Exception as e:
            logger.error(f"Failed to send temperature alert for {thermostat_name} at {property_name}: {str(e)}")
    else:
        logger.info(f"check_temperature_alerts: {thermostat_name} - no alert violations found")
    
    return alerts_sent

def get_thermostat_settings(thermostat, location, reservation=False, mode=None, temperatures=None):
    """
    Determine the optimal thermostat settings based on weather, reservation status,
    and thermostat configuration.
    
    Args:
        thermostat: Thermostat configuration dictionary
        location: Property location with latitude and longitude
        reservation: Whether there's an active reservation
        mode: Explicit HVAC mode to use (optional)
        temperatures: Temperature configuration dictionary (optional)
        
    Returns:
        Tuple of (mode, cool_temp, heat_temp, thermostat_scenario, freeze_protection_status)
    """
    # Fetch weather data for the property location
    current_temperature, temperature_min, temperature_max = get_weather_forecast(location['latitude'], location['longitude'])
    current_temp = current_temperature
    min_temp = temperature_min
    max_temp = temperature_max
    logger.info(f"Weather Temperatures: Current: {current_temp}°F, Low: {min_temp}°F, High: {max_temp}°F")

    # Get freeze protection configuration from thermostat
    freeze_protection = None
    freeze_protection_status = False

    if not reservation:
        # Look for non-reservation freeze protection in thermostat temperatures
        non_reservation_config = next(
            (temp for temp in thermostat.get('temperatures', []) if temp.get('when') == 'non_reservations'),
            None
        )
        
        if non_reservation_config:
            freeze_protection = non_reservation_config.get('freeze_protection')

    # Check for freezing conditions and override if necessary
    freeze_mode, freeze_cool_temp, freeze_heat_temp = check_and_override_for_freezing(min_temp, freeze_protection)
    if freeze_mode:
        mode = freeze_mode
        cool_temp = freeze_cool_temp
        heat_temp = freeze_heat_temp
        freeze_protection_status = True
    else:
        # Determine mode if not explicitly provided
        if mode is None:
            mode = determine_thermostat_mode(max_temp, min_temp)

        # Fetch comfortable temperatures based on the determined mode
        if temperatures is None:
            temperatures = thermostat.get('temperatures', [])
        cool_temp, heat_temp = get_comfortable_temperatures(mode, reservation, temperatures)

    # Get thermostat scenario
    thermostat_scenario = get_thermostat_scenario(reservation)
    logger.info(f"Thermostat Settings: Mode: {mode}, Cool: {cool_temp}°F, Heat: {heat_temp}°F, Scenario: {thermostat_scenario}")

    return mode, cool_temp, heat_temp, thermostat_scenario, freeze_protection_status
