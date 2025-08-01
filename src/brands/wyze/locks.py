import os
import time
import pytz
from devices import Device
from datetime import datetime
from wyze_sdk.models.devices.locks import LockKeyPermission, LockKeyPermissionType
from slack_notify import send_slack_message, send_summary_slack_message
from utilty import format_datetime
from brands.wyze.wyze import *

# Configuration
VAULT_URL = os.environ["VAULT_URL"]
CHECK_IN_OFFSET_HOURS = int(os.environ['CHECK_IN_OFFSET_HOURS'])
CHECK_OUT_OFFSET_HOURS = int(os.environ['CHECK_OUT_OFFSET_HOURS'])
NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
TIMEZONE = os.environ['TIMEZONE']
ALWAYS_SEND_SLACK_SUMMARY = os.environ.get('ALWAYS_SEND_SLACK_SUMMARY', 'false').lower() == 'true'
WYZE_API_DELAY_SECONDS = int(os.environ['WYZE_API_DELAY_SECONDS'])
LOCK_CODE_ADD_MAX_ATTEMPTS = int(os.environ['LOCK_CODE_ADD_MAX_ATTEMPTS'])
LOCK_CODE_VERIFY_MAX_ATTEMPTS = int(os.environ['LOCK_CODE_VERIFY_MAX_ATTEMPTS'])

