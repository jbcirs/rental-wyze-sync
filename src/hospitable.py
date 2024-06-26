import requests
import logging
import pytz
from datetime import datetime, timedelta
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = os.environ["VAULT_URL"]
TIMEZONE = os.environ['TIMEZONE']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

if LOCAL_DEVELOPMENT:
    HOSPITABLE_EMAIL = os.environ["HOSPITABLE_EMAIL"]
    HOSPITABLE_PASSWORD = os.environ["HOSPITABLE_PASSWORD"]
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    HOSPITABLE_EMAIL = client.get_secret("HOSPITABLE-EMAIL").value
    HOSPITABLE_PASSWORD = client.get_secret("HOSPITABLE-PASSWORD").value

def authenticate_hospitable():
    url = 'https://api.hospitable.com/v1/auth/login'
    payload = {
        'email': HOSPITABLE_EMAIL,
        'password': HOSPITABLE_PASSWORD,
        'flow': 'link'
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200 and 'token' in response.json().get('data', {}):
        return response.json()['data']['token']
    logging.error('Failed to authenticate with Hospitable API.')
    return None

def get_properties(token):
    url = 'https://api.hospitable.com/v1/properties?pagination=false&transformer=simple'
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['data']
    logging.error('Failed to fetch properties from Hospitable API.')
    return None

def get_reservations(token, property_id):
    timezone = pytz.timezone(TIMEZONE)
    today = datetime.now(timezone).strftime('%Y-%m-%d')
    next_week = (datetime.now(timezone) + timedelta(days=7)).strftime('%Y-%m-%d')
    url = f"https://api.hospitable.com/v1/reservations/?starts_or_ends_between={today}_{next_week}&timezones=false&property_ids={property_id}&calendar_blockable=true&include_family_reservations=true"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['data']
    logging.error(f'Failed to fetch reservations for property ID {property_id}.')
    return None
