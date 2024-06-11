import logging
import os
import time
import pytz
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from wyze_sdk import Client
from hospitable import authenticate_hospitable, get_properties, get_reservations
from slack_notify import send_slack_message
import brands.wyze.lock_sync as wyze_lock
from brands.wyze.wyze import get_wyze_token

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
TEST_PROPERTY_NAME = os.environ['TEST_PROPERTY_NAME']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
STORAGE_ACCOUNT_NAME = os.environ['STORAGE_ACCOUNT_NAME']
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'

if LOCAL_DEVELOPMENT:
    STORAGE_ACCOUNT_KEY = os.environ['STORAGE_ACCOUNT_KEY']
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    STORAGE_ACCOUNT_KEY = client.get_secret("STORAGE-ACCOUNT-KEY").value

def process_reservations(delete_all_guest_codes=False):
    logging.info('Processing reservations.')

    try:
        logging.info(f"Server Time: {datetime.now()}")
        timezone = pytz.timezone(TIMEZONE)
        current_time = datetime.now(timezone)
        logging.info(f"current_time: {current_time}")

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

            if not reservations and ALWAYS_SEND_SLACK_SUMMARY:
                send_slack_message(f"No reservations for property {property_name}.")
                continue

            lock_name = f"{property_name} - FD"

            if NON_PROD:
                if lock_name != TEST_PROPERTY_NAME:
                    send_slack_message(f"Skipping locks for property {property_name}.")
                    continue
                
            # Call Locks
            wyze_lock.sync(locks_client, lock_name, property_name, reservations, current_time, timezone, delete_all_guest_codes)

    except Exception as e:
        logging.error(f"Error in function: {str(e)}")
        send_slack_message(f"Error in function: {str(e)}")

if __name__ == "__main__" and LOCAL_DEVELOPMENT:
    process_reservations()
