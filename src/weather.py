import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from logger import Logger

logger = Logger()

VAULT_URL = os.environ["VAULT_URL"]
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

if LOCAL_DEVELOPMENT:
    OPENWEATHERMAP_KEY = os.environ["OPENWEATHERMAP_KEY"]
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    OPENWEATHERMAP_KEY = client.get_secret("OPENWEATHERMAP-KEY").value

def get_weather_by_lat_long(lat, lon):
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHERMAP_KEY}&units=imperial'
    response = requests.get(url)
    data = response.json()
    # current_temp = current_weather['main']['temp']
    # max_temp = current_weather['main']['temp_max']
    # min_temp = current_weather['main']['temp_min']
    return data

def get_current_temperature_by_zip(zip_code, country_code='US'):
    url = f'http://api.openweathermap.org/data/2.5/weather?zip={zip_code},{country_code}&appid={OPENWEATHERMAP_KEY}&units=imperial'
    response = requests.get(url)
    data = response.json()
    current_temp = data['main']['temp']
    return current_temp

import requests

def get_weather_forecast(latitude, longitude):
    logger.info(f"Get weather from api.weather.gov")
    point_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    
    try:
        # Get grid coordinates for the given latitude and longitude
        response = requests.get(point_url)
        response.raise_for_status()  # Raise exception if the request fails
        point_data = response.json()

        # Get the forecast URL
        forecast_url = point_data['properties']['forecast']

        # Fetch the weather forecast
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()  # Raise exception if the request fails
        forecast_data = forecast_response.json()

        # Extract the current temperature
        current_forecast = forecast_data['properties']['periods'][0]
        current_temperature = current_forecast['temperature']
        temperature_unit = current_forecast['temperatureUnit']

        temperature_min = None
        temperature_max = None

        # Loop through the periods to find today's min and max temperatures
        for period in forecast_data['properties']['periods']:
            if 'Today' in period['name'] or 'This Afternoon' in period['name']:
                temperature_max = period['temperature']
            if 'Tonight' in period['name']:
                temperature_min = period['temperature']

        logger.info(f"Current Temperature: {current_temperature} {temperature_unit}")
        logger.info(f"Min Temperature Today: {temperature_min} {temperature_unit}")
        logger.info(f"Max Temperature Today: {temperature_max} {temperature_unit}")

        # If min/max is not found, return current_temperature
        if temperature_min is None:
            temperature_min = current_temperature
        if temperature_max is None:
            temperature_max = current_temperature

        return current_temperature, temperature_min, temperature_max
    
    except requests.exceptions.RequestException as e:
        logger.error(f"get_weather_forecast error: {e}")
        return {"error": str(e)}