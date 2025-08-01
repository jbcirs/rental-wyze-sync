import requests
from logger import Logger
import os
import json
import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = os.environ["VAULT_URL"]
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
SMARTTHINGS_API_DELAY_SECONDS = int(os.environ.get('SMARTTHINGS_API_DELAY_SECONDS', '2'))

logger = Logger()

if LOCAL_DEVELOPMENT:
    SMARTTHINGS_TOKEN = os.environ["SMARTTHINGS_TOKEN"]
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    SMARTTHINGS_TOKEN = client.get_secret("SMARTTHINGS-TOKEN").value

# API endpoints
BASE_URL = 'https://api.smartthings.com/v1'

# Headers for the API requests
HEADERS = {
    'Authorization': f'Bearer {SMARTTHINGS_TOKEN}',
    'Content-Type': 'application/json'
}

def send_command(url, command):
    """
    Send a command to a SmartThings device.
    
    Args:
        url: API endpoint URL
        command: Command dictionary to send
        
    Returns:
        bool: True if command was successful, False otherwise
    """
    payload = {"commands": [command]}

    try:
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            logger.error(f"⚠️ Failed to execute command '{command['command']}'. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        logger.info(f"Command '{command['command']}' executed successfully.")
        return True
        
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while executing command '{command['command']}'.")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"🔌 Connection Error: Failed to connect to SmartThings API while executing command '{command['command']}'.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to execute command '{command['command']}'. Error: {str(e)}")
        return False

def get_all_locations():
    """
    Get all locations from SmartThings API.
    
    Returns:
        List of location objects or None if failed
    """
    try:
        response = requests.get(f'{BASE_URL}/locations', headers=HEADERS)

        if response.status_code != 200:
            logger.error(f"⚠️ Failed to get_all_locations. Status Code: {response.status_code}")
            logger.error(f"Response: {response.content.decode()}")
            return None

        response.raise_for_status()
        return response.json()['items']
    except requests.exceptions.Timeout:
        logger.error("⏱️ Timeout Error: Connection to SmartThings API timed out while retrieving locations.")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to retrieve locations. Error: {str(e)}")
        return None

def find_location_by_name(location_name):
    """
    Find a location by name in SmartThings.
    
    Args:
        location_name: Name of location to find
        
    Returns:
        Location ID if found, None otherwise
    """
    locations = get_all_locations()
    if not locations:
        logger.error(f"❓ No locations found in SmartThings account when searching for '{location_name}'.")
        return None
        
    for location in locations:
        if location['name'].lower() == location_name.lower():
            return location['locationId']
            
    logger.error(f"❓ Location Not Found: No location named '{location_name}' found in your SmartThings account.")
    return None

def get_devices(location_id):
    """
    Get all devices for a location.
    
    Args:
        location_id: ID of the location
        
    Returns:
        List of device objects or None if failed
    """
    try:
        if not location_id:
            logger.error("🔍 Missing location_id in get_devices call.")
            return None
            
        response = requests.get(f'{BASE_URL}/devices?locationId={location_id}', headers=HEADERS)
        response.raise_for_status()
        
        if response.status_code == 200:
            return response.json()['items']
        else:
            logger.error(f"⚠️ Failed to retrieve devices. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while retrieving devices for location {location_id}.")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to retrieve devices for location {location_id}. Error: {str(e)}")
        return None

def get_device_id_by_label(location_id, label):
    """
    Find a device by its label in a specific location.
    
    Args:
        location_id: ID of the location
        label: Device label to search for
        
    Returns:
        Device ID if found, None otherwise
    """
    devices = get_devices(location_id)
    if not devices:
        logger.error(f"❓ No devices found for location ID {location_id}")
        return None

    for device in devices:
        if device['label'] == label:
            return device['deviceId']
            
    logger.error(f"❓ Device Not Found: No device labeled '{label}' found at location {location_id}")
    return None

def get_device_id_by_name(location_id, name):
    devices = get_devices(location_id)
    if not devices:
        logger.error(f"❓ No devices found for location ID {location_id}")
        return None

    for device in devices:
        if device['name'] == name:
            return device['deviceId']
            
    logger.error(f"❓ Device Not Found: No device named '{name}' found at location {location_id}")
    return None

def get_device_status(device_id):
    status_url = f'{BASE_URL}/devices/{device_id}/status'
    try:
        response = requests.get(status_url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while retrieving status for device {device_id}.")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to retrieve status for device {device_id}. Error: {str(e)}")
        return None

def refresh_device_status(device_id):
    """
    Force a refresh of device status from the physical device to SmartThings cloud.
    This ensures the latest data is available when querying device status.
    
    Args:
        device_id: ID of the device to refresh
        
    Returns:
        bool: True if refresh command was successful, False otherwise
    """
    if not device_id:
        logger.error("🔍 Missing device_id in refresh_device_status call.")
        return False
        
    url = f"{BASE_URL}/devices/{device_id}/commands"

    payload = {
        "commands": [
            {
                "component": "main",
                "capability": "refresh",
                "command": "refresh"
            }
        ]
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            logger.info(f"🔄 Successfully sent refresh command to device {device_id}")
            return True
        else:
            # Log warning instead of error for 424 (device connectivity issues)
            if response.status_code == 424:
                logger.warning(f"⚠️ Device {device_id} is temporarily unavailable (424). This is usually a device connectivity issue.")
            else:
                logger.warning(f"⚠️ Failed to send refresh command to device {device_id}. Status code: {response.status_code}")
            logger.warning(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error refreshing device {device_id}: {str(e)}")
        return False

def get_device_status_with_refresh(device_id, force_refresh=True):
    """
    Get device status with optional forced refresh to ensure latest data.
    
    Args:
        device_id: ID of the device
        force_refresh: Whether to force a refresh before getting status (default: True)
        
    Returns:
        Device status JSON or None if failed
    """
    if not device_id:
        logger.error("🔍 Missing device_id in get_device_status_with_refresh call.")
        return None
    
    if force_refresh:
        logger.info(f"🔄 Refreshing device {device_id} to get latest status...")
        refresh_success = refresh_device_status(device_id)
        
        if refresh_success:
            # Wait for the device to update its status after refresh
            logger.info(f"⏱️ Waiting {SMARTTHINGS_API_DELAY_SECONDS} seconds for device status to update...")
            time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
        else:
            logger.warning(f"⚠️ Refresh failed for device {device_id}, proceeding with cached status")
    
    # Get the current status
    return get_device_status(device_id)

def switch(device_id, state=True):
    if device_id is None:
        logger.error(f"❓ Device '{device_id}' not found.")
        return False

    url = f"{BASE_URL}/devices/{device_id}/commands"
    command = "on" if state else "off"
    payload = {
        "commands": [
            {
                "component": "main",
                "capability": "switch",
                "command": command
            }
        ]
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            logger.error(f"⚠️ Failed to switch. Status Code: {response.status_code}")
            logger.error(f"Response: {response.content.decode()}")
            return False

        response.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while switching device {device_id}.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to switch device {device_id}. Error: {str(e)}")
        return False

def set_thermostat(device_id, device_name, mode, cool_temp=None, heat_temp=None, fan_mode="auto"):
    """
    Set thermostat mode, temperature, and fan settings.
    
    Args:
        device_id: Thermostat device ID
        device_name: Name of the thermostat (for logging)
        mode: Desired mode (cool, heat, auto, off)
        cool_temp: Cooling setpoint temperature
        heat_temp: Heating setpoint temperature
        fan_mode: Fan mode (auto, on)
        
    Returns:
        bool: True if all commands were successful, False otherwise
    """
    if not device_id:
        logger.error(f"❓ Missing device_id for thermostat '{device_name}'")
        return False
        
    url = f"{BASE_URL}/devices/{device_id}/commands"
    commands = []
    
    # Track original settings for logging - refresh to get latest data
    original_settings = get_device_status_with_refresh(device_id, force_refresh=True)
    if original_settings:
        try:
            original_mode = original_settings['components']['main']['thermostatMode']['thermostatMode']['value']
            original_cool = original_settings['components']['main']['thermostatCoolingSetpoint']['coolingSetpoint']['value']
            original_heat = original_settings['components']['main']['thermostatHeatingSetpoint']['heatingSetpoint']['value']
            original_fan = original_settings['components']['main']['thermostatFanMode']['thermostatFanMode']['value']
        except KeyError:
            logger.warning(f"⚠️ Could not extract all original settings for '{device_name}'")
            original_mode = "unknown"
            original_cool = "unknown"
            original_heat = "unknown"
            original_fan = "unknown"
    else:
        original_mode = "unknown"
        original_cool = "unknown"
        original_heat = "unknown" 
        original_fan = "unknown"

    # Build commands list based on what needs to be updated
    if mode in ["cool", "heat", "auto", "off"]:
        commands.append({
            "component": "main",
            "capability": "thermostatMode",
            "command": "setThermostatMode",
            "arguments": [mode]
        })

    if cool_temp is not None:
        commands.append({
            "component": "main",
            "capability": "thermostatCoolingSetpoint",
            "command": "setCoolingSetpoint",
            "arguments": [cool_temp]
        })

    if heat_temp is not None:
        commands.append({
            "component": "main",
            "capability": "thermostatHeatingSetpoint",
            "command": "setHeatingSetpoint",
            "arguments": [heat_temp]
        })

    if fan_mode in ["auto", "on"]:
        commands.append({
            "component": "main",
            "capability": "thermostatFanMode",
            "command": "setThermostatFanMode",
            "arguments": [fan_mode]
        })

    # Track changes for Slack notification
    changes = []
    if original_mode != "unknown" and original_mode != mode:
        changes.append(f"Mode: {original_mode} → {mode}")
    if original_cool != "unknown" and cool_temp is not None and original_cool != cool_temp:
        changes.append(f"Cool: {original_cool}°F → {cool_temp}°F")
    if original_heat != "unknown" and heat_temp is not None and original_heat != heat_temp:
        changes.append(f"Heat: {original_heat}°F → {heat_temp}°F")
    if original_fan != "unknown" and original_fan != fan_mode:
        changes.append(f"Fan: {original_fan} → {fan_mode}")

    # Send the commands one by one with a delay
    all_succeeded = True
    for command in commands:
        success = send_command(url, command)
        if not success:
            all_succeeded = False
        time.sleep(1)  # Add delay between commands
    
    # Return changes for Slack notification
    return all_succeeded, changes

def filter_locks(devices):
    locks = [device for device in devices if any(capability['id'] == 'lockCodes' for capability in device['components'][0]['capabilities'])]
    return locks

def get_locks_with_users(devices):
    locks_with_users = []
    for device in devices:
        device_id = device['deviceId']
        # Do NOT force refresh to avoid excessive SmartThings API calls
        device_status = get_device_status_with_refresh(device_id, force_refresh=False)
        lock_codes_json = device_status.get('components', {}).get('main', {}).get('lockCodes', {}).get('lockCodes', {}).get('value', "{}")
        lock_codes = json.loads(lock_codes_json)
        locks_with_users.append({
            'lock_id': device_id,
            'lock_name': device['label'],
            'users': lock_codes
        })
    return locks_with_users

def find_next_available_user_id(lock_codes):
    existing_ids = {int(user_id) for user_id in lock_codes.keys()}
    max_id = max(existing_ids, default=0)
    for next_id in range(1, max_id + 2):
        if next_id not in existing_ids:
            return int(next_id)
    return int(max_id + 1)

def find_user_id_by_name(lock, user_name):
    return next((int(user_id) for user_id, name in lock['users'].items() if name == user_name), None)

def find_all_guest_user_ids(lock):
    return [int(user_id) for user_id, name in lock['users'].items() if name.startswith("Guest")]

def find_all_guest_user_names(lock):
    return [name for name in lock['users'].values() if name.startswith("Guest")]

def add_user_code(lock, user_name, code):
    """
    Add a new access code to a lock.
    
    Args:
        lock: Lock information dictionary
        user_name: Name/label for the code
        code: Access code (usually last 4 digits of phone)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate code is numeric and not empty
    if not code or not code.isdigit():
        logger.error(f"📱 Invalid Lock Code: Cannot create lock code for '{user_name}' - code '{code}' is not a valid numeric code.")
        return False
        
    lock_id = lock['lock_id']
    lock_codes = lock['users']
    url = f'{BASE_URL}/devices/{lock_id}/commands'
    user_id = find_next_available_user_id(lock_codes)
    
    try:
        payload = {
            "commands": [
                {
                    "capability": "lockCodes",
                    "command": "setCode",
                    "arguments": [user_id, code, user_name]
                }
            ]
        }
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            logger.error(f"🔐 Failed to add user code for '{user_name}'. Status Code: {response.status_code}")
            logger.error(f"Response: {response.content.decode()}")
            return False

        logger.info(f"🔑 Successfully added code for user '{user_name}' to lock '{lock['lock_name']}'")
        return True
        
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while adding code for '{user_name}'.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to add code for '{user_name}'. Error: {str(e)}")
        return False

def delete_user_code(lock, user_id):
    lock_id = lock['lock_id']
    url = f'{BASE_URL}/devices/{lock_id}/commands'
    payload = {
        "commands": [
            {
                "capability": "lockCodes",
                "command": "deleteCode",
                "arguments": [user_id]
            }
        ]
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload)

        if response.status_code != 200:
            logger.error(f"🔐 Failed to delete user code for user ID '{user_id}'. Status Code: {response.status_code}")
            logger.error(f"Response: {response.content.decode()}")
            return False

        logger.info(f"🔑 Successfully deleted code for user ID '{user_id}' from lock '{lock['lock_name']}'")
        return True
        
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout Error: Connection to SmartThings API timed out while deleting code for user ID '{user_id}'.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected Error: Failed to delete code for user ID '{user_id}'. Error: {str(e)}")
        return False

def get_locks(location_id):
    devices = get_devices(location_id)
    locks = filter_locks(devices)
    locks_with_users = get_locks_with_users(locks)
    
    return locks_with_users

def find_lock_by_name(locks_with_users, lock_name):
    return next((lock for lock in locks_with_users if lock['lock_name'].lower() == lock_name.lower()), None)

def refresh_lock_data(location_id, lock_name):
    """
    Refresh lock data by re-fetching from SmartThings with forced device refresh.
    This ensures we get the latest lock codes after adding/deleting them.
    
    Args:
        location_id: SmartThings location ID
        lock_name: Name of the lock to refresh
        
    Returns:
        Updated lock dictionary with latest codes, or None if error
    """
    try:
        logger.info(f"🔄 Refreshing lock data for '{lock_name}' to get latest codes...")
        
        # Get fresh lock data with refresh
        locks_with_users = get_locks(location_id)
        if not locks_with_users:
            logger.error(f"❌ Failed to get refreshed locks data for location {location_id}")
            return None
            
        # Find the specific lock
        lock = find_lock_by_name(locks_with_users, lock_name)
        if not lock:
            logger.error(f"❌ Lock '{lock_name}' not found after refresh")
            return None
            
        logger.info(f"✅ Successfully refreshed lock data for '{lock_name}'")
        return lock
        
    except Exception as e:
        logger.error(f"❌ Error refreshing lock data for '{lock_name}': {str(e)}")
        return None

# Debugging Use
def print_locks_with_users(locks_with_users):
    for lock in locks_with_users:
        print(f"Lock Name: {lock['lock_name']}")
        print(f"Lock ID: {lock['lock_id']}")
        print("Users assigned to this lock:")
    for user_id, user_info in lock['users'].items():
        print(f"- {user_id}: {user_info}")
    print("")

# def main():
#     logger.info("Start Samrthings")

#     location_name = "Paradise Cove"
#     location_id = find_location_by_name(location_name)
#     locks_with_users = get_locks(location_id)
#     lock_name = "Master Bath Closet Door Lock"
#     lock = find_lock_by_name(locks_with_users,lock_name)

#     print(f"Lock: {lock}")

#      # Example: Adding a new user code
#     user_code = "8832"
#     user_name = "Guest Joe 20240625"
#     #add_user_code(lock, user_name, user_code)
#     #time.sleep(60)

    
#     # Example: Deleting a user code
#     #delete_user_code(lock, user_name)

# if __name__ == "__main__":
#     main()
