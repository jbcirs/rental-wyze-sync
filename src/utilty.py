import time
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
