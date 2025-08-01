from logger import Logger
import os
import time
import requests
import json
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from brands.wyze.error_mapping import get_error_message
from slack_notify import send_slack_message
from wyze_sdk.models.devices.thermostats import Thermostat, ThermostatFanMode, ThermostatSystemMode, ThermostatScenarioType
from typing import Optional, Dict, Any


VAULT_URL = os.environ["VAULT_URL"]
TIMEZONE = os.environ['TIMEZONE']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
WYZE_API_DELAY_SECONDS = int(os.environ['WYZE_API_DELAY_SECONDS'])

# Wyze API Constants
WYZE_API_BASE_URL = "https://api.wyzecam.com"
SV_GET_DEVICE_PROPERTY_LIST = '1df2807c63254e16a06213323fe8dec8'
SV_GET_OBJECT_LIST = 'c417b62d72ee44bf933054bdca183e77'

logger = Logger()


if LOCAL_DEVELOPMENT:
    WYZE_EMAIL = os.environ.get("WYZE_EMAIL")
    WYZE_PASSWORD = os.environ.get("WYZE_PASSWORD")
    WYZE_KEY_ID = os.environ.get("WYZE_KEY_ID")
    WYZE_API_KEY = os.environ.get("WYZE_API_KEY")
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    WYZE_EMAIL = client.get_secret("WYZE-EMAIL").value
    WYZE_PASSWORD = client.get_secret("WYZE-PASSWORD").value
    WYZE_KEY_ID = client.get_secret("WYZE-KEY-ID").value
    WYZE_API_KEY = client.get_secret("WYZE-API-KEY").value

def get_wyze_token():
    """
    Authenticate with Wyze API and get an access token.
    
    Returns:
        str: Access token if successful, None if failed
    """
    try:
        response = Client().login(
                    email=WYZE_EMAIL,
                    password=WYZE_PASSWORD,
                    key_id=WYZE_KEY_ID,
                    api_key=WYZE_API_KEY
                )
        return response['access_token']
    except WyzeApiError as e:
        logger.error(f"Wyze API Error: {str(e)}")
        return None

