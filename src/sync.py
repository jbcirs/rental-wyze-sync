# Rental Property Smart Device Synchronization System
# This module coordinates and manages smart devices (locks, lights, thermostats) for rental properties
# based on reservation data from hospitality management systems.

import os
import time
import pytz
import json
from logger import Logger
from typing import List, Dict, Any, Tuple
from devices import Devices
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from wyze_sdk import Client
from hospitable import authenticate_hospitable, get_properties, get_reservations
from slack_notify import send_slack_message, send_summary_slack_message
import brands.wyze.locks as wyze_lock
import brands.wyze.thermostats as wyze_thermostats
from brands.wyze.wyze import get_wyze_token
import brands.smartthings.locks as smartthings_lock
import brands.smartthings.lights as smartthings_lights
import brands.smartthings.thermostats as smartthings_thermostats
from thermostat import get_thermostat_settings, should_process_thermostat_for_frequency, check_temperature_alerts_with_current_device
from azure.data.tables import TableServiceClient
from utilty import format_datetime, filter_by_key, is_valid_hour
from light import get_light_settings
from when import When

# === Configuration Constants ===
# Key Vault URL for retrieving secrets
VAULT_URL = os.environ["VAULT_URL"]
# Hours before check-in time to apply settings
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
# Hours after check-out time to apply settings
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
# Flag to run in non-production mode (limited to test property)
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
# Property to use in non-production mode
TEST_PROPERTY_NAME = os.environ['TEST_PROPERTY_NAME']
# Flag for local development environment
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
# Azure storage account for property data
STORAGE_ACCOUNT_NAME = os.environ['STORAGE_ACCOUNT_NAME']
# Local timezone for time calculations
TIMEZONE = os.environ['TIMEZONE']
# Send Slack summary even when no changes occurred
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'

# Service/brand identifiers
HOSPITABLE = "Hospitable"
SMARTTHINGS = "smartthings"
WYZE = "wyze"

logger = Logger()

if LOCAL_DEVELOPMENT:
    STORAGE_CONNECTION_STRING = os.environ['STORAGE_CONNECTION_STRING']
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    STORAGE_CONNECTION_STRING = client.get_secret("STORAGE-CONNECTION-STRING").value

def active_property(devices: List[Devices]) -> List[Dict[str, Any]]:
    """
    Retrieve active properties from Azure Table Storage that have the specified devices configured.
    
    Args:
        devices: List of device types to check for in properties
        
    Returns:
        List of property records with active status and required device configurations
    """
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
            logger.info(f"Processing entry with PartitionKey: {entry['PartitionKey']}, RowKey: {entry['RowKey']}")
            
            for device in devices:
                # Check if the device property exists and is not empty
                if device.value in entry and entry[device.value]:
                    try:
                        properties.append(entry)
                        # Break after adding to avoid duplicates if property has multiple requested devices
                        break
                    except json.JSONDecodeError as json_err:
                        logger.error(f"JSON decoding error for entry {entry['RowKey']}: {str(json_err)}")
                    except Exception as e:
                        logger.error(f"Error processing entry {entry['RowKey']}: {str(e)}")
                else:
                    logger.warning(f"No '{device.value}' property found or '{device.value}' property is empty for entry {entry['RowKey']}")
    except Exception as e:
        logger.error(f"An error occurred while querying the table: {str(e)}")

    return properties
    
def get_settings(property: Dict[str, Any], brand: str) -> Dict[str, Any]:
    """
    Extract settings for a specific brand from the property configuration.
    
    Args:
        property: Property configuration dictionary
        brand: Brand identifier (e.g., 'wyze', 'smartthings')
        
    Returns:
        Brand-specific settings dictionary or None if not found
    """
    brand_settings = json.loads(property["BrandSettings"])
    for item in brand_settings:
        if item['brand'] == brand:
            return item
    return None

