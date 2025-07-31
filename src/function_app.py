import logging
import os
import json
import time
from datetime import datetime
from devices import Devices
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

# Configure Application Insights if available
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from applicationinsights import TelemetryClient
    
    # Get Application Insights connection string from environment
    app_insights_connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    app_insights_key = os.environ.get('APPINSIGHTS_INSTRUMENTATIONKEY')
    
    if app_insights_connection_string:
        # Configure logging to send to Application Insights
        logger = logging.getLogger(__name__)
        handler = AzureLogHandler(connection_string=app_insights_connection_string)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Initialize telemetry client for custom metrics
        if app_insights_key:
            telemetry_client = TelemetryClient(app_insights_key)
        else:
            telemetry_client = None
            
        logging.info("Application Insights configured successfully")
    else:
        telemetry_client = None
        logging.info("Application Insights not configured - connection string not found")
        
except ImportError:
    telemetry_client = None
    logging.warning("Application Insights packages not available")

app = func.FunctionApp()

# Initialize execution tracking dict
last_execution = {}

NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
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

@app.schedule(schedule="0 */30 * * * *", arg_name="mytimer", run_on_startup=False, use_monitor=True)
def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
    global last_execution
    
    # Only run scheduled timer in production environments
    if NON_PROD:
        logging.info('Skipping timer execution - scheduled timer only runs in production environments')
        if telemetry_client:
            telemetry_client.track_event('TimerTriggerSync_Skipped', {'reason': 'non_production_environment'})
        return
    
    # Track function execution start
    if telemetry_client:
        telemetry_client.track_event('TimerTriggerSync_Started')
    
    # Log environment info for debugging
    logging.info(f'Timer execution started - Production environment (NON_PROD: {NON_PROD})')
    
    # Implement a simple lock mechanism to prevent concurrent executions
    current_time = time.time()
    function_name = "timer_trigger_sync"
    
    # If the function was called in the last 25 minutes, skip execution (adjusted for 30-min schedule)
    if function_name in last_execution and current_time - last_execution[function_name] < 1500:  # 25 minutes
        time_since_last = current_time - last_execution[function_name]
        logging.info(f'Skipping execution - previous run too recent: {datetime.fromtimestamp(last_execution[function_name])} ({time_since_last/60:.1f} minutes ago)')
        if telemetry_client:
            telemetry_client.track_event('TimerTriggerSync_Skipped', {
                'reason': 'recent_execution',
                'time_since_last_minutes': time_since_last / 60
            })
        return
        
    # Set the last execution time
    last_execution[function_name] = current_time
    
    logging.info('Python timer trigger function executed at %s', mytimer)

    try:
        execution_start = time.time()
        from sync import process_reservations
        process_reservations([Devices.LOCKS,Devices.LIGHTS,Devices.THERMOSTATS])
        execution_time = time.time() - execution_start
        
        logging.info('Run process_reservations()')
        
        if telemetry_client:
            telemetry_client.track_metric('TimerSync_ExecutionTime', execution_time)
            telemetry_client.track_event('TimerTriggerSync_Completed', {'execution_time_seconds': execution_time})
            
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        if telemetry_client:
            telemetry_client.track_exception()
            telemetry_client.track_event('TimerTriggerSync_Failed', {'error': str(e)})

@app.function_name(name="Sync_Locks")
@app.route(route="trigger_sync_locks", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync_locks(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')
    
    if telemetry_client:
        telemetry_client.track_event('HttpTriggerSync_Locks_Started')

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
        execution_start = time.time()
        from sync import process_reservations
        process_reservations([Devices.LOCKS], delete_all_guest_codes)
        execution_time = time.time() - execution_start
        
        if telemetry_client:
            telemetry_client.track_metric('HttpSync_Locks_ExecutionTime', execution_time)
            telemetry_client.track_event('HttpTriggerSync_Locks_Completed', 
                                       {'execution_time_seconds': execution_time, 
                                        'delete_all_guest_codes': delete_all_guest_codes})
        
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        if telemetry_client:
            telemetry_client.track_exception()
            telemetry_client.track_event('HttpTriggerSync_Locks_Failed', {'error': str(e)})
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Sync_Lights")
@app.route(route="trigger_sync_lights", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync_lights(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')
    
    if telemetry_client:
        telemetry_client.track_event('HttpTriggerSync_Lights_Started')

    try:
        execution_start = time.time()
        from sync import process_reservations
        process_reservations([Devices.LIGHTS])
        execution_time = time.time() - execution_start
        
        if telemetry_client:
            telemetry_client.track_metric('HttpSync_Lights_ExecutionTime', execution_time)
            telemetry_client.track_event('HttpTriggerSync_Lights_Completed', {'execution_time_seconds': execution_time})
        
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        if telemetry_client:
            telemetry_client.track_exception()
            telemetry_client.track_event('HttpTriggerSync_Lights_Failed', {'error': str(e)})
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Sync_Thermostats")
@app.route(route="trigger_sync_thermostats", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
def http_trigger_sync_thermostats(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')
    
    if telemetry_client:
        telemetry_client.track_event('HttpTriggerSync_Thermostats_Started')

    try:
        execution_start = time.time()
        from sync import process_reservations
        process_reservations([Devices.THERMOSTATS])
        execution_time = time.time() - execution_start
        
        if telemetry_client:
            telemetry_client.track_metric('HttpSync_Thermostats_ExecutionTime', execution_time)
            telemetry_client.track_event('HttpTriggerSync_Thermostats_Completed', {'execution_time_seconds': execution_time})
        
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        if telemetry_client:
            telemetry_client.track_exception()
            telemetry_client.track_event('HttpTriggerSync_Thermostats_Failed', {'error': str(e)})
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

