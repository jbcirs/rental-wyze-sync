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

def get_thermostat_settings(location, reservation=False, mode=None, temperatures=None):

    current_temperature, temperature_min, temperature_max = get_weather_forecast(location['latitude'], location['longitude'])
    current_temp = current_temperature
    min_temp = temperature_min
    max_temp = temperature_max
    logger.info(f"Weather Temperatures: Current: {current_temp}, Low: {min_temp}, High: {max_temp}")
    
    if mode is None:
        mode = determine_thermostat_mode(max_temp, min_temp)

    cool_temp, heat_temp = get_comfortable_temperatures(mode, reservation, temperatures)
    thermostat_scenario = get_thermostat_scenario(reservation)
    logger.info(f"Thermostat Settings: Mode: {mode}, Cool: {cool_temp}, Heat: {heat_temp}, Senerio: {thermostat_scenario}")

    return mode, cool_temp, heat_temp, thermostat_scenario