import logging
import os
import json
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
#from fastapi import FastAPI
from slack_comands import bp01


app = func.FunctionApp()

app.register_functions(bp01)

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


# # Define the /lock command handler
# @app.command("/lock")
# def handle_lock_command(ack, body, respond):
#     ack()
#     user_id = body["user_id"]
#     text = body["text"]
#     respond(f"Lock command received from <@{user_id}> with text: {text}")

# # FastAPI app
# fast_app = FastAPI()
# handler = SlackRequestHandler(app)

# @fast_app.post("/slack_command_lock")
# async def lock_command(request: func.HttpRequest) -> func.HttpResponse:
#     return await handler.handle(request)

# @app.function_name(name="Slack_Command_Lock")
# @app.route(route="slack_command_lock", methods=[func.HttpMethod.POST], auth_level=func.AuthLevel.ANONYMOUS)
# async def slack_command_lock(req: func.HttpRequest) -> func.HttpResponse:
#     logging.info('HTTP trigger function processed a request Slack Commnd Lock.')

#     return await handler.handle(req)
    
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