"""
Utility functions for datetime handling, data validation, and filtering.
"""
import time
import json
from logger import Logger
from datetime import datetime, timedelta
import pytz
from pytz import AmbiguousTimeError, NonExistentTimeError

logger = Logger()

def format_datetime(date_str, offset_hours=0, timezone_str='UTC'):
    """
    Convert a date string to a timezone-aware datetime with an optional offset.
    
    Args:
        date_str: Date string in format "%Y-%m-%dT%H:%M:%S"
        offset_hours: Hours to add/subtract from the parsed date
        timezone_str: Timezone identifier (e.g., 'America/New_York')
        
    Returns:
        Timezone-aware datetime object with applied offset
    """
    date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    timezone = pytz.timezone(timezone_str)
    date = timezone.localize(date)
    date += timedelta(hours=offset_hours)
    return date
    
def subtract_string_lists(list1, list2):
    """
    Return items in list1 that are not in list2.
    
    Args:
        list1: First list of strings
        list2: Second list of strings to subtract
        
    Returns:
        List of strings that are in list1 but not list2
    """
    set1 = set(list1)
    set2 = set(list2)
    result = list(set1 - set2)
    return result

def parse_local_time(time_str, timezone, reference_time=None):
    """
    Parse a time string (HH:MM) into a timezone-aware datetime for today.
    
    Args:
        time_str: Time string in format "HH:MM"
        timezone: Timezone identifier or tzinfo object
        reference_time: Optional timezone-aware datetime to use as reference for the date
        
    Returns:
        Timezone-aware datetime object for today with the specified time
    """
    local_timezone = pytz.timezone(timezone) if isinstance(timezone, str) else timezone
    time_parts = time_str.split(':')
    
    # Use reference_time if provided, otherwise use current time in the target timezone
    if reference_time is not None and hasattr(reference_time, 'astimezone'):
        # Convert reference time to the target timezone to get the correct date
        local_ref = reference_time.astimezone(local_timezone)
        naive_datetime = datetime(local_ref.year, local_ref.month, local_ref.day, int(time_parts[0]), int(time_parts[1]))
        
        try:
            # Use localize with is_dst=None to raise an error if the time is ambiguous (DST transition)
            return local_timezone.localize(naive_datetime, is_dst=None)
        except pytz.AmbiguousTimeError:
            # During DST transition, choose the earlier occurrence (before "fall back")
            logger.warning(f"Ambiguous time {time_str} due to DST transition, using earlier occurrence")
            return local_timezone.localize(naive_datetime, is_dst=True)
        except pytz.NonExistentTimeError:
            # During DST transition, time doesn't exist (during "spring forward")
            logger.warning(f"Non-existent time {time_str} due to DST transition, using later occurrence")
            return local_timezone.localize(naive_datetime, is_dst=False)
    else:
        # Fallback to current system time
        now = datetime.now()
        naive_datetime = datetime(now.year, now.month, now.day, int(time_parts[0]), int(time_parts[1]))
        
        try:
            return local_timezone.localize(naive_datetime, is_dst=None)
        except pytz.AmbiguousTimeError:
            logger.warning(f"Ambiguous time {time_str} due to DST transition, using earlier occurrence")
            return local_timezone.localize(naive_datetime, is_dst=True)
        except pytz.NonExistentTimeError:
            logger.warning(f"Non-existent time {time_str} due to DST transition, using later occurrence")
            return local_timezone.localize(naive_datetime, is_dst=False)


def validate_json(json_str):
    """
    Validate and parse a JSON string, raising detailed errors if invalid.
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        Parsed JSON object
        
    Raises:
        ValueError: If JSON is invalid with details about the error
    """
    try:
        json_obj = json.loads(json_str)
        return json_obj
    except json.JSONDecodeError as e:
        error = f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}"
        logger.error(error)
        raise ValueError(error)
    except Exception as e:
        error = f"An error occurred: {e}"
        logger.error(error)
        raise ValueError(error)
    
def filter_by_key(device, sub_key, key_value):
    """
    Filter a device configuration by a specific key value in a sub-dictionary.
    
    Args:
        device: Device configuration dictionary
        sub_key: Key containing list of items to filter
        key_value: Value to filter by in the "when" field of items
        
    Returns:
        New device dictionary with filtered items, or None if no matches
    """
    filtered_data = None
    filtered_items = [
        item for item in device.get(sub_key, [])
        if item.get("when") == key_value
    ]

    if filtered_items:
        new_device = device.copy()
        new_device[sub_key] = filtered_items
        filtered_data = new_device
    
    return filtered_data

def is_valid_hour(item, current_time):
    """
    Check if the current hour is in the list of rest hours for a device.
    
    Args:
        item: Device configuration with optional "rest_times" list
        current_time: Current datetime to check
        
    Returns:
        True if current hour is a designated rest hour, False otherwise
    """
    current_hour = current_time.hour
    logger.info(f"current_hour: {current_hour}")
    
    # Extract hours from rest_times strings (format "HH:MM")
    rest_hours = [datetime.strptime(time, "%H:%M").hour for time in item.get("rest_times", [])]
    logger.info(f"rest_hours: {rest_hours}")
    
    return current_hour in rest_hours
