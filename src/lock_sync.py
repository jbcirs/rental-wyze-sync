import logging
import os
import requests
import re
import time
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from wyze_sdk.models.devices.locks import LockKeyPermission, LockKeyPermissionType
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from error_mapping import get_error_message

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
SLACK_CHANNEL = os.environ['SLACK_CHANNEL']
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
TEST =  os.environ.get('TEST', 'false').lower() == 'true'
TEST_PROPERTY_NAME = os.environ['TEST_PROPERTY_NAME']
LOCAL = os.environ.get('LOCAL', 'false').lower() == 'true'

if LOCAL:
    HOSPITABLE_EMAIL = os.environ["HOSPITABLE_EMAIL"]
    HOSPITABLE_PASSWORD = os.environ["HOSPITABLE_PASSWORD"]
    SLACK_TOKEN = os.environ["SLACK_TOKEN"]
    WYZE_EMAIL = os.environ["WYZE_EMAIL"]
    WYZE_PASSWORD = os.environ["WYZE_PASSWORD"]
    WYZE_KEY_ID = os.environ["WYZE_KEY_ID"]
    WYZE_API_KEY = os.environ["WYZE_API_KEY"]
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    HOSPITABLE_EMAIL = client.get_secret("HOSPITABLE-EMAIL").value
    HOSPITABLE_PASSWORD = client.get_secret("HOSPITABLE-PASSWORD").value
    SLACK_TOKEN = client.get_secret("SLACK-TOKEN").value
    WYZE_EMAIL = client.get_secret("WYZE-EMAIL").value
    WYZE_PASSWORD = client.get_secret("WYZE-PASSWORD").value
    WYZE_KEY_ID = client.get_secret("WYZE-KEY-ID").value
    WYZE_API_KEY = client.get_secret("WYZE-API-KEY").value


# Initialize Slack client
slack_client = WebClient(token=SLACK_TOKEN)

def process_reservations(delete_all_guest_codes=False):
    logging.info('Processing reservations.')

    try:
        token = authenticate_hospitable()
        if not token:
            send_slack_message("Unable to authenticate with Hospitable API.")
            return

        properties = get_properties(token)
        if not properties:
            send_slack_message("Unable to fetch properties from Hospitable API.")
            return

        wyze_token = get_wyze_token()
        if not wyze_token:
            send_slack_message("Unable to authenticate with Wyze API.")
            return

        client = Client(token=wyze_token)
        locks_client = client.locks
        
        for prop in properties:
            property_id = prop['id']
            property_name = prop['name']
            reservations = get_reservations(token, property_id)

            if not reservations:
                send_slack_message(f"No reservations for property {property_name}.")
                continue

            lock_name = f"{property_name} - FD"

            if TEST:
                if lock_name != TEST_PROPERTY_NAME:
                    send_slack_message(f"Skipping locks for property {property_name}.")
                    continue

            lock_info = get_lock_info(locks_client, lock_name)
            if lock_info is None:
                send_slack_message(f"Unable to fetch lock info for {lock_name} at {property_name}.")
                continue

            lock_mac = lock_info.mac
            existing_codes = get_lock_codes(locks_client, lock_mac)

            if existing_codes is None:
                send_slack_message(f"Unable to fetch lock codes for {lock_name} at {property_name}.")
                continue

            locks_client._user_id = get_user_id_from_existing_codes(existing_codes, locks_client._user_id)

            if locks_client._user_id is None:
                send_slack_message(f":4934-error: Unable to find user_id")
                return

            deletions = []
            updates = []
            additions = []
            errors = []

            # Delete old guest codes
            for code in existing_codes:
                if code.name.startswith("Guest"):
                    permission = code.permission
                    if delete_all_guest_codes or (permission.type == LockKeyPermissionType.DURATION and permission.end < datetime.now()):
                        if delete_lock_code(locks_client, lock_mac, code.id):
                            deletions.append(code.name)
                        else:
                            errors.append(f"Deleting Code for {label}")

            # Process reservations
            for reservation in reservations:
                guest_name = reservation['guest']
                guest_first_name = guest_name.split()[0]
                phone_last4 = reservation['phone'][-4:]
                label = f"Guest {guest_first_name}"
                label += f" {reservation['checkin'][:10].replace('-', '')}"
                checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS)
                checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS)

                permission = LockKeyPermission(
                    type=LockKeyPermissionType.DURATION, 
                    begin=checkin_time, 
                    end=checkout_time
                )

                if not label_exists(existing_codes, label):
                    logging.info(f"ADD: {property_name}; label: {label}")
                    if add_lock_code(locks_client, lock_mac, phone_last4, label, permission):
                        additions.append(label)
                    else:
                        errors.append(f"Adding Code for {label}")
                else:
                    update_code = next((c for c in existing_codes if c.name == label), None)
                    if update_code:
                        logging.info(f"UPDATE: {property_name}; label: {label}")
                        if update_lock_code(locks_client, lock_mac, update_code.id, phone_last4, label, permission):
                            updates.append(label)
                        else:
                            errors.append(f"Updating Code for {label}")
                
                # Slow down API calls for Wyze locks
                time.sleep(5)

            # Send Slack summary
            send_summary_slack_message(property_name, deletions, updates, additions, errors)

    except Exception as e:
        logging.error(f"Error in function: {str(e)}")
        send_slack_message(f"Error in function: {str(e)}")

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
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    url = f"https://api.hospitable.com/v1/reservations/?starts_or_ends_between={today}_{next_week}&timezones=false&property_ids={property_id}&calendar_blockable=true&include_family_reservations=true"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['data']
    logging.error(f'Failed to fetch reservations for property ID {property_id}.')
    return None

