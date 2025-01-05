from weather import get_weather_forecast
from logger import Logger

logger = Logger()



def determine_thermostat_mode(max_temp, min_temp):
    if (max_temp > 80 and min_temp > 68) or max_temp > 90:
        return 'cool'
    elif (min_temp < 64 and max_temp < 70) or min_temp < 40:
        return 'heat'
    else:
        return 'auto'

def get_comfortable_temperatures(mode, reservation=False, temperatures=None):
    if reservation:
        default_temperatures = {
            'heat': {'cool_temp': 78, 'heat_temp': 74},
            'cool': {'cool_temp': 74, 'heat_temp': 68},
            'auto': {'cool_temp': 74, 'heat_temp': 70}
        }
    else:
        default_temperatures = {
            'heat': {'cool_temp': 85, 'heat_temp': 50},
            'cool': {'cool_temp': 85, 'heat_temp': 50},
            'auto': {'cool_temp': 85, 'heat_temp': 50}
        }

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
    if reservation:
        thermostat_scenario = 'home'
    else:
        thermostat_scenario = 'away'

    return thermostat_scenario

def check_and_override_for_freezing(min_temp, freeze_protection):
    """
    Check if the minimum temperature is below the freezing threshold
    and override the thermostat to heat mode to protect water pipes.
    Uses freeze_protection from the thermostat configuration.
    """
    if not freeze_protection:
        return None, None, None  # No freeze protection defined; skip checking

    freezing_threshold = freeze_protection.get('freeze_temp', 32)  # Default to 32°F
    pipe_protection_heat_temp = freeze_protection.get('heat_temp', 50)  # Default to 50°F

    if min_temp <= freezing_threshold:
        logger.warning(f"Temperature is below freezing. Overriding to 'heat' mode to protect water pipes.")
        return 'heat', pipe_protection_heat_temp, pipe_protection_heat_temp

    return None, None, None

def get_thermostat_settings(thermostat, location, reservation=False, mode=None, temperatures=None):
    """
    Determine the thermostat settings based on weather, reservation status,
    and thermostat configuration.
    """
    # Fetch weather data
    current_temperature, temperature_min, temperature_max = get_weather_forecast(location['latitude'], location['longitude'])
    current_temp = current_temperature
    min_temp = temperature_min
    max_temp = temperature_max
    logger.info(f"Weather Temperatures: Current: {current_temp}, Low: {min_temp}, High: {max_temp}")

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
    logger.info(f"Thermostat Settings: Mode: {mode}, Cool: {cool_temp}, Heat: {heat_temp}, Scenario: {thermostat_scenario}")

    return mode, cool_temp, heat_temp, thermostat_scenario, freeze_protection_status