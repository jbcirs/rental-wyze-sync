import requests
import logging
import os
import json
import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = os.environ["VAULT_URL"]
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

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

def get_all_locations():
    response = requests.get(f'{BASE_URL}/locations', headers=HEADERS)

    if response.status_code != 200:
        logging.info(f"Failed to get_all_locations. Status Code: {response.status_code}")
        logging.info(f"Response: {response.content.decode()}")

    response.raise_for_status()
    return response.json()['items']

def find_location_by_name(location_name):
    locations = get_all_locations()
    for location in locations:
        if location['name'].lower() == location_name.lower():
            return location['locationId']
    return None

def get_devices(location_id):
    response = requests.get(f'{BASE_URL}/devices?locationId={location_id}', headers=HEADERS)
    response.raise_for_status()
    if response.status_code == 200:
        return response.json()['items']
    else:
        logging.info(f"Failed to retrieve devices. Status code: {response.status_code}")
        logging.info(f"Response: {response.text}")
        return None

def get_device_id_by_label(location_id,label):
    devices = get_devices(location_id)

    for device in devices:
        if device['label'] == label:
            return device['deviceId']
    logging.info(f"No device label found called: {label} at {location_id}")
    return None

def get_device_id_by_name(location_id,name):
    devices = get_devices(location_id)

    for device in devices:
        if device['name'] == name:
            return device['deviceId']
    logging.info(f"No device label found called: {name} at {location_id}")
    return None

def get_device_status(device_id):
    status_url = f'{BASE_URL}/devices/{device_id}/status'
    response = requests.get(status_url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def switch(device_id, state=True):
    if device_id is None:
        logging.info(f"Device '{device_id}' not found.")
        return

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

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logging.info(f"Failed to switch. Status Code: {response.status_code}")
        logging.info(f"Response: {response.content.decode()}")
        return False

    response.raise_for_status()
    return True

def send_command(url, command):
    payload = {"commands": [command]}

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logging.info(f"Failed to execute command '{command['command']}'. Status code: {response.status_code}")
        logging.info(f"Response: {response.text}")
        return False
    
    logging.info(f"Command '{command['command']}' executed successfully.")

    return True

def set_thermostat(device_id, device_name, mode, cool_temp=None, heat_temp=None, fan_mode="auto"):
    url = f"{BASE_URL}/devices/{device_id}/commands"
    commands = []

    if mode in ["cool", "heat", "auto", "off"]:
        commands.append({
            "component": "main",
            "capability": "thermostatMode",
            "command": "setThermostatMode",
            "arguments": [mode]
        })

    if cool_temp is not None and mode == "cool":
        commands.append({
            "component": "main",
            "capability": "thermostatCoolingSetpoint",
            "command": "setCoolingSetpoint",
            "arguments": [cool_temp]
        })

    if heat_temp is not None and mode == "heat":
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

    # Send the commands one by one with a delay
    for command in commands:
        success = send_command(url, command)
        if not success:
            return False
        time.sleep(1)
    
    return True


def filter_locks(devices):
    locks = [device for device in devices if any(capability['id'] == 'lockCodes' for capability in device['components'][0]['capabilities'])]
    return locks

def get_locks_with_users(devices):
    locks_with_users = []
    for device in devices:
        device_id = device['deviceId']
        device_status = get_device_status(device_id)
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
    lock_id = lock['lock_id']
    lock_codes = lock['users']
    url = f'{BASE_URL}/devices/{lock_id}/commands'
    user_id = find_next_available_user_id(lock_codes)
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
        logging.info(f"Failed to add user code. Status Code: {response.status_code}")
        logging.info(f"Response: {response.content.decode()}")
        return False

    response.raise_for_status()
    return True


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
    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code != 200:
        logging.info(f"Failed to delete user code. Status Code: {response.status_code}")
        logging.info(f"Response: {response.content.decode()}")
        return False

    response.raise_for_status()
    return True

def get_locks(location_id):
    devices = get_devices(location_id)
    locks = filter_locks(devices)
    locks_with_users = get_locks_with_users(locks)
    
    return locks_with_users

def find_lock_by_name(locks_with_users, lock_name):
    return next((lock for lock in locks_with_users if lock['lock_name'].lower() == lock_name.lower()), None)

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
#     logging.info("Start Samrthings")

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