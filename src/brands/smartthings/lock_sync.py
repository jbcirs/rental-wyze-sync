import logging
import os
import time
import pytz
from datetime import datetime
from slack_notify import send_slack_message
from utilty import format_datetime
from brands.smartthings.smartthings import *
import utilty

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'

def sync(lock_name, property_name, location, reservations, current_time):
    logging.info('Processing SmartThings reservations.')
    deletions = []
    updates = []
    additions = []
    errors = []
    active_guest_user_names = []

    try:
        location_id = find_location_by_name(location)
        if location_id is None:
            send_slack_message(f"Unable to fetch location ID for {lock_name} at {property_name}.")
            return
        
        locks_with_users = get_locks(location_id)
        if locks_with_users is None:
            send_slack_message(f"Unable to fetch locks with users for {lock_name} at {property_name}.")
            return
        
        lock = find_lock_by_name(locks_with_users,lock_name)
        if lock is None:
            send_slack_message(f"Unable to fetch lock for {lock_name} at {property_name}.")
            return
        
        # Process reservations
        for reservation in reservations:
            guest_name = reservation['guest']
            guest_first_name = guest_name.split()[0]
            phone_last4 = reservation['phone'][-4:]
            label = f"Guest {guest_first_name}"
            label += f" {reservation['checkin'][:10].replace('-', '')}"
            active_guest_user_names.append(label)
            checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
            checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

            if checkin_time <= current_time < checkout_time:
                if not find_user_id_by_name(lock, label):
                    logging.info(f"ADD: {property_name}; label: {label}")
                    if add_user_code(lock, user_name, phone_last4):
                        additions.append(f"{lock_name}: {label}")
                    else:
                        errors.append(f"Adding Code for {lock_name}: {label}")

        # Delete old guest codes
        guest_user_names = find_all_guest_user_names(lock)
        purge_user_names = utilty.subtract_string_lists(guest_user_names, active_guest_user_names)

        if purge_user_names:
            for user_name in guest_user_names:
                user_id = find_user_id_by_name(lock,user_name)

                if delete_user_code(lock, user_id):
                    deletions.append(f"{lock_name}: {user_name}")
                else:
                    errors.append(f"Deleting Code for {lock_name}: {user_name}")

    except Exception as e:
        error = f"Error in SmatThings function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmatThings function: {str(e)}")

    return deletions, updates, additions, errors