def process_reservations(devices: List[Devices] = [Devices.LOCKS], delete_all_guest_codes: bool = False) -> None:
    """
    Main function to process property reservations and synchronize devices accordingly.
    
    Args:
        devices: List of device types to synchronize
        delete_all_guest_codes: Flag to force deletion of all guest access codes
    """
    logger.info(f'Starting reservation processing for device types: {[d.value for d in devices]}')

    try:
        # Initialize timezone and current time
        logger.info(f"Server Time: {datetime.now()}")
        timezone = pytz.timezone(TIMEZONE)
        current_time = datetime.now(timezone)
        logger.info(f"Local time ({TIMEZONE}): {current_time}")

        # Authenticate with Hospitable
        logger.info("Authenticating with Hospitable API")
        hospitable_token = authenticate_hospitable()
        if not hospitable_token:
            error_msg = "Unable to authenticate with Hospitable API."
            logger.error(error_msg)
            send_slack_message(error_msg)
            return

        # Fetch properties from Hospitable
        logger.info("Fetching properties from Hospitable API")
        hospitable_properties = get_properties(hospitable_token)
        if not hospitable_properties:
            error_msg = "Unable to fetch properties from Hospitable API."
            logger.error(error_msg)
            send_slack_message(error_msg)
            return
        
        # Authenticate with Wyze
        logger.info("Authenticating with Wyze API")
        wyze_token = get_wyze_token()
        if not wyze_token:
            error_msg = "Unable to authenticate with Wyze API."
            logger.error(error_msg)
            send_slack_message(error_msg)
            return

        wyze_client = Client(token=wyze_token)

        # Get active properties from database
        logger.info(f"Retrieving active properties with devices: {[d.value for d in devices]}")
        table_properties = active_property(devices)
        logger.info(f"Found {len(table_properties)} active properties to process")
        
        # Process each property
        for property in table_properties:
            # Initialize tracking lists for this property
            property_deletions, property_updates, property_additions, property_errors = [], [], [], []
            property_name = property['PartitionKey']

            # Get reservations for this property
            if property["RowKey"] == HOSPITABLE:
                property_id = next((prop['id'] for prop in hospitable_properties if prop['name'] == property_name), None)
                reservations = get_reservations(hospitable_token, property_id)
            else:
                property_id = ""
                reservations = None

            # Skip non-test properties in non-production mode
            if NON_PROD and property_name != TEST_PROPERTY_NAME:
                send_slack_message(f"Skipping property {property_name} in non-production mode.")
                continue

            # Process different device types if requested
            if Devices.LIGHTS in devices:
                process_property_lights(property, reservations, current_time, property_updates, property_errors)

            if Devices.THERMOSTATS in devices:
                wyze_thermostats_client = wyze_client.thermostats
                process_property_thermostats(property, reservations, wyze_thermostats_client, current_time, property_updates, property_errors)

            # Log if no reservations found
            if not reservations and ALWAYS_SEND_SLACK_SUMMARY:
                send_slack_message(f"No reservations for property {property_name}.")
            
            if Devices.LOCKS in devices:
                wyze_locks_client = wyze_client.locks
                process_property_locks(property, reservations, wyze_locks_client, current_time, timezone, delete_all_guest_codes, property_deletions, property_updates, property_additions, property_errors)

            # Send summary message if there were changes or if always-send flag is set
            if ALWAYS_SEND_SLACK_SUMMARY or any([property_deletions, property_updates, property_additions, property_errors]):
                send_summary_slack_message(property_name, property_deletions, property_updates, property_additions, property_errors)

        logger.info("Reservation processing completed successfully")

    except Exception as e:
        logger.error(f"Error in process_reservations: {str(e)}")
        send_slack_message(f"Error in process_reservations: {str(e)}")

