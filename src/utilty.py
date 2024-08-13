import time
import json
import logging
from datetime import datetime, timedelta
import pytz

def format_datetime(date_str, offset_hours=0, timezone_str='UTC'):
    date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    timezone = pytz.timezone(timezone_str)
    date = timezone.localize(date)
    date += timedelta(hours=offset_hours)
    return date
    
def subtract_string_lists(list1, list2):
    set1 = set(list1)
    set2 = set(list2)
    result = list(set1 - set2)
    return result

def parse_local_time(time_str, timezone):
    local_timezone = pytz.timezone(timezone)
    time_parts = time_str.split(':')
    now = datetime.now()
    return local_timezone.localize(datetime(now.year, now.month, now.day, int(time_parts[0]), int(time_parts[1])))


def validate_json(json_str):
    try:
        json_obj = json.loads(json_str)
        return json_obj
    except json.JSONDecodeError as e:
        error = f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}"
        logging.error(error)
        raise ValueError(error)
    except Exception as e:
        error = f"An error occurred: {e}"
        logging.error(error)
        raise ValueError(error)
    
def filter_by_key(device, sub_key, key_value):
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
