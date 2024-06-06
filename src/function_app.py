import logging
import os
import azure.functions as func
from lock_sync import process_reservations

app = func.FunctionApp()

@app.function_name(name="sync-locks-timer")
@app.schedule(schedule="0 * * * * *", arg_name="mytimer", run_on_startup=True, use_monitor=True)
def TimerTriggerFunction(mytimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed at %s', mytimer)

    try:
        process_reservations()
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")

@app.function_name(name="sync-locks-http")
@app.route(route="trigger", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def HttpTriggerFunction(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('HTTP trigger function processed a request.')

    delete_all_guest_codes = req.params.get('DELETE_ALL_GUEST_CODES')
    if not delete_all_guest_codes:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            delete_all_guest_codes = req_body.get('DELETE_ALL_GUEST_CODES')

    if delete_all_guest_codes:
        os.environ['DELETE_ALL_GUEST_CODES'] = delete_all_guest_codes.lower() == 'true'

    try:
        process_reservations()
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)