def process_property_locks(
    property: Dict[str, Any], 
    reservations: List[Dict[str, Any]], 
    wyze_locks_client: Any, 
    current_time: datetime, 
    timezone: pytz.timezone, 
    delete_all_guest_codes: bool, 
    property_deletions: List[str], 
    property_updates: List[str], 
    property_additions: List[str], 
    property_errors: List[str]
) -> None:
    """
    Process locks for a specific property, updating access based on reservations.
    
    Args:
        property: Property configuration
        reservations: List of reservation data
        wyze_locks_client: Wyze API client for locks
        current_time: Current datetime in the property's timezone
        timezone: pytz timezone object
        delete_all_guest_codes: Flag to force deletion of all guest access codes
        property_deletions: List to track code deletions (modified in-place)
        property_updates: List to track code updates (modified in-place)
        property_additions: List to track code additions (modified in-place)
        property_errors: List to track errors (modified in-place)
    """
    locks = json.loads(property['Locks'])
    property_name = property['PartitionKey']
    
    for lock in locks:
        logger.info(f"Processing lock: {lock['brand']} - {lock['name']}")

        if lock['brand'] == WYZE:
            # Process Wyze locks
            deletions, updates, additions, errors = wyze_lock.sync(
                wyze_locks_client, lock['name'], property_name, reservations, 
                current_time, timezone, delete_all_guest_codes
            )
        
        elif lock['brand'] == SMARTTHINGS:
            # Process SmartThings locks
            smarthings_settings = get_settings(property, SMARTTHINGS)
            deletions, updates, additions, errors = smartthings_lock.sync(
                lock['name'], property_name, smarthings_settings["location"], 
                reservations, current_time
            )
        
        # Collect results from lock processing
        property_deletions.extend(deletions)
        property_updates.extend(updates)
        property_additions.extend(additions)
        property_errors.extend(errors)

def process_property_lights(
    property: Dict[str, Any], 
    reservations: List[Dict[str, Any]], 
    current_time: datetime, 
    property_updates: List[str], 
    property_errors: List[str]
) -> None:
    """
    Process lights for a specific property, updating states based on reservations and time.
    
    Args:
        property: Property configuration
        reservations: List of reservation data
        current_time: Current datetime in the property's timezone
        property_updates: List to track updates (modified in-place)
        property_errors: List to track errors (modified in-place)
    """
    lights = json.loads(property['Lights'])
    location = json.loads(property['Location'])
    property_name = property['PartitionKey']

    for light in lights:
        logger.info(f"Processing light: {light['brand']} - {light['name']}")
        updates = []
        errors = []

        # Get the desired light settings based on current state
        light_state, change_state, light_errors = get_light_settings(light, location, reservations, current_time)

        if len(light_errors) > 0:
            errors.append(light_errors)
        elif change_state:
            # Only attempt state change if needed
            if light['brand'] == SMARTTHINGS:
                smarthings_settings = get_settings(property, SMARTTHINGS)
                updates, errors = smartthings_lights.sync(light, property_name, smarthings_settings['location'], light_state)
            
        property_updates.extend(updates)
        property_errors.extend(errors)

