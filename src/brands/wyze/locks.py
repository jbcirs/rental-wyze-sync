import logging
import os
import time
import pytz
from devices import Device
from datetime import datetime
from wyze_sdk.models.devices.locks import LockKeyPermission, LockKeyPermissionType
from slack_notify import send_slack_message, send_summary_slack_message
from utilty import format_datetime
from brands.wyze.wyze import (
    get_lock_info, 
    get_lock_codes, 
    find_code, 
    add_lock_code, 
    update_lock_code, 
    delete_lock_code,  
    get_user_id_from_existing_codes
)

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'
WYZE_API_DELAY_SECONDS = int(os.environ['WYZE_API_DELAY_SECONDS'])

def sync(locks_client, lock_name, property_name, reservations, current_time, timezone, delete_all_guest_codes=False):
    logging.info(f'Processing Wyze {Device.LOCK.value} reservations.')
    deletions = []
    updates = []
    additions = []
    errors = []

    try:
        lock_info = get_lock_info(locks_client, lock_name)
        if lock_info is None:
            send_slack_message(f"Unable to fetch lock info for {lock_name} at {property_name}.")
            return

        lock_mac = lock_info.mac
        existing_codes = get_lock_codes(locks_client, lock_mac)

        if existing_codes is None:
            send_slack_message(f"Unable to fetch {Device.LOCK.value} codes for {lock_name} at {property_name}.")
            return

        locks_client._user_id = get_user_id_from_existing_codes(existing_codes, locks_client._user_id)

        if locks_client._user_id is None:
            send_slack_message(f":4934-error: Unable to find user_id")
            return

        deletions = []
        updates = []
        additions = []
        errors = []

        deleted_codes = False
        
        # Delete old guest codes
        for code in existing_codes:
            if code.name.startswith("Guest"):
                permission = code.permission
                if delete_all_guest_codes or (permission.type == LockKeyPermissionType.DURATION and permission.end < datetime.now()):
                    if delete_lock_code(locks_client, lock_mac, code.id):
                        deletions.append(f"{Device.LOCK.value} - {lock_name}: {code.name}")
                    else:
                        errors.append(f"Deleting {Device.LOCK.value} Code for {lock_name}: {code.name}")
                    
                    deleted_codes = True

        # Update existing codes after delete    
        if deleted_codes:
            time.sleep(WYZE_API_DELAY_SECONDS)   # Slow down API calls for Wyze locks
            existing_codes = get_lock_codes(locks_client, lock_mac)

        # Process reservations
        for reservation in reservations:
            guest_name = reservation['guest']
            guest_first_name = guest_name.split()[0]
            phone_last4 = reservation['phone'][-4:]
            label = f"Guest {guest_first_name}"
            label += f" {reservation['checkin'][:10].replace('-', '')}"

            checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
            checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

            if current_time < checkout_time:

                permission = LockKeyPermission(
                    type=LockKeyPermissionType.DURATION, 
                    begin=checkin_time, 
                    end=checkout_time
                )

                code = find_code(existing_codes, label)

                if not code:
                    logging.info(f"ADD: {property_name}; label: {label}")
                    if add_lock_code(locks_client, lock_mac, phone_last4, label, permission):
                        additions.append(f"{Device.LOCK.value} - {lock_name}: {label}")
                    else:
                        errors.append(f"Adding {Device.LOCK.value} Code for {lock_name}: {label}")
                else:
                    begin_utc = code.permission.begin.replace(tzinfo=pytz.utc)
                    end_utc = code.permission.end.replace(tzinfo=pytz.utc)
                    checkin_utc = checkin_time.astimezone(pytz.utc)
                    checkout_utc = checkout_time.astimezone(pytz.utc)

                    if LOCAL_DEVELOPMENT:
                        begin_utc = timezone.localize(code.permission.begin)
                        end_utc = timezone.localize(code.permission.end)
                        checkin_utc = checkin_time
                        checkout_utc = checkout_time

                    if begin_utc != checkin_utc or end_utc != checkout_utc:
                        logging.info(f"UPDATE: {property_name}; label: {label}")
                        if update_lock_code(locks_client, lock_mac, code.id, phone_last4, label, permission):
                            updates.append(f"{Device.LOCK.value} - {lock_name}: {label}")
                        else:
                            errors.append(f"Updating {Device.LOCK.value} Code for {lock_name}: {label}")

    except Exception as e:
        error = f"Error in Wyze {Device.LOCK.value} function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in Wyze {Device.LOCK.value} function: {str(e)}")

    return deletions, updates, additions, errors
