"""
Thermostat control logic for managing temperature settings based on weather,
reservation status, and property configuration.
"""
from weather import get_weather_forecast
from logger import Logger
from datetime import datetime, timedelta
from slack_notify import send_slack_message
from typing import List, Tuple, Optional
import os

logger = Logger()

# Get timezone from environment
TIMEZONE = os.environ.get('TIMEZONE', 'UTC')

# Default frequency if not specified
DEFAULT_FREQUENCY = 'first_day'

# Alert message emojis
ALERT_EMOJI_COOL = '🔵'
ALERT_EMOJI_HEAT = '🔴'
ALERT_EMOJI_THERMOSTAT = '🌡️'

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
            'heat': {'cool_temp': 78, 'heat_temp': 74},
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

def check_temperature_alerts(thermostat_name: str, property_name: str, current_mode: str, current_cool_temp: int, current_heat_temp: int, temperature_config: dict) -> list:
    """
    Check if current thermostat settings violate alert thresholds and send Slack notifications.
    
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
    
    # Check if alerts are enabled (default to True if not specified)
    if not alerts.get('enabled', True):
        return alerts_sent
    
    alert_messages = []
    
    # Check cooling temperature alerts
    if current_mode in ['cool', 'auto']:
        cool_below = alerts.get('cool_below')
        cool_above = alerts.get('cool_above')
        
        if cool_below is not None and current_cool_temp < cool_below:
            alert_messages.append(f"{ALERT_EMOJI_COOL} Cool setpoint {current_cool_temp}°F is below threshold {cool_below}°F")
            
        if cool_above is not None and current_cool_temp > cool_above:
            alert_messages.append(f"{ALERT_EMOJI_COOL} Cool setpoint {current_cool_temp}°F is above threshold {cool_above}°F")
    
    # Check heating temperature alerts
    if current_mode in ['heat', 'auto']:
        heat_below = alerts.get('heat_below')
        heat_above = alerts.get('heat_above')
        
        if heat_below is not None and current_heat_temp < heat_below:
            alert_messages.append(f"{ALERT_EMOJI_HEAT} Heat setpoint {current_heat_temp}°F is below threshold {heat_below}°F")
            
        if heat_above is not None and current_heat_temp > heat_above:
            alert_messages.append(f"{ALERT_EMOJI_HEAT} Heat setpoint {current_heat_temp}°F is above threshold {heat_above}°F")
    
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
