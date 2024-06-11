import logging
import os
import json
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


app = func.FunctionApp()

NON_PROD =  os.environ.get('NON_PROD', 'false').lower() == 'true'
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
VAULT_URL = os.environ["VAULT_URL"]

if LOCAL_DEVELOPMENT:
    SLACK_VERIFICATION_TOKEN = os.environ['SLACK_VERIFICATION_TOKEN']
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    SLACK_VERIFICATION_TOKEN = client.get_secret("SLACK-VERIFICATION-TOKEN").value

if not NON_PROD:
    @app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=True, use_monitor=True)
    def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
        logging.info('Python timer trigger function executed at %s', mytimer)

        try:
            from sync import process_reservations
            process_reservations()
            logging.info('Run process_reservations()')
        except Exception as e:
            logging.error(f"Error executing function: {str(e)}")

@app.function_name(name="Sync")
@app.route(route="trigger_sync", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.FUNCTION)
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
        process_reservations(delete_all_guest_codes)
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)
    
@app.function_name(name="Slack_Command_Lock")
@app.route(route="slack_command_lock", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
def slack_command_lock(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request Slack Commnd Lock.')

    property_names = [
        "Property1 - Front Door",
        "Property2 - Front Door",
        "Property3 - Front Door"
    ]

    # Parse the request body
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid request", status_code=400)

    # Verify the Slack token
    slack_token = req_body.get('token')
    expected_token = os.getenv('SLACK_VERIFICATION_TOKEN')
    if slack_token != expected_token:
        return func.HttpResponse("Unauthorized request", status_code=401)
    
    # Get the text command from the request
    command_text = req_body.get('text', '').strip()

    if command_text == 'help':
        response_text = (
            "Available commands:\n"
            "• help: Show this help message\n"
            "• list: List all property names"
        )
    elif command_text == 'list':
        response_text = "Property names:\n" + "\n".join(property_names)
    else:
        response_text = (
            "Unknown command. Available commands:\n"
            "• help: Show this help message\n"
            "• list: List all property names"
        )

    return func.HttpResponse(
        json.dumps({
            "response_type": "in_channel",  # public to the channel
            "text": response_text
        }),
        mimetype="application/json"
    )
    
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
    


# @app.function_name(name="DeleteGuestCodesFunction")
# @app.route(route="deletecodes", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
# def delete_guest_codes(req: func.HttpRequest) -> func.HttpResponse:
#     logging.info('Python HTTP trigger function processed a request.')

#     try:
#         req_body = req.get_json()
#     except ValueError:
#         return func.HttpResponse(
#             "Invalid JSON body",
#             status_code=400
#         )

#     delete_all_guest_codes = req_body.get('delete_all_guest_codes')

#     if delete_all_guest_codes is not None:
#         if delete_all_guest_codes:
#             logging.info("Deleting all guest codes.")
#             # Implement the deletion logic here
#         else:
#             logging.info("Not deleting guest codes.")

#         return func.HttpResponse(
#             json.dumps({"message": "Request processed successfully"}),
#             status_code=200,
#             mimetype="application/json"
#         )
#     else:
#         return func.HttpResponse(
#             json.dumps({"error": "Missing 'delete_all_guest_codes' field"}),
#             status_code=400,
#             mimetype="application/json"
#         )