def process_property_thermostats(
    property: Dict[str, Any], 
    reservations: List[Dict[str, Any]], 
    wyze_thermostats_client: Any, 
    current_time: datetime, 
    property_updates: List[str], 
    property_errors: List[str]
) -> None:
    """
    Process thermostats for a specific property, updating settings based on reservations and time.
    
    Args:
        property: Property configuration
        reservations: List of reservation data
        wyze_thermostats_client: Wyze API client for thermostats
        current_time: Current datetime in the property's timezone
        property_updates: List to track updates (modified in-place)
        property_errors: List to track errors (modified in-place)
    """
    thermostats = json.loads(property['Thermostats'])
    location = json.loads(property['Location'])
    property_name = property['PartitionKey']

    for thermostat in thermostats:
        logger.info(f"Processing thermostat: {thermostat['brand']} - {thermostat['manufacture']} - {thermostat['name']}")
        has_reservation = False
        reservation_start_date = None
        temperature_config = None

        # Determine if there's an active reservation
        if reservations:
            for reservation in reservations:
                checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
                checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

                logger.info(f"checkin_time: {checkin_time.date()}")
                logger.info(f"checkout_time: {checkout_time.date()}")

                # Check if current date falls within reservation period
                if checkin_time.date() <= current_time.date() < checkout_time.date():
                    filtered_thermostat = filter_by_key(thermostat, "temperatures", When.RESERVATIONS_ONLY.value)
                    has_reservation = True
                    reservation_start_date = checkin_time.date()
                    
                    # Find the specific temperature configuration for the current mode
                    # We'll determine mode first, then find the matching config
                    break
                else:
                    filtered_thermostat = filter_by_key(thermostat, "temperatures", When.NON_RESERVATIONS.value)
        else:
            # No reservations, use non-reservation settings
            filtered_thermostat = filter_by_key(thermostat, "temperatures", When.NON_RESERVATIONS.value)

        logger.info(f"filtered_thermostat by When: {filtered_thermostat}")

        # Skip if current hour is not within operating hours
        if not is_valid_hour(filtered_thermostat, current_time):
            logger.info(f"Not a valid hour for {thermostat['name']} at {property_name}")
            continue
        
        # Get the desired thermostat settings
        mode, cool_temp, heat_temp, thermostat_scenario, freeze_protection = get_thermostat_settings(
            thermostat, location, reservation=has_reservation, mode=None, 
            temperatures=filtered_thermostat['temperatures']
        )

        # For reservation-only settings, check frequency and find the specific temperature config
        if has_reservation and reservation_start_date:
            # Find the temperature configuration that matches the determined mode
            for temp_config in filtered_thermostat['temperatures']:
                if temp_config.get('mode') == mode:
                    temperature_config = temp_config
                    break
            
            # Check temperature alerts FIRST - but we need current device settings, not target settings
            # This helps catch guests setting extreme temperatures that could run up costs
            if temperature_config and temperature_config.get('alerts'):
                logger.info(f"Checking temperature alerts for {thermostat['name']} at {property_name} (runs daily during reservations)")
                
                # Use the helper function to check alerts with current device settings
                alerts_sent = check_temperature_alerts_with_current_device(
                    thermostat['name'], property_name, thermostat, property, 
                    mode, cool_temp, heat_temp, temperature_config, wyze_thermostats_client
                )
                if alerts_sent:
                    logger.info(f"Temperature alerts sent for {thermostat['name']} at {property_name}: {len(alerts_sent)} alerts")
                else:
                    logger.info(f"No temperature alerts triggered for {thermostat['name']} at {property_name}")
            
            # Check if we should process thermostat updates based on frequency setting
            if temperature_config and not should_process_thermostat_for_frequency(
                temperature_config, reservation_start_date, current_time.date()
            ):
                logger.info(f"Skipping thermostat {thermostat['name']} at {property_name} - frequency setting doesn't allow processing today")
                continue
            
            # Validate temperature configuration if found
            if temperature_config:
                frequency = temperature_config.get('frequency', 'first_day')
                logger.info(f"Processing thermostat {thermostat['name']} with frequency: {frequency}")
                
                # Log if alerts are configured
                if temperature_config.get('alerts'):
                    alerts_enabled = temperature_config['alerts'].get('enabled', True)
                    logger.info(f"Temperature alerts {'enabled' if alerts_enabled else 'disabled'} for {thermostat['name']}")
            else:
                logger.warning(f"No temperature configuration found for mode '{mode}' in thermostat {thermostat['name']} at {property_name}")
        else:
            # No reservation - no alerts needed
            logger.info(f"No active reservation for {thermostat['name']} at {property_name} - skipping alert checks")

        # Apply settings based on thermostat brand
        if thermostat['brand'] == WYZE:
            updates, errors = wyze_thermostats.sync(
                wyze_thermostats_client, thermostat, mode, cool_temp, 
                heat_temp, thermostat_scenario, property_name
            )
        
        elif thermostat['brand'] == SMARTTHINGS:
            smarthings_settings = get_settings(property, SMARTTHINGS)
            updates, errors = smartthings_thermostats.sync(
                thermostat, mode, cool_temp, heat_temp, 
                property_name, smarthings_settings['location']
            )

        # Handle freeze protection override
        if freeze_protection:
            updates.append(f"Freeze protection override for {property_name} - {thermostat['name']}")
        
        property_updates.extend(updates)
        property_errors.extend(errors)


if __name__ == "__main__" and LOCAL_DEVELOPMENT:
    # For local testing, process only thermostats
    process_reservations([Devices.THERMOSTATS])
