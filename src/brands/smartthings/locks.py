import os
from devices import Device
from datetime import datetime
from slack_notify import send_slack_message
from utilty import format_datetime
from brands.smartthings.smartthings import *
import utilty
import time  # Import time module for sleep

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'
SMARTTHINGS_API_DELAY_SECONDS = int(os.environ['SMARTTHINGS_API_DELAY_SECONDS'])
LOCK_CODE_ADD_MAX_ATTEMPTS = int(os.environ['LOCK_CODE_ADD_MAX_ATTEMPTS'])
LOCK_CODE_VERIFY_MAX_ATTEMPTS = int(os.environ['LOCK_CODE_VERIFY_MAX_ATTEMPTS'])

def sync(lock_name, property_name, location, reservations, current_time):
    """
    Synchronize lock codes with reservation data for SmartThings locks.
    
    Args:
        lock_name (str): The name of the lock to update
        property_name (str): The property name for logging purposes
        location (str): The location name to search for in SmartThings
        reservations (list): List of reservation dictionaries with guest, phone, checkin, checkout data
        current_time (datetime): The current time used to determine active reservations
        
    Returns:
        tuple: (deletions, updates, additions, errors) lists tracking changes made
    """
    logger.info(f'Processing SmartThings {Device.LOCK.value} reservations.')
    deletions = []
    updates = []
    additions = []
    errors = []
    active_guest_user_names = []

    try:
        location_id = find_location_by_name(location)
        if location_id is None:
            error_msg = f"Unable to fetch location ID for {Device.LOCK.value} '{lock_name}' at {property_name}."
            send_slack_message(error_msg)
            errors.append(error_msg)
            return deletions, updates, additions, errors
        
        # Get locks with current codes - this uses refresh mechanism to ensure latest data
        locks_with_users = get_locks(location_id)
        if locks_with_users is None:
            send_slack_message(f"Unable to fetch {Device.LOCK.value} with users for {lock_name} at {property_name}.")
            return deletions, updates, additions, errors
        
        lock = find_lock_by_name(locks_with_users, lock_name)
        if lock is None:
            send_slack_message(f"Unable to fetch {Device.LOCK.value} for {lock_name} at {property_name}.")
            return deletions, updates, additions, errors
        
        # Process reservations
        for reservation in reservations:
            # Validate reservation data
            if 'guest' not in reservation or not reservation['guest']:
                error_msg = f"🔍 Missing Data: Reservation is missing guest name for `{property_name}`. Skipping lock code management for this reservation."
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            guest_name = reservation['guest']
            guest_first_name = guest_name.split()[0]
            
            # Check for valid phone number
            if 'phone' not in reservation or not reservation['phone']:
                error_msg = f"📱 Missing Phone Number: Guest `{guest_first_name}` has no phone number associated with their reservation at `{property_name}`. Skipping code creation."
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            # Extract last 4 digits of phone number
            phone = reservation['phone']
            try:
                # Remove any non-numeric characters
                phone_clean = ''.join(filter(str.isdigit, phone))
                if len(phone_clean) < 4:
                    error_msg = f"📱 Invalid Phone Number: Phone number for guest `{guest_first_name}` at `{property_name}` doesn't have enough digits. Skipping code creation."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                    
                phone_last4 = phone_clean[-4:]
                
                if not phone_last4.isdigit():
                    error_msg = f"📱 Non-numeric Phone: Unable to extract numeric code from phone number for guest `{guest_first_name}` at `{property_name}`. Skipping code creation."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            except Exception as e:
                error_msg = f"📱 Phone Number Error: Failed to process phone number for guest `{guest_first_name}` at `{property_name}`. Error: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
            
            label = f"Guest {guest_first_name}"
            label += f" {reservation['checkin'][:10].replace('-', '')}"
            checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
            checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

            # Only consider the reservation active if checkout time hasn't passed
            if current_time < checkout_time:
                active_guest_user_names.append(label)
                
            if checkin_time <= current_time < checkout_time:
                if not find_user_id_by_name(lock, label):
                    logger.info(f"ADD: {property_name}; {Device.LOCK.value} label: {label}")
                    # Ensure code_verified is always defined
                    code_verified = False
                    # Try adding the code up to configured number of times
                    for attempt in range(1, LOCK_CODE_ADD_MAX_ATTEMPTS + 1):
                        logger.info(f"🔑 Attempt {attempt} of {LOCK_CODE_ADD_MAX_ATTEMPTS} to add {Device.LOCK.value} code for `{guest_first_name}` at `{property_name}`")
                        if add_user_code(lock, label, phone_last4):
                            # Try validating the code up to configured number of times
                            code_verified = False
                            for verify_attempt in range(1, LOCK_CODE_VERIFY_MAX_ATTEMPTS + 1):
                                logger.info(f"🔍 Validation attempt {verify_attempt} of {LOCK_CODE_VERIFY_MAX_ATTEMPTS} for {Device.LOCK.value} code '{label}'")
                                time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
                                
                                # Refresh lock data to get latest codes from the physical device
                                refreshed_lock = refresh_lock_data(location_id, lock_name)
                                if refreshed_lock and find_user_id_by_name(refreshed_lock, label):
                                    additions.append(f"{Device.LOCK.value} - {lock_name}: {label}")
                                    success_msg = f"🔑 Added {Device.LOCK.value} code for `{guest_first_name}` at `{property_name}` (verified on attempt {verify_attempt})"
                                    send_slack_message(success_msg)
                                    code_verified = True
                                    # Update the lock object with refreshed data for subsequent operations
                                    lock = refreshed_lock
                                    break
                                logger.warning(f"⚠️ Verification attempt {verify_attempt} failed for '{label}'. Waiting before retry...")
                            if code_verified:
                                break
                            elif verify_attempt == LOCK_CODE_VERIFY_MAX_ATTEMPTS:
                                logger.error(f"❌ Failed to verify {Device.LOCK.value} code after {LOCK_CODE_VERIFY_MAX_ATTEMPTS} attempts for {lock_name}: {label}")
                                if attempt == LOCK_CODE_ADD_MAX_ATTEMPTS:
                                    error_msg = f"🔐 Failed to add and verify {Device.LOCK.value} code after {LOCK_CODE_ADD_MAX_ATTEMPTS} attempts for {lock_name}: {label}"
                                    logger.error(error_msg)
                                    send_slack_message(error_msg)
                                    errors.append(error_msg)
                                continue  # Try adding the code again if attempts remain
                        else:
                            error_msg = f"🔐 Failed to add {Device.LOCK.value} code for {lock_name}: {label} (attempt {attempt})"
                            logger.error(error_msg)
                            if attempt < LOCK_CODE_ADD_MAX_ATTEMPTS:
                                logger.info(f"Waiting {SMARTTHINGS_API_DELAY_SECONDS} seconds before retry...")
                                time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
                                continue
                            send_slack_message(error_msg)
                            errors.append(error_msg)
                            break
                    # After all attempts, if code was never verified, log error
                    if not code_verified:
                        error_msg = f"❌ Failed to add and verify {Device.LOCK.value} code after all attempts for {lock_name}: {label}"
                        logger.error(error_msg)
                        send_slack_message(error_msg)
                        errors.append(error_msg)

        # Delete old guest codes - refresh lock data to get current state
        logger.info(f"🔄 Refreshing lock data before cleanup for `{lock_name}` at `{property_name}`")
        refreshed_lock_for_cleanup = refresh_lock_data(location_id, lock_name)
        if refreshed_lock_for_cleanup:
            lock = refreshed_lock_for_cleanup
            logger.info(f"✅ Using refreshed lock data with {len(lock['users'])} total codes for cleanup")
        else:
            logger.warning(f"⚠️ Failed to refresh lock data for cleanup, using existing data")
            
        guest_user_names = find_all_guest_user_names(lock)
        purge_user_names = utilty.subtract_string_lists(guest_user_names, active_guest_user_names)

        if purge_user_names:
            logger.info(f"Found {len(purge_user_names)} lock codes to remove for {property_name}")
            for user_name in purge_user_names:
                user_id = find_user_id_by_name(lock, user_name)
                if user_id and delete_user_code(lock, user_id):
                    # Wait a moment then verify the deletion was successful
                    time.sleep(SMARTTHINGS_API_DELAY_SECONDS)
                    
                    # Refresh and verify the code was actually deleted
                    verification_lock = refresh_lock_data(location_id, lock_name)
                    if verification_lock and not find_user_id_by_name(verification_lock, user_name):
                        deletions.append(f"{Device.LOCK.value} - {lock_name}: {user_name}")
                        logger.info(f"✅ DELETE: {property_name}; user: {user_name} (verified)")
                        success_msg = f"🗑️ Deleted {Device.LOCK.value} code `{user_name}` at `{property_name}`"
                        send_slack_message(success_msg)
                        # Update lock for next iteration
                        lock = verification_lock
                    else:
                        error_msg = f"⚠️ Failed to verify deletion of {Device.LOCK.value} code `{user_name}` at `{property_name}`"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        send_slack_message(error_msg)
                else:
                    errors.append(f"Deleting {Device.LOCK.value} Code for {lock_name}: {user_name}")

    except Exception as e:
        error = f"Error in SmartThings {Device.LOCK.value} function: {str(e)}"
        logger.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmartThings {Device.LOCK.value} function: {str(e)}")

    return deletions, updates, additions, errors
