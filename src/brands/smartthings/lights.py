import logging
from devices import Device
from slack_notify import send_slack_message
from brands.smartthings.smartthings import *


def get_switch_value(data):
    try:
        return data["components"]["main"]["switch"]["switch"]["value"]
    except KeyError:
        return None

def switch_light(light_id,state,light_name,property_name,updates,errors):
    light_status = 'on' if state else 'off'
    light = get_device_status(light_id)
    current_status = get_switch_value(light)

    if current_status is None or current_status != light_status:
        if switch(light_id, state):
            logging.info(f"Switched {Device.LIGHT.value} {light_status}: {light_name} at {property_name}")
            updates.append(f"{Device.LIGHT.value} {light_status} - {property_name} - {light_name}")
        else:
            errors.append(f"Switching {Device.LIGHT.value} for {light_name} at {property_name}")
    else:
        logging.info(f"Switch {Device.LIGHT.value} already {light_status}: {light_name} at {property_name}, no change required")
    
    return updates, errors

def sync(light, property_name, location, light_state=False):
    logging.info(f'Processing SmartThings {Device.LIGHT.value} reservations.')
    updates = []
    errors = []

    try:        
        light_name = light['name']
        location_id = find_location_by_name(location)

        if location_id is None:
            send_slack_message(f"Unable to fetch location ID for {light_name} at {property_name}.")
            return

        light_id = get_device_id_by_label(location_id,light_name)

        if light_id is None:
            send_slack_message(f"Unable to fetch {Device.LIGHT.value} for {light_name} at {property_name}.")
            return
        
        switch_light(light_id, light_state, light_name, property_name, updates, errors)


    except Exception as e:
        error = f"Error in SmatThings {Device.LIGHT.value} function: {str(e)}"
        logging.error(error)
        errors.append(error)
        send_slack_message(f"Error in SmatThings {Device.LIGHT.value} function: {str(e)}")

    return updates, errors