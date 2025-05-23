"""
Hospitable API Client Module

This module provides functionality for interacting with the Hospitable API,
including authentication, property retrieval, and reservation management.
"""
import requests
from logger import Logger
import pytz
import jwt
from datetime import datetime, timedelta, timezone
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Environment configuration
VAULT_URL = os.environ["VAULT_URL"]
TIMEZONE = os.environ['TIMEZONE']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

logger = Logger()

# Configure credentials based on environment
if LOCAL_DEVELOPMENT:
    # For local development, load credentials from environment variables
    HOSPITABLE_EMAIL = os.environ["HOSPITABLE_EMAIL"]
    HOSPITABLE_PASSWORD = os.environ["HOSPITABLE_PASSWORD"]
    HOSPITABLE_TOKEN = os.environ["HOSPITABLE_TOKEN"]
else:
    # For production, fetch credentials from Azure Key Vault
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    HOSPITABLE_EMAIL = client.get_secret("HOSPITABLE-EMAIL").value
    HOSPITABLE_PASSWORD = client.get_secret("HOSPITABLE-PASSWORD").value
    HOSPITABLE_TOKEN = client.get_secret("HOSPITABLE-TOKEN").value

def get_new_token():
    """
    Authenticate with Hospitable API and obtain a new authentication token.
    
    Returns:
        str or None: A new authentication token if successful, None otherwise.
    """
    url = 'https://api.hospitable.com/v1/auth/login'
    payload = {
        'email': HOSPITABLE_EMAIL,
        'password': HOSPITABLE_PASSWORD,
        'flow': 'link'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raises exception for HTTP errors
        
        if response.status_code == 200 and 'token' in response.json().get('data', {}):
            token = response.json()['data']['token']
            try:
                if not LOCAL_DEVELOPMENT:
                    client.set_secret("HOSPITABLE-TOKEN", token)
            except Exception as e:
                logger.error(f"Error in updating Hospitable token: {str(e)}")
            return token
        logger.error('Failed to authenticate with Hospitable API.')
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Hospitable API: {str(e)}")
        return None

def token_is_valid(token):
    """
    Check if the provided JWT token is valid and not about to expire.
    
    Args:
        token (str): The JWT token to validate.
        
    Returns:
        bool: True if the token is valid and not expiring soon, False otherwise.
    """
    if not token:
        return False
        
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded_token['exp']
        exp_time = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        # Check if token expires in more than 15 minutes
        return exp_time > datetime.now(tz=timezone.utc) + timedelta(minutes=15)
    except jwt.ExpiredSignatureError:
        logger.info('Token has expired')
        return False
    except jwt.DecodeError:
        logger.error('Failed to decode JWT token.')
        return False
    except Exception as e:
        logger.error(f'Unexpected error validating token: {str(e)}')
        return False

def authenticate_hospitable(token=None):
    """
    Authenticate with the Hospitable API, using existing token if valid.
    
    Args:
        token (str, optional): An existing token to validate and use if possible.
        
    Returns:
        str or None: A valid authentication token if successful, None otherwise.
    """
    if token and token_is_valid(token):
        logger.info('Hospitable token valid')
        return token
    else:
        logger.info('Get new Hospitable token')
        return get_new_token()


def get_properties(token):
    """
    Fetch all properties from the Hospitable API.
    
    Args:
        token (str): A valid authentication token.
        
    Returns:
        list or None: List of property data if successful, None otherwise.
    """
    if not token:
        logger.error('No valid token provided to get_properties')
        return None
        
    url = 'https://api.hospitable.com/v1/properties?pagination=false&transformer=simple'
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['data']
    except requests.exceptions.RequestException as e:
        logger.error(f'Failed to fetch properties from Hospitable API: {str(e)}')
        return None
    except (KeyError, ValueError) as e:
        logger.error(f'Error parsing Hospitable API response: {str(e)}')
        return None

def get_reservations(token, property_id, days_ahead=7):
    """
    Fetch reservations for a specific property within a date range.
    
    Args:
        token (str): A valid authentication token.
        property_id (str): ID of the property to fetch reservations for.
        days_ahead (int, optional): Number of days ahead to fetch. Defaults to 7.
        
    Returns:
        list or None: List of reservation data if successful, None otherwise.
    """
    if not token:
        logger.error('No valid token provided to get_reservations')
        return None
        
    # Calculate date range
    timezone_obj = pytz.timezone(TIMEZONE)
    today = datetime.now(timezone_obj).strftime('%Y-%m-%d')
    future_date = (datetime.now(timezone_obj) + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    
    url = f"https://api.hospitable.com/v1/reservations/?starts_or_ends_between={today}_{future_date}&timezones=false&property_ids={property_id}&calendar_blockable=true&include_family_reservations=true"
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['data']
    except requests.exceptions.RequestException as e:
        logger.error(f'Failed to fetch reservations for property ID {property_id}: {str(e)}')
        return None
    except (KeyError, ValueError) as e:
        logger.error(f'Error parsing reservation data: {str(e)}')
        return None
