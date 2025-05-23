import os
import requests
import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from logger import Logger
from slack_notify import send_slack_message

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

def get_weather_by_lat_long(lat, lon, retries=3):
    """
    Get current weather data by latitude and longitude.
    
    Args:
        lat: Latitude
        lon: Longitude
        retries: Number of retry attempts
        
    Returns:
        Dictionary with weather data or error information
    """
    url = f'http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHERMAP_KEY}&units=imperial'
    logger.info(f"Getting weather for coordinates: {lat}, {lon}")
    
    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Successfully retrieved weather data for coordinates: {lat}, {lon}")
            return data
        except requests.exceptions.RequestException as e:
            error_message = f"get_weather_by_lat_long attempt {attempt + 1} error: {e}"
            logger.error(error_message)
            attempt += 1
            
            if attempt < retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                send_slack_message(error_message, "rentals-errors")
                return {"error": str(e)}

def get_current_temperature_by_zip(zip_code, country_code='US', retries=3):
    """
    Get current temperature by zip code.
    
    Args:
        zip_code: Postal/ZIP code
        country_code: Country code (default: 'US')
        retries: Number of retry attempts
        
    Returns:
        Current temperature or error dictionary
    """
    url = f'http://api.openweathermap.org/data/2.5/weather?zip={zip_code},{country_code}&appid={OPENWEATHERMAP_KEY}&units=imperial'
    logger.info(f"Getting temperature for zip code: {zip_code}, {country_code}")
    
    attempt = 0
    while attempt < retries:
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            current_temp = data['main']['temp']
            logger.info(f"Current temperature for {zip_code}: {current_temp}°F")
            return current_temp
        except requests.exceptions.RequestException as e:
            error_message = f"get_current_temperature_by_zip attempt {attempt + 1} error: {e}"
            logger.error(error_message)
            attempt += 1
            
            if attempt < retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                send_slack_message(error_message, "rentals-errors")
                return {"error": str(e)}
        except (KeyError, ValueError) as e:
            error_message = f"Data parsing error: {e}"
            logger.error(error_message)
            send_slack_message(error_message, "rentals-errors")
            return {"error": str(e)}

def get_weather_forecast(latitude, longitude, retries=3):
    logger.info(f"Getting weather forecast for coordinates: {latitude}, {longitude}")
    point_url = f"https://api.weather.gov/points/{latitude},{longitude}"
    
    attempt = 0

    while attempt < retries:
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
            error_message = f"get_weather_forecast attempt {attempt + 1} error: {e}"
            logger.error(error_message)
            attempt += 1
            
            if attempt < retries:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                send_slack_message(error_message, "rentals-errors")
                return {"error": str(e)}
