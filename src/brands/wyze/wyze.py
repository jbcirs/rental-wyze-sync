import logging
import os
import time
import pytz
from datetime import datetime
from wyze_sdk import Client
from wyze_sdk.errors import WyzeApiError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from brands.wyze.error_mapping import get_error_message
from slack_notify import send_slack_message


VAULT_URL = os.environ["VAULT_URL"]
TIMEZONE = os.environ['TIMEZONE']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
WYZE_API_DELAY_SECONDS = int(os.environ['WYZE_API_DELAY_SECONDS'])


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

def find_code(existing_codes, label):
    return next((c for c in existing_codes if c.name == label), None)

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
        time.sleep(WYZE_API_DELAY_SECONDS) # Slow down API calls for Wyze locks

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
        time.sleep(WYZE_API_DELAY_SECONDS) # Slow down API calls for Wyze locks

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
        if response['ErrNo'] not in (0, 5021):
            logging.error(f"{get_error_message(response['ErrNo'])}; Original response: {response}")
            return False
            
        logging.info(f"{response}")
        time.sleep(WYZE_API_DELAY_SECONDS) # Slow down API calls for Wyze locks

        return True
    except WyzeApiError as e:
        logging.error(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")
        send_slack_message(f"Error deleting lock code {code_id} from {lock_mac}: {str(e)}")

def get_user_id_from_existing_codes(existing_codes, user_id=None):
    if user_id is not None:
        return user_id

    for code in existing_codes:
        if hasattr(code, 'userid') and code.userid is not None:
            return code.userid

    return user_id
