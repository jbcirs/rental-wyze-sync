import datetime
import logging
from .timer_function import run_timer_function
import azure.functions as func

def main(mytimer: func.TimerRequest) -> None:
    utc_now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
    logging.info('Timer trigger function executed at %s', utc_now)

    # Check if the timer trigger is finding itself past due
    if mytimer.past_due:
        logging.info("The timer is past due!")

    try:
        run_timer_function()

    except Exception as e:
        logging.error(f"Failed to retrieve data: {str(e)}")
