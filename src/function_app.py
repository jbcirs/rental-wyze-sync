import logging
import os
import json
import azure.functions as func


app = func.FunctionApp()

@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=True, use_monitor=True)
def timer_trigger_sync(mytimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed at %s', mytimer)

    try:
        from lock_sync import process_reservations
        process_reservations()
        logging.info('Run process_reservations()')
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")

@app.route(route="trigger_sync", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
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
        from lock_sync import process_reservations
        process_reservations(delete_all_guest_codes)
        return func.HttpResponse("Function executed successfully.", status_code=200)
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
        return func.HttpResponse(f"Error executing function: {str(e)}", status_code=500)

@app.function_name(name="DeleteGuestCodesFunction")
@app.route(route="deletecodes", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def delete_guest_codes(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Invalid JSON body",
            status_code=400
        )

    delete_all_guest_codes = req_body.get('delete_all_guest_codes')

    if delete_all_guest_codes is not None:
        if delete_all_guest_codes:
            logging.info("Deleting all guest codes.")
            # Implement the deletion logic here
        else:
            logging.info("Not deleting guest codes.")

        return func.HttpResponse(
            json.dumps({"message": "Request processed successfully"}),
            status_code=200,
            mimetype="application/json"
        )
    else:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'delete_all_guest_codes' field"}),
            status_code=400,
            mimetype="application/json"
        )