def wyze_api_call(endpoint: str, token: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Make a direct API call to Wyze API with common required parameters.
    
    Args:
        endpoint: API endpoint (e.g., '/app/v2/device/get_property_list')
        token: Access token
        data: Additional request payload data (optional)
        
    Returns:
        API response as dict, or None if failed
    """
    try:
        url = f"{WYZE_API_BASE_URL}{endpoint}"
        
        # Build payload with required common parameters based on working Postman example
        payload = {
            "access_token": token,
            "app_name": "com.hualai",
            "app_ver": "com.hualai___2.19.14",
            "app_version": "2.19.14",
            "phone_id": "0e78f2a0-8e04-4f47-89e9-c114d63f7d9e",
            "phone_system_type": "2",
            "sc": "a626948714654991afd3c0dbd7cdb901",
            "ts": int(time.time() * 1000),  # Current timestamp in milliseconds
        }
        
        # Add any additional data from the caller
        if data:
            payload.update(data)
        
        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') == '1' and result.get('msg') == 'SUCCESS':
            return result
        else:
            logger.error(f"Wyze API error: {result.get('msg', 'Unknown error')} (code: {result.get('code', 'unknown')})")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling Wyze API {endpoint}: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from Wyze API {endpoint}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error calling Wyze API {endpoint}: {str(e)}")
        return None

def get_device_list_direct(token: str) -> Optional[list]:
    """
    Get list of all devices using direct API call.
    
    Args:
        token: Access token
        
    Returns:
        List of devices, or None if failed
    """
    try:
        # Use the correct sv parameter for get_object_list endpoint
        data = {
            "sv": "c417b62d72ee44bf933054bdca183e77"
        }
        
        response = wyze_api_call('/app/v2/home_page/get_object_list', token, data)
        if response and 'data' in response:
            return response['data'].get('device_list', [])
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting device list: {str(e)}")
        return None

def find_device_by_name_direct(token: str, device_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a device by name using direct API call.
    
    Args:
        token: Access token
        device_name: Device nickname to search for
        
    Returns:
        Device info dict, or None if not found
    """
    try:
        devices = get_device_list_direct(token)
        if not devices:
            return None
        
        for device in devices:
            if device.get('nickname') == device_name:
                return device
        
        logger.error(f"Device '{device_name}' not found in device list")
        return None
        
    except Exception as e:
        logger.error(f"Error finding device by name: {str(e)}")
        return None

def get_device_property_list(client, device_mac: str, device_model: str):
    """
    Get device property list using direct API call.
    
    Args:
        client: Wyze API client (used to get token)
        device_mac: Device MAC address (from device['mac'])
        device_model: Device model (from device['product_model'])
        
    Returns:
        Dict containing property list response, or None if failed
    """
    try:
        # Get token from the client if we don't have it
        token = get_wyze_token()
        if not token:
            logger.error("Unable to get Wyze token for property list API call")
            return None
        
        # Build specific data for property list endpoint
        data = {
            "device_mac": device_mac,
            "device_model": device_model,
            "sv": SV_GET_DEVICE_PROPERTY_LIST
        }
        
        response = wyze_api_call('/app/v2/device/get_property_list', token, data)
        return response
        
    except Exception as e:
        logger.error(f"Error getting device property list: {str(e)}")
        return None

def get_device_by_name(client, name):
    """
    Find a Wyze device by its nickname.
    
    Args:
        client: Wyze API client
        name: Device nickname to search for
        
    Returns:
        Device object if found, None otherwise
    """
    try:
        devices = client.list()
        for device in devices:
            if device.nickname == name:
                return device
        
        # Device not found after checking all devices
        error_msg = f"Device Not Found: No device named '{name}' found in your Wyze account. Please verify the device exists and is correctly named."
        slack_msg = f"❓ Device Not Found: No device named '{name}' found in your Wyze account. Please verify the device exists and is correctly named."
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except WyzeApiError as e:
        error_code = getattr(e, 'code', 'unknown')
        error_msg = f"Wyze API Error: Failed to retrieve device '{name}'. Error code: {error_code}. {str(e)}"
        slack_msg = f"⚠️ Wyze API Error: Failed to retrieve device '{name}'. Error code: {error_code}. {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except requests.exceptions.Timeout:
        error_msg = f"Timeout Error: Connection to Wyze API timed out while searching for device '{name}'. Please check your network connection."
        slack_msg = f"⏱️ Timeout Error: Connection to Wyze API timed out while searching for device '{name}'. Please check your network connection."
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected Error: Failed to search for device '{name}'. Error: {str(e)}"
        slack_msg = f"❌ Unexpected Error: Failed to search for device '{name}'. Error: {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None

def get_thermostat_status(client, device):
    """
    Get the current status of a thermostat device.
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        
    Returns:
        Thermostat status object if successful, None if failed
    """
    try:
        return client.info(device_mac=device.mac, device_model=device.product.model)
    except WyzeApiError as e:
        error_code = getattr(e, 'code', 'unknown')
        error_msg = f"Wyze API Error: Failed to get status for thermostat '{device.nickname}'. Error code: {error_code}. {str(e)}"
        slack_msg = f"⚠️ Wyze API Error: Failed to get status for thermostat '{device.nickname}'. Error code: {error_code}. {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except requests.exceptions.Timeout:
        error_msg = f"Timeout Error: Connection to Wyze API timed out while retrieving thermostat status for '{device.nickname}'."
        slack_msg = f"⏱️ Timeout Error: Connection to Wyze API timed out while retrieving thermostat status for '{device.nickname}'."
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected Error: Failed to get thermostat status for '{device.nickname}'. Error: {str(e)}"
        slack_msg = f"❌ Unexpected Error: Failed to get thermostat status for '{device.nickname}'. Error: {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None

def set_thermostat_temperature(client, device, heating_setpoint, cooling_setpoint):
    """
    Set heating and cooling temperature setpoints for a thermostat.
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        heating_setpoint: Desired heating temperature
        cooling_setpoint: Desired cooling temperature
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client.set_temperature(
            device_mac=device.mac,
            device_model=device.product.model,
            heating_setpoint=heating_setpoint,
            cooling_setpoint=cooling_setpoint
        )
        logger.info(f"Temperature for {device.nickname} set to heating: {heating_setpoint}°F, cooling: {cooling_setpoint}°F.")
        
        return True
    
    except WyzeApiError as e:
        logger.error(f"Failed to set temperature for {device.nickname}: {e}")
    
    return False

def set_thermostat_fan_mode(client, device, fan_mode="auto"):
    """
    Set fan mode for a thermostat.
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        fan_mode: Desired fan mode (default: "auto")
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        fan_mode = map_to_fan_mode(fan_mode)
        client.set_fan_mode(
            device_mac=device.mac,
            device_model=device.product.model,
            fan_mode=fan_mode
        )
        logger.info(f"Fan mode for {device.nickname} set to {fan_mode.name}.")

        return True
    
    except WyzeApiError as e:
        logger.error(f"Failed to set fan mode for {device.nickname}: {e}")
    
    return False

def set_thermostat_system_mode(client, device, mode):
    """
    Set the system mode for a thermostat (heat, cool, auto, etc.).
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        mode: Desired system mode
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        system_mode = map_to_thermostat_mode(mode)
        client.set_system_mode(
            device_mac=device.mac,
            device_model=device.product.model,
            system_mode=system_mode
        )
        logger.info(f"System mode for {device.nickname} set to {system_mode.name}.")

        return True
    
    except WyzeApiError as e:
        logger.error(f"Failed to set system mode for {device.nickname}: {e}")

    return False

def set_thermostat_scenario(client, device, scenario):
    """
    Set thermostat to a specified scenario (home, away, sleep).
    
    Args:
        client: Wyze API client
        device: Thermostat device object
        scenario: Desired scenario
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        system_scenario = map_to_thermostat_scenario(scenario)
        client.set_current_scenario(
            device_mac=device.mac,
            device_model=device.product.model,
            scenario=system_scenario
        )
        logger.info(f"System mode for {device.nickname} set to {system_scenario.name}.")

        return True
    
    except WyzeApiError as e:
        logger.error(f"Failed to set scenario for {device.nickname}: {e}")

    return False

def get_lock_codes(locks_client, lock_mac):
    """
    Get all access codes for a lock.
    
    Args:
        locks_client: Wyze API client
        lock_mac: MAC address of the lock
        
    Returns:
        List of access codes if successful, None if failed
    """
    try:
        codes = locks_client.get_keys(device_mac=lock_mac)
        if codes is None or len(codes) == 0:
            logger.info(f"📝 No existing access codes found for lock with MAC {lock_mac}.")
        return codes
    except WyzeApiError as e:
        error_code = getattr(e, 'code', 'unknown')
        error_msg = f"Wyze API Error: Failed to retrieve lock codes for lock {lock_mac}. Error code: {error_code}. {str(e)}"
        slack_msg = f"⚠️ Wyze API Error: Failed to retrieve lock codes for lock {lock_mac}. Error code: {error_code}. {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except requests.exceptions.Timeout:
        error_msg = f"Timeout Error: Connection to Wyze API timed out while retrieving lock codes for {lock_mac}."
        slack_msg = f"⏱️ Timeout Error: Connection to Wyze API timed out while retrieving lock codes for {lock_mac}."
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None
    except Exception as e:
        error_msg = f"Unexpected Error: Failed to retrieve lock codes for {lock_mac}. Error: {str(e)}"
        slack_msg = f"❌ Unexpected Error: Failed to retrieve lock codes for {lock_mac}. Error: {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return None

def find_code(existing_codes, label):
    """
    Find an access code by its label.
    
    Args:
        existing_codes: List of access codes
        label: Label to search for
        
    Returns:
        Access code object if found, None otherwise
    """
    return next((c for c in existing_codes if c.name == label), None)

def add_lock_code(locks_client, lock_mac, code, label, permission):
    """
    Add a new access code to a lock.
    
    Args:
        locks_client: Wyze API client
        lock_mac: MAC address of the lock
        code: Access code (usually last 4 digits of phone)
        label: Label for the code (typically includes guest name)
        permission: Access permission object (type and duration)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate phone code is numeric and not empty
        if not code or not code.isdigit():
            error_msg = f"Invalid Lock Code: Cannot create lock code for '{label}' - code '{code}' is not a valid numeric code."
            slack_msg = f"📱 Invalid Lock Code: Cannot create lock code for '{label}' - code '{code}' is not a valid numeric code."
            logger.error(error_msg)
            send_slack_message(slack_msg)
            return False
            
        response = locks_client.create_access_code(
            device_mac=lock_mac, 
            access_code=code, 
            name=label, 
            permission=permission
        )
        if response['ErrNo'] != 0:
            error_msg = f"Lock Code Error: {get_error_message(response['ErrNo'])} for code '{label}' on lock {lock_mac}."
            slack_msg = f"🔐 Lock Code Error: {get_error_message(response['ErrNo'])} for code '{label}' on lock {lock_mac}."
            logger.error(f"{error_msg}; Original response: {response}")
            send_slack_message(slack_msg)
            return False
        
        logger.info(f"{response}")
        # Add delay to prevent API rate limiting
        time.sleep(WYZE_API_DELAY_SECONDS)

        return True
    except WyzeApiError as e:
        error_code = getattr(e, 'code', 'unknown')
        error_msg = f"Wyze API Error: Failed to add lock code '{label}' to lock {lock_mac}. Error code: {error_code}. {str(e)}"
        slack_msg = f"⚠️ Wyze API Error: Failed to add lock code '{label}' to lock {lock_mac}. Error code: {error_code}. {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return False
    except requests.exceptions.Timeout:
        error_msg = f"Timeout Error: Connection to Wyze API timed out while adding lock code '{label}' to lock {lock_mac}."
        slack_msg = f"⏱️ Timeout Error: Connection to Wyze API timed out while adding lock code '{label}' to lock {lock_mac}."
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return False
    except Exception as e:
        error_msg = f"Unexpected Error: Failed to add lock code '{label}' to lock {lock_mac}. Error: {str(e)}"
        slack_msg = f"❌ Unexpected Error: Failed to add lock code '{label}' to lock {lock_mac}. Error: {str(e)}"
        logger.error(error_msg)
        send_slack_message(slack_msg)
        return False

def update_lock_code(locks_client, lock_mac, code_id, code, label, permission):
    """
    Update an existing access code.
    
    Args:
        locks_client: Wyze API client
        lock_mac: MAC address of the lock
        code_id: ID of the code to update
        code: New access code
        label: New label for the code
        permission: New access permission object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = locks_client.update_access_code(
            device_mac=lock_mac, 
            access_code_id=code_id, 
            access_code=code, 
            name=label, 
            permission=permission
        )

        if response['ErrNo'] != 0:
            logger.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
        
        logger.info(f"{response}")
        # Add delay to prevent API rate limiting
        time.sleep(WYZE_API_DELAY_SECONDS)

        return True
    except WyzeApiError as e:
        logger.error(f"Error updating lock code {code} in {lock_mac}: {str(e)}")
        send_slack_message(f"Error updating lock code {code} in {lock_mac}: {str(e)}")
        return False

def delete_lock_code(locks_client, lock_mac, code_id):
    """
    Delete an access code from a lock.
    
    Args:
        locks_client: Wyze API client
        lock_mac: MAC address of the lock
        code_id: ID of the code to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = locks_client.delete_access_code(
            device_mac=lock_mac, 
            access_code_id=code_id
        )
        # Accept both 0 (success) and 5021 (successfully deleted) as valid responses
        if response['ErrNo'] not in (0, 5021):
            logger.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
            
        logger.info(f"{response}")
        # Add delay to prevent API rate limiting
        time.sleep(WYZE_API_DELAY_SECONDS)

        return True
    except WyzeApiError as e:
        logger.error(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")
        send_slack_message(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")
        return False

def get_user_id_from_existing_codes(existing_codes, user_id=None):
    """
    Extract user ID from existing codes if not already provided.
    
    Args:
        existing_codes: List of existing access codes
        user_id: Current user ID (if any)
        
    Returns:
        User ID if found, None otherwise
    """
    if user_id is not None:
        return user_id

    for code in existing_codes:
        if hasattr(code, 'userid') and code.userid is not None:
            return code.userid

    return user_id

def map_to_thermostat_mode(input_str: str) -> Optional[ThermostatSystemMode]:
    """
    Map a string to a ThermostatSystemMode enum value.
    
    Args:
        input_str: String representation of the mode
        
    Returns:
        ThermostatSystemMode enum value if match found, None otherwise
    """
    normalized_str = input_str.strip().lower()
    for mode in ThermostatSystemMode:
        if normalized_str == mode.codes or normalized_str == mode.description.lower():
            return mode
    return None

def map_to_fan_mode(input_str: str) -> Optional[ThermostatFanMode]:
    """
    Map a string to a ThermostatFanMode enum value.
    
    Args:
        input_str: String representation of the fan mode
        
    Returns:
        ThermostatFanMode enum value if match found, None otherwise
    """
    normalized_str = input_str.strip().lower()
    for mode in ThermostatFanMode:
        if normalized_str == mode.codes or normalized_str == mode.description.lower():
            return mode
    return None

def map_to_thermostat_scenario(input_str: str) -> Optional[ThermostatScenarioType]:
    """
    Map a string to a ThermostatScenarioType enum value.
    
    Args:
        input_str: String representation of the scenario
        
    Returns:
        ThermostatScenarioType enum value if match found, None otherwise
    """
    normalized_str = input_str.strip().lower()
    for mode in ThermostatScenarioType:
        if normalized_str == mode.codes or normalized_str == mode.description.lower():
            return mode
    return None