def sync(client, lock_name, property_name, reservations, current_time, timezone, delete_all_guest_codes=False):
    """
    Synchronize Wyze lock access codes with guest reservations.
    
    Args:
        client: Wyze API client
        lock_name: Name of the lock device
        property_name: Name of the property for logging purposes
        reservations: List of reservation dictionaries containing guest info and dates
        current_time: Current datetime for determining which codes to manage
        timezone: Timezone object for date/time conversions
        delete_all_guest_codes: If True, delete all guest codes regardless of expiration
        
    Returns:
        Tuple of (deletions, updates, additions, errors) lists tracking operations
    """
    logger.info(f'Processing Wyze {Device.LOCK.value} reservations.')
    deletions = []
    updates = []
    additions = []
    errors = []

    try:
        # Get the lock device from Wyze
        lock_info = get_device_by_name(client, lock_name)
        if lock_info is None:
            error_msg = f"Device Not Found: Unable to fetch {Device.LOCK.value} info for {lock_name} at {property_name}. Please verify the {Device.LOCK.value} exists and is connected."
            slack_msg = f"❓ Device Not Found: Unable to fetch {Device.LOCK.value} info for `{lock_name}` at `{property_name}`. Please verify the {Device.LOCK.value} exists and is connected."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(slack_msg)
            return deletions, updates, additions, errors

        # Get all existing access codes for the lock
        lock_mac = lock_info.mac
        existing_codes = get_lock_codes(client, lock_mac)

        if existing_codes is None:
            error_msg = f"{Device.LOCK.value} Code Error: Unable to fetch codes for {lock_name} at {property_name}. The {Device.LOCK.value} may be offline or experiencing connectivity issues."
            slack_msg = f"🔒 {Device.LOCK.value} Code Error: Unable to fetch codes for `{lock_name}` at `{property_name}`. The {Device.LOCK.value} may be offline or experiencing connectivity issues."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(slack_msg)
            return deletions, updates, additions, errors

        # Ensure we have a valid user ID for the API operations
        client._user_id = get_user_id_from_existing_codes(existing_codes, client._user_id)

        if client._user_id is None:
            error_msg = f"Authentication Error: Unable to find user_id for {Device.LOCK.value} {lock_name} at {property_name}. This may indicate an account permissions issue."
            slack_msg = f"🔑 Authentication Error: Unable to find user_id for {Device.LOCK.value} `{lock_name}` at `{property_name}`. This may indicate an account permissions issue."
            logger.error(error_msg)
            errors.append(error_msg)
            send_slack_message(slack_msg)
            return deletions, updates, additions, errors

        deleted_codes = False
        
        # Step 1: Delete expired or all guest codes based on configuration
        for code in existing_codes:
            if code.name.startswith("Guest"):
                permission = code.permission
                if delete_all_guest_codes or (permission.type == LockKeyPermissionType.DURATION and permission.end < datetime.now()):
                    if delete_lock_code(client, lock_mac, code.id):
                        deletions.append(f"{Device.LOCK.value} - {lock_name}: {code.name}")
                    else:
                        errors.append(f"Deleting {Device.LOCK.value} Code for {lock_name}: {code.name}")
                    
                    deleted_codes = True

        # Refresh the code list if any codes were deleted
        if deleted_codes:
            time.sleep(WYZE_API_DELAY_SECONDS)   # Slow down API calls for Wyze locks
            existing_codes = get_lock_codes(client, lock_mac)

        # Step 2: Process each reservation to add/update access codes
        if not reservations or len(reservations) == 0:
            info_msg = f"📆 No Reservations: No active reservations found for `{property_name}`. No lock codes will be added or updated."
            logger.info(info_msg)
            # Don't send to Slack as this might be normal
            return deletions, updates, additions, errors
            
        for reservation in reservations:
            # Validate reservation data
            if 'guest' not in reservation or not reservation['guest']:
                error_msg = f"Missing Data: Reservation is missing guest name for {property_name}. Skipping lock code management for this reservation."
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            guest_name = reservation['guest']
            guest_first_name = guest_name.split()[0]
            
            # Check for valid phone number
            if 'phone' not in reservation or not reservation['phone']:
                error_msg = f"Missing Phone Number: Guest {guest_first_name} has no phone number associated with their reservation at {property_name}. Skipping code creation."
                logger.error(error_msg)
                errors.append(error_msg)
                continue
                
            # Extract last 4 digits of phone number
            phone = reservation['phone']
            try:
                # Remove any non-numeric characters
                phone_clean = ''.join(filter(str.isdigit, phone))
                if len(phone_clean) < 4:
                    error_msg = f"Invalid Phone Number: Phone number for guest {guest_first_name} at {property_name} doesn't have enough digits. Skipping code creation."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                    
                phone_last4 = phone_clean[-4:]
                
                if not phone_last4.isdigit():
                    error_msg = f"Non-numeric Phone: Unable to extract numeric code from phone number for guest {guest_first_name} at {property_name}. Skipping code creation."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            except Exception as e:
                error_msg = f"Phone Number Error: Failed to process phone number for guest {guest_first_name} at {property_name}. Error: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
            
            # Create a unique label that includes guest name and check-in date
            label = f"Guest {guest_first_name}"
            label += f" {reservation['checkin'][:10].replace('-', '')}"

            # Calculate check-in and check-out times with configured offsets
            checkin_time = format_datetime(reservation['checkin'], CHECK_IN_OFFSET_HOURS, TIMEZONE)
            checkout_time = format_datetime(reservation['checkout'], CHECK_OUT_OFFSET_HOURS, TIMEZONE)

            # Only manage codes for current and future reservations
            if current_time < checkout_time:
                # Create permission with duration (time-limited access)
                permission = LockKeyPermission(
                    type=LockKeyPermissionType.DURATION, 
                    begin=checkin_time, 
                    end=checkout_time
                )

                # Check if code already exists
                code = find_code(existing_codes, label)

                if not code:
                    logger.info(f"ADD: {property_name}; {Device.LOCK.value} label: {label}")
                    
                    # Try adding the code up to configured number of times
                    for attempt in range(1, LOCK_CODE_ADD_MAX_ATTEMPTS + 1):
                        logger.info(f"🔑 Attempt {attempt} of {LOCK_CODE_ADD_MAX_ATTEMPTS} to add {Device.LOCK.value} code for `{guest_first_name}` at `{property_name}`")
                        
                        if add_lock_code(client, lock_mac, phone_last4, label, permission):
                            # Try validating the code up to configured number of times
                            code_verified = False
                            for verify_attempt in range(1, LOCK_CODE_VERIFY_MAX_ATTEMPTS + 1):
                                logger.info(f"🔍 Validation attempt {verify_attempt} of {LOCK_CODE_VERIFY_MAX_ATTEMPTS} for {Device.LOCK.value} code '{label}'")
                                time.sleep(WYZE_API_DELAY_SECONDS)
                                
                                updated_codes = get_lock_codes(client, lock_mac)
                                if find_code(updated_codes, label):
                                    additions.append(f"{Device.LOCK.value} - {lock_name}: {label}")
                                    success_msg = f"🔑 Added {Device.LOCK.value} code for `{guest_first_name}` at `{property_name}` (verified on attempt {verify_attempt})"
                                    send_slack_message(success_msg)
                                    code_verified = True
                                    break
                                logger.warning(f"⚠️ Verification attempt {verify_attempt} failed for '{label}'. Waiting before retry...")
                            
                            if code_verified:
                                break
                            elif verify_attempt == LOCK_CODE_VERIFY_MAX_ATTEMPTS:
                                logger.error(f"❌ Failed to verify {Device.LOCK.value} code after {LOCK_CODE_VERIFY_MAX_ATTEMPTS} attempts for {lock_name}: {label}")
                                if attempt == LOCK_CODE_ADD_MAX_ATTEMPTS:
                                    error_msg = f"Failed to add and verify {Device.LOCK.value} code after {LOCK_CODE_ADD_MAX_ATTEMPTS} attempts for {lock_name}: {label}"
                                    slack_msg = f"🔐 Failed to add and verify {Device.LOCK.value} code after {LOCK_CODE_ADD_MAX_ATTEMPTS} attempts for {lock_name}: {label}"
                                    logger.error(error_msg)
                                    errors.append(error_msg)
                                    send_slack_message(slack_msg)
                                continue  # Try adding the code again if attempts remain
                        
                        else:
                            error_msg = f"Failed to add {Device.LOCK.value} code for {lock_name}: {label} (attempt {attempt})"
                            logger.error(error_msg)
                            if attempt < LOCK_CODE_ADD_MAX_ATTEMPTS:
                                logger.info(f"Waiting {WYZE_API_DELAY_SECONDS} seconds before retry...")
                                time.sleep(WYZE_API_DELAY_SECONDS)
                                continue
                            
                            slack_msg = f"🔐 Failed to add {Device.LOCK.value} code for {lock_name}: {label} (attempt {attempt})"
                            errors.append(error_msg)
                            send_slack_message(slack_msg)
                            break
                
                else:
                    # Handle timezone conversion for date comparison
                    begin_utc = code.permission.begin.replace(tzinfo=pytz.utc)
                    end_utc = code.permission.end.replace(tzinfo=pytz.utc)
                    checkin_utc = checkin_time.astimezone(pytz.utc)
                    checkout_utc = checkout_time.astimezone(pytz.utc)

                    if LOCAL_DEVELOPMENT:
                        begin_utc = timezone.localize(code.permission.begin)
                        end_utc = timezone.localize(code.permission.end)
                        checkin_utc = checkin_time
                        checkout_utc = checkout_time

                    # Update code if dates have changed
                    if begin_utc != checkin_utc or end_utc != checkout_utc:
                        logger.info(f"UPDATE: {property_name}; label: {label}")
                        if update_lock_code(client, lock_mac, code.id, phone_last4, label, permission):
                            updates.append(f"{Device.LOCK.value} - {lock_name}: {label}")
                        else:
                            errors.append(f"Updating {Device.LOCK.value} Code for {lock_name}: {label}")

    except Exception as e:
        error_msg = f"Unexpected Error in Wyze {Device.LOCK.value} function for {property_name}: {str(e)}"
        slack_msg = f"❌ Unexpected Error in Wyze {Device.LOCK.value} function for `{property_name}`: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        send_slack_message(slack_msg)

    return deletions, updates, additions, errors
