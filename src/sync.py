import logging
import os
import time
import pytz
import json
from typing import List
from usno import is_sunset, is_sunrise, set_offset_minutes
from devices import Devices
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from wyze_sdk import Client
from hospitable import authenticate_hospitable, get_properties, get_reservations
from slack_notify import send_slack_message, send_summary_slack_message
import brands.wyze.locks as wyze_lock
from brands.wyze.wyze import get_wyze_token
import brands.smartthings.locks as smartthings_lock
import brands.smartthings.lights as smartthings_lights
import brands.smartthings.thermostats as smartthings_thermostats
from azure.data.tables import TableServiceClient
from utilty import validate_json

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

def active_property(devices: List[Devices]):
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
            
            for device in devices:
                # Check if the device property exists and is not empty
                if device.value in entry and entry[device.value]:
                    try:
                        properties.append(entry)
                    except json.JSONDecodeError as json_err:
                        logging.error(f"JSON decoding error for entry {entry['RowKey']}: {str(json_err)}")
                    except Exception as e:
                        logging.error(f"Error processing locks for entry {entry['RowKey']}: {str(e)}")
                else:
                    logging.warning(f"No '{device.value}' property found or '{device.value}' property is empty for entry {entry['RowKey']}")
    except Exception as e:
        logging.error(f"An error occurred while querying the table: {str(e)}")

    return properties
    
def get_settings(property, brand):
    brand_settings = json.loads(property["BrandSettings"])
    for item in brand_settings:
        if item['brand'] == brand:
            return item
    return None

def process_reservations(devices: List[Devices] = [Devices.LOCKS], delete_all_guest_codes=False):
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

        table_properties = active_property(devices)
        
        for property in table_properties:
            property_deletions, property_updates, property_additions, property_errors = [], [], [], []
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

            if NON_PROD and property_name != TEST_PROPERTY_NAME:
                send_slack_message(f"Skipping property {property_name}.")
                continue
            
            if Devices.LOCKS in devices:
                process_property_locks(property, reservations, wyze_locks_client, current_time, timezone, delete_all_guest_codes, property_deletions, property_updates, property_additions, property_errors)
            
            if Devices.LIGHTS in devices:
                process_property_lights(property, reservations, current_time, property_updates, property_errors)

            if Devices.THERMOSTATS in devices:
                process_property_thermostats(property, reservations, current_time, property_updates, property_errors)

            if ALWAYS_SEND_SLACK_SUMMARY or any([property_deletions, property_updates, property_additions, property_errors]):
                send_summary_slack_message(property_name, property_deletions, property_updates, property_additions, property_errors)

    except Exception as e:
        logging.error(f"Error in function: {str(e)}")
        send_slack_message(f"Error in function: {str(e)}")

def process_property_locks(property, reservations, wyze_locks_client, current_time, timezone, delete_all_guest_codes, property_deletions, property_updates, property_additions, property_errors):
    locks = json.loads(property['Locks'])
    property_name = property['PartitionKey']
    
    for lock in locks:
        logging.info(f"Processing lock: {lock['brand']} - {lock['name']}")

        if lock['brand'] == WYZE:
            deletions, updates, additions, errors = wyze_lock.sync(wyze_locks_client, lock['name'], property_name, reservations, current_time, timezone, delete_all_guest_codes)
        
        elif lock['brand'] == SMARTTHINGS:
            smarthings_settings = get_settings(property, SMARTTHINGS)
            deletions, updates, additions, errors = smartthings_lock.sync(lock['name'], property_name, smarthings_settings["location"], reservations, current_time)
        
        property_deletions.extend(deletions)
        property_updates.extend(updates)
        property_additions.extend(additions)
        property_errors.extend(errors)

def process_property_lights(property, reservations, current_time, property_updates, property_errors):
    lights = json.loads(property['Lights'])
    location =json.loads( property['Location'])
    property_name = property['PartitionKey']

    for light in lights:
        logging.info(f"Processing light: {light['brand']} - {light['name']}")
        
        if light['minutes_before_sunset'] is None and  light['minutes_after_sunrise'] is None:
            set_offset_minutes(light['minutes_before_sunset'],light['minutes_after_sunrise'])

        if light['minutes_before_sunset'] is None:
            sunset = False
        else:
            sunset = is_sunset(location['latitude'], location['longitude'], light['minutes_before_sunset'], current_time)
        
        if light['minutes_after_sunrise'] is None:
            sunrise = False
        else:
            sunrise = is_sunrise(location['latitude'], location['longitude'], light['minutes_after_sunrise'], current_time)

        if light['brand'] == SMARTTHINGS:
            smarthings_settings = get_settings(property, SMARTTHINGS)
            updates, errors = smartthings_lights.sync(light, sunset, sunrise, property_name, smarthings_settings['location'], reservations, current_time)
        
        property_updates.extend(updates)
        property_errors.extend(errors)

def process_property_thermostats(property, reservations, current_time, property_updates, property_errors):
    thermostats = json.loads(property['Thermostats'])
    location =json.loads( property['Location'])
    property_name = property['PartitionKey']

    for thermostat in thermostats:
        logging.info(f"Processing thermostat: {thermostat['brand']} - {thermostat['manufacture']} - {thermostat['name']}")

        if thermostat['brand'] == SMARTTHINGS:
            smarthings_settings = get_settings(property, SMARTTHINGS)
            updates, errors = smartthings_thermostats.sync(thermostat, property_name, smarthings_settings['location'], reservations, current_time)
        
        property_updates.extend(updates)
        property_errors.extend(errors)


if __name__ == "__main__" and LOCAL_DEVELOPMENT:
    process_reservations([Devices.LIGHTS])
