import logging
import azure.functions as func
from lock_sync import process_reservations

app = func.FunctionApp()

@app.function_name(name="sync-locks-job")
@app.schedule(schedule="0 * * * * *", arg_name="mytimer", run_on_startup=True, use_monitor=True)
def TimerTriggerFunction(mytimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed at %s', mytimer)

    try:
        process_reservations()
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
