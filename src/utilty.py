import time
from datetime import datetime, timedelta
import pytz

def format_datetime(date_str, offset_hours=0, timezone_str='UTC'):
    date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    timezone = pytz.timezone(timezone_str)
    date = timezone.localize(date)
    date += timedelta(hours=offset_hours)
    return date
