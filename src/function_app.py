import logging
import os
import json
import time
from datetime import datetime
from devices import Devices
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Force logging to start immediately
logging.basicConfig(level=logging.INFO)
logging.info("=== function_app.py starting to load ===")

# Configure Application Insights if available
try:
    from applicationinsights import TelemetryClient
    
    # Get Application Insights connection string from environment
    app_insights_connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    app_insights_key = os.environ.get('APPINSIGHTS_INSTRUMENTATIONKEY')
    
    if app_insights_key:
        # Initialize telemetry client for custom metrics
        telemetry_client = TelemetryClient(app_insights_key)
        logging.info("Application Insights configured successfully")
    else:
        telemetry_client = None
        logging.info("Application Insights not configured - instrumentation key not found")
        
except ImportError:
    telemetry_client = None
    logging.warning("Application Insights packages not available")

app = func.FunctionApp()

# Log that the FunctionApp was created
logging.info("=== FunctionApp instance created ===")

# Initialize execution tracking dict
last_execution = {}

NON_PROD = os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

# Log startup information
logging.info(f"Function App starting up - NON_PROD: {NON_PROD}, LOCAL_DEVELOPMENT: {LOCAL_DEVELOPMENT}")
logging.info(f"Python version: {os.sys.version}")
try:
    logging.info(f"Azure Functions version: {func.__version__}")
except AttributeError:
    logging.info("Azure Functions version: unknown")

# Key Vault setup - only if needed for sync operations
VAULT_URL = os.environ.get("VAULT_URL", "")

# Simplified secrets handling for testing
if LOCAL_DEVELOPMENT:
    logging.info("Running in LOCAL_DEVELOPMENT mode")
else:
    logging.info("Running in Azure environment")
    if VAULT_URL:
        try:
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=VAULT_URL, credential=credential)
            logging.info("Key Vault client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Key Vault client: {str(e)}")
            client = None

# Conditionally register timer function only in production
if not NON_PROD:
    @app.function_name(name="TimerTriggerSync")
    @app.timer_trigger(schedule="0 */5 * * * *",
                  arg_name="mytimer",
                  run_on_startup=False)
    def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
        """Main timer function that processes reservations every 5 minutes - PRODUCTION ONLY"""
        logging.info("=== TimerTriggerSync function is being registered ===")

        # Log timer trigger details for debugging
        logging.info(f'=== Timer trigger fired ===')
        if mytimer.past_due:
            logging.info('The timer is past due!')
        logging.info(f'Schedule info: {mytimer.schedule_status}')
        logging.info(f'Past due: {mytimer.past_due}')
        logging.info(f'Environment: NON_PROD={NON_PROD}, LOCAL_DEVELOPMENT={LOCAL_DEVELOPMENT}')
        
        # Track function execution start
        if telemetry_client:
            telemetry_client.track_event('TimerTriggerSync_Started')
        
        # Log environment info for debugging
        env_type = "Production" if not NON_PROD else "Non-Production"
        logging.info(f'Timer execution started - {env_type} environment')
        
        logging.info('Python timer trigger function executed at %s', mytimer)

        try:
            execution_start = time.time()
            logging.info('Starting process_reservations...')
            
            from sync import process_reservations
            process_reservations([Devices.LOCKS, Devices.LIGHTS, Devices.THERMOSTATS])
            
            execution_time = time.time() - execution_start
            logging.info(f'process_reservations completed successfully in {execution_time:.2f} seconds')
            
            if telemetry_client:
                telemetry_client.track_metric('TimerSync_ExecutionTime', execution_time)
                telemetry_client.track_event('TimerTriggerSync_Completed', {'execution_time_seconds': execution_time})
                
        except Exception as e:
            logging.error(f"Error executing function: {str(e)}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
            
            if telemetry_client:
                telemetry_client.track_exception()
                telemetry_client.track_event('TimerTriggerSync_Failed', {'error': str(e)})
        
        logging.info('=== Timer trigger completed ===')
    
    logging.info("TimerTriggerSync function registered for PRODUCTION environment")
else:
    logging.info("TimerTriggerSync function DISABLED for NON_PROD environment")

@app.function_name(name="HealthCheck")
@app.route(route="health", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint to verify function app is working"""
    logging.info("=== HealthCheck function is being registered ===")
    logging.info('Health check requested')
    
    # Build list of available functions based on environment
    available_functions = [
        "HealthCheck", 
        "Sync_Locks", 
        "Sync_Lights", 
        "Sync_Thermostats", 
        "Property_List"
    ]
    
    # Add timer function only in production
    if not NON_PROD:
        available_functions.append("TimerTriggerSync")
    
    health_info = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": {
            "NON_PROD": NON_PROD,
            "LOCAL_DEVELOPMENT": LOCAL_DEVELOPMENT,
            "python_version": os.sys.version.split()[0],
        },
        "functions": available_functions,
        "vault_configured": bool(VAULT_URL),
        "endpoints": {
            "health": "GET /api/health",
            "sync_locks": "POST /api/trigger_sync_locks",
            "sync_lights": "POST /api/trigger_sync_lights", 
            "sync_thermostats": "POST /api/trigger_sync_thermostats",
            "property_list": "GET /api/property_list"
        }
    }
    
    if telemetry_client:
        telemetry_client.track_event('HealthCheck_Requested')
        health_info["application_insights"] = "configured"
    else:
        health_info["application_insights"] = "not_configured"
    
    return func.HttpResponse(
        json.dumps(health_info, indent=2),
        mimetype="application/json",
        status_code=200
    )

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


