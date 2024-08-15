import os
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

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
    return data

def get_current_temperature_by_zip(zip_code, country_code='US'):
    url = f'http://api.openweathermap.org/data/2.5/weather?zip={zip_code},{country_code}&appid={OPENWEATHERMAP_KEY}&units=imperial'
    response = requests.get(url)
    data = response.json()
    current_temp = data['main']['temp']
    return current_temp