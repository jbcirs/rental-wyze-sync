import logging
import os
import time
import pytz
import json
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from wyze_sdk import Client
from hospitable import authenticate_hospitable, get_properties, get_reservations
from slack_notify import send_slack_message
import brands.wyze.lock_sync as wyze_lock
from brands.wyze.wyze import get_wyze_token
import brands.smartthings.lock_sync as smartthings_lock
from azure.data.tables import TableServiceClient

HOSPITABLE = "Hospitable"
SMARTTHINGS = "smartthings"
WYZE = "wyze"

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
TEST_PROPERTY_NAME = os.environ['TEST_PROPERTY_NAME']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
STORAGE_ACCOUNT_NAME = os.environ['STORAGE_ACCOUNT_NAME']
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'

if LOCAL_DEVELOPMENT:
    STORAGE_CONNECTION_STRING = os.environ['STORAGE_CONNECTION_STRING']
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    STORAGE_CONNECTION_STRING = client.get_secret("STORAGE-CONNECTION-STRING").value

def active_property_locks():
    table_name = "properties"
    properties = []


    # Initialize the Table service client
    table_service_client = TableServiceClient.from_connection_string(conn_str=STORAGE_CONNECTION_STRING)
    table_client = table_service_client.get_table_client(table_name)

    try:
        # Query to get all active entries
        filter_query = "Active eq true"
        active_entries = table_client.query_entities(query_filter=filter_query)

        # Process each active entry
        for entry in active_entries:
            logging.info(f"Processing entry with PartitionKey: {entry['PartitionKey']}, RowKey: {entry['RowKey']}")
            
            # Check if the 'Locks' property exists and is not empty
            if 'Locks' in entry and entry['Locks']:
                try:
                    properties.append(entry)
                except json.JSONDecodeError as json_err:
                    logging.error(f"JSON decoding error for entry {entry['RowKey']}: {str(json_err)}")
                except Exception as e:
                    logging.error(f"Error processing locks for entry {entry['RowKey']}: {str(e)}")
            else:
                logging.warning(f"No 'Locks' property found or 'Locks' property is empty for entry {entry['RowKey']}")
        return properties
    
    except Exception as e:
        logging.error(f"Error retrieving or processing entries: {str(e)}")
    
    return None


def process_reservations(delete_all_guest_codes=False):
    logging.info('Processing reservations.')

    try:
        logging.info(f"Server Time: {datetime.now()}")
        timezone = pytz.timezone(TIMEZONE)
        current_time = datetime.now(timezone)
        logging.info(f"current_time: {current_time}")

        hospitable_token = authenticate_hospitable()
        if not hospitable_token:
            send_slack_message("Unable to authenticate with Hospitable API.")
            return

        hospitable_properties = get_properties(hospitable_token)
        if not hospitable_properties:
            send_slack_message("Unable to fetch properties from Hospitable API.")
            return
        
        wyze_token = get_wyze_token()
        if not wyze_token:
            send_slack_message("Unable to authenticate with Wyze API.")
            return

        wyze_client = Client(token=wyze_token)
        wyze_locks_client = wyze_client.locks

        table_properties = active_property_locks()
        
        for property in table_properties:
            property_name = property['PartitionKey']

            if property["RowKey"] == HOSPITABLE:
                property_id = next((prop['id'] for prop in hospitable_properties if prop['name'] == property_name), None)
                reservations = get_reservations(hospitable_token, property_id)
            else:
                property_id = ""
                reservations = None

            if not reservations and ALWAYS_SEND_SLACK_SUMMARY:
                send_slack_message(f"No reservations for property {property_name}.")
                continue

            if NON_PROD:
                if property_name != TEST_PROPERTY_NAME:
                    send_slack_message(f"Skipping locks for property {property_name}.")
                    continue

            # Process the Locks property
            locks = json.loads(property['Locks'])
            print(locks)

            for lock in locks:
                print(f"Processing lock: {lock['brand']} - {lock['name']}")

                if lock['brand'] == WYZE:
                    wyze_lock.sync(wyze_locks_client, lock['name'], property_name, reservations, current_time, timezone, delete_all_guest_codes)
                elif lock['brand'] == SMARTTHINGS:
                    smartthings_lock.sync(lock['name'], property_name, property["Location"], reservations, current_time)


    except Exception as e:
        logging.error(f"Error in function: {str(e)}")
        send_slack_message(f"Error in function: {str(e)}")

if __name__ == "__main__" and LOCAL_DEVELOPMENT:
    process_reservations()
