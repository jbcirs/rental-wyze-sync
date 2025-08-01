import logging
import os
import json
import time
from datetime import datetime
from devices import Devices
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

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

@app.function_name(name="TimerTriggerSync")
@app.timer_trigger(schedule="0 */10 * * * *", arg_name="mytimer", run_on_startup=False, use_monitor=True)
def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
    """Main timer function that processes reservations every 10 minutes"""
    
    # Log timer trigger details for debugging
    logging.info(f'=== Timer trigger fired ===')
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

@app.function_name(name="HealthCheck")
@app.route(route="health", methods=[func.HttpMethod.GET], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint to verify function app is working"""
    logging.info('Health check requested')
    
    health_info = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": {
            "NON_PROD": NON_PROD,
            "LOCAL_DEVELOPMENT": LOCAL_DEVELOPMENT,
            "python_version": os.sys.version.split()[0],
        },
        "functions": ["TimerTriggerSync", "HealthCheck"],
        "vault_configured": bool(VAULT_URL)
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

