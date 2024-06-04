import logging
import azure.functions as func
from ..lock_sync import process_reservations

def main(mytimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed at %s', mytimer)
    
    try:
        process_reservations()
    except Exception as e:
        logging.error(f"Error executing function: {str(e)}")
