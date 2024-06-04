# timer_function.py
import datetime
import os
import logging
from wyze_sdk import Client

def get_token():
    response = Client().login(
                email=os.environ['WYZE_EMAIL'],
                password=os.environ['WYZE_PASSWORD'],
                key_id=os.environ['WYZE_KEY_ID'],
                api_key=os.environ['WYZE_API_KEY']
            )
    return response['access_token']

client = Client(token=get_token())

def run_timer_function():
    logging.info(f"Executing at {datetime.datetime.now().isoformat()}")
    try:
        locks = client.locks.list()
        for lock in locks:
            keys = client.locks.get_keys(device_mac=lock.mac)
            print(f'Lock MAC: {lock.mac}, Guest Access Keys: {keys}')
    except Exception as e:
        print(f"Failed to retrieve data: {str(e)}")

if __name__ == "__main__":
    run_timer_function()
