import logging
import os
import json
from devices import Devices
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

app = func.FunctionApp()

NON_PROD =  os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
VAULT_URL = os.environ["VAULT_URL"]

if LOCAL_DEVELOPMENT:
    SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    SLACK_SIGNING_SECRET = client.get_secret("SLACK-SIGNING-SECRET").value
    SLACK_TOKEN = client.get_secret("SLACK-TOKEN").value

if not NON_PROD:
    @app.schedule(schedule="0 */30 * * * *", arg_name="mytimer", run_on_startup=False, use_monitor=True)
    def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
        logging.info('Python timer trigger function executed at %s', mytimer)

        try:
            from sync import process_reservations
            process_reservations([Devices.LOCKS,Devices.LIGHTS,Devices.THERMOSTATS])
            logging.info('Run process_reservations()')
        except Exception as e:
            logging.error(f"Error executing function: {str(e)}")

@app.function_name(name="Sync_Locks")
@app.route(route="trigger_sync_locks", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')

    logging.info(f"req.params: {req.params}")
    delete_all_guest_codes = req.params.get('delete_all_guest_codes', 'false').lower() == 'true'
    logging.info(f"delete_all_guest_codes: {delete_all_guest_codes}")

    if not delete_all_guest_codes:
        try:
            req_body = req.get_json()
            logging.info(f"req_body: {req_body}")
            delete_all_guest_codes = req_body.get('delete_all_guest_codes', 'false').lower() == 'true'
            logging.info(f"delete_all_guest_codes: {delete_all_guest_codes}")
        except ValueError:
            logging.warning('Invalid JSON in request body.')

    try:
        from sync import process_reservations
        process_reservations([Devices.LOCKS], delete_all_guest_codes)
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Sync_Lights")
@app.route(route="trigger_sync_lights", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')

    try:
        from sync import process_reservations
        process_reservations([Devices.LIGHTS])
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Sync_Thermostats")
@app.route(route="trigger_sync_thermostats", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')

    try:
        from sync import process_reservations
        process_reservations([Devices.THERMOSTATS])
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Property_List")
@app.route(route="property_list", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.FUNCTION)
def property_list(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request get_property_list.')

    try:
        from hospitable import authenticate_hospitable, get_properties
        token = authenticate_hospitable()
        if not token:
            logging.info("Unable to authenticate with Hospitable API.")
            return

        properties = get_properties(token)
        if not properties:
            logging.info("Unable to fetch properties from Hospitable API.")
            return
        
        property_names = []
        
        for prop in properties:
            property_names.append(prop['name'])

        return func.HttpResponse(
            json.dumps(property_names),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