def get_wyze_token():
    try:
        response = Client().login(
                    email=WYZE_EMAIL,
                    password=WYZE_PASSWORD,
                    key_id=WYZE_KEY_ID,
                    api_key=WYZE_API_KEY
                )
        return response['access_token']
    except WyzeApiError as e:
        logging.error(f"Wyze API Error: {str(e)}")
        return None

def get_lock_info(locks_client, lock_name):
    try:
        locks = locks_client.list()
        for lock in locks:
            if lock.nickname == lock_name:
                return lock
    except WyzeApiError as e:
        logging.error(f"Error retrieving lock info for {lock_name}: {str(e)}")
    return None

def get_lock_codes(locks_client, lock_mac):
    try:
        return locks_client.get_keys(device_mac=lock_mac)
    except WyzeApiError as e:
        logging.error(f"Error retrieving lock codes for {lock_mac}: {str(e)}")
        return None

def label_exists(existing_codes, label):
    return any(c.name == label for c in existing_codes)

def add_lock_code(locks_client, lock_mac, code, label, permission):
    try:
        response = locks_client.create_access_code(
            device_mac=lock_mac, 
            access_code=code, 
            name=label, 
            permission=permission
        )
        if response['ErrNo'] != 0:
            logging.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
        
        logging.info(f"{response}")
        return True
    except WyzeApiError as e:
        logging.error(f"Error adding lock code {label} to {lock_mac}: {str(e)}")
        send_slack_message(f"Error adding lock code {label} to {lock_mac}: {str(e)}")

def update_lock_code(locks_client, lock_mac, code_id, code, label, permission):
    try:
        response = locks_client.update_access_code(
            device_mac=lock_mac, 
            access_code_id=code_id, 
            access_code=code, 
            name=label, 
            permission=permission
        )

        if response['ErrNo'] != 0:
            logging.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
        
        logging.info(f"{response}")
        return True
    except WyzeApiError as e:
        logging.error(f"Error updating lock code {code} in {lock_mac}: {str(e)}")
        send_slack_message(f"Error updating lock code {code} in {lock_mac}: {str(e)}")

def delete_lock_code(locks_client, lock_mac, code_id):
    try:
        response = locks_client.delete_access_code(
            device_mac=lock_mac, 
            access_code_id=code_id
        )
        if response['ErrNo'] != 0:
            logging.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
            
        logging.info(f"{response}")
        return True
    except WyzeApiError as e:
        logging.error(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")
        send_slack_message(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")

def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
    except SlackApiError as e:
        logging.error(f"Slack API Error: {str(e)}")

def send_summary_slack_message(property_name, deletions, updates, additions, errors):
    message = f"Property: {property_name}\n"
    message += "Deleted Codes:\n" + ("\n".join([f"`{item}`" for item in deletions]) if deletions else "_-None-_") + "\n"
    message += "Updated Codes:\n" + ("\n".join([f"`{item}`" for item in updates]) if updates else "_-None-_") + "\n"
    message += "Added Codes:\n" + ("\n".join([f"`{item}`" for item in additions]) if additions else "_-None-_") + "\n"
    message += "Errors:\n" + ("\n".join([f"`{item}`" for item in errors]) if errors else "_-None-_") + "\n"
    send_slack_message(message)

def format_datetime(date_str, offset_hours=0):
    date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    date += timedelta(hours=offset_hours)
    return date

def get_user_id_from_existing_codes(existing_codes, user_id=None):
    if user_id is not None:
        return user_id

    for code in existing_codes:
        if hasattr(code, 'userid') and code.userid is not None:
            return code.userid

    return user_id

if __name__ == "__main__":
    process_reservations()
