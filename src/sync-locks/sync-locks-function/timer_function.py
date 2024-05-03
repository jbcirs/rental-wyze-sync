# timer_function.py
import datetime
import os
import logging
from wyze_sdk import Client

def run_timer_function():
    logging.info(f"Executing at {datetime.datetime.now().isoformat()}")
    try:
        client = Client(token=os.environ['WYZE_ACCESS_TOKEN'])
        locks = client.locks.list()
        for lock in locks:
            keys = client.locks.get_keys(device_mac=lock.mac)
            logging.info(f'Lock MAC: {lock.mac}, Guest Access Keys: {keys}')
    except Exception as e:
        logging.info(f"Failed to retrieve data: {str(e)}")

if __name__ == "__main__":
    run_timer_function()
