import azure.functions as func
import json
import logging
import os
from datetime import datetime
import pytz
from battery_monitor import get_all_lock_battery_levels, send_property_battery_report
from hospitable import get_hospitable_properties
from logger import Logger

logger = Logger()

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to monitor battery levels for locks across all properties.
    Generates comprehensive battery reports with alerts and sends to Slack.
    """
    logger.info('Battery monitoring function triggered.')
    
    try:
        # Get timezone
        timezone_str = os.environ.get('TIMEZONE', 'UTC')
        timezone = pytz.timezone(timezone_str)
        current_time = datetime.now(timezone)
        
        # Get all properties from Hospitable
        properties = get_hospitable_properties()
        if not properties:
            logger.error("No properties found from Hospitable")
            return func.HttpResponse(
                json.dumps({"error": "No properties found"}),
                status_code=500,
                mimetype="application/json"
            )
        
        total_errors = []
        all_battery_data = []
        property_results = {}
        
        # First pass: Collect all battery data
        for property_data in properties:
            try:
                property_name = property_data.get('propertyName', 'Unknown Property')
                
                # Check if property has lock configurations
                if 'locks' not in property_data or not property_data['locks']:
                    logger.debug(f"No locks configured for property {property_name}")
                    continue
                
                # Parse lock configurations if it's a JSON string
                lock_configs = property_data['locks']
                if isinstance(lock_configs, str):
                    try:
                        lock_configs = json.loads(lock_configs)
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid lock configuration JSON for property {property_name}: {str(e)}"
                        logger.error(error_msg)
                        total_errors.append(error_msg)
                        continue
                
                # Get battery levels for this property
                battery_data, errors = get_all_lock_battery_levels(lock_configs, property_name)
                
                # Collect data and errors
                all_battery_data.extend(battery_data)
                total_errors.extend(errors)
                
                # Track results for this property
                low_battery_count = len([lock for lock in battery_data if lock['is_low_battery']])
                warning_count = len([lock for lock in battery_data if lock['is_warning']])
                property_results[property_name] = {
                    "total_locks": len(battery_data),
                    "low_battery_count": low_battery_count,
                    "warning_count": warning_count,
                    "errors": len(errors),
                    "locks": battery_data,
                    "error_details": errors
                }
                
                logger.info(f"Battery data collected for {property_name}: {len(battery_data)} locks, {low_battery_count} low battery, {warning_count} warnings, {len(errors)} errors")
                
            except Exception as e:
                error_msg = f"Error processing property {property_data.get('propertyName', 'Unknown')}: {str(e)}"
                logger.error(error_msg)
                total_errors.append(error_msg)
                continue
        
        # Second pass: Send battery reports to Slack for each property
        reports_sent = 0
        for property_name, property_result in property_results.items():
            try:
                if property_result['total_locks'] > 0:
                    report_sent = send_property_battery_report(all_battery_data, property_name)
                    if report_sent:
                        reports_sent += 1
                        logger.info(f"Battery report sent for {property_name}")
                    else:
                        logger.error(f"Failed to send battery report for {property_name}")
            except Exception as e:
                error_msg = f"Error sending battery report for {property_name}: {str(e)}"
                logger.error(error_msg)
                total_errors.append(error_msg)
        
        # Calculate totals for summary
        total_locks = len(all_battery_data)
        total_low_battery = len([lock for lock in all_battery_data if lock['is_low_battery']])
        total_warnings = len([lock for lock in all_battery_data if lock['is_warning']])
        
        # Create summary response
        response_data = {
            "timestamp": current_time.isoformat(),
            "summary": {
                "total_properties_processed": len(property_results),
                "total_locks_monitored": total_locks,
                "total_low_battery_alerts": total_low_battery,
                "total_warnings": total_warnings,
                "total_reports_sent": reports_sent,
                "total_errors": len(total_errors)
            },
            "property_results": property_results,
            "all_battery_data": all_battery_data
        }
        
        # Log summary
        logger.info(f"Battery monitoring completed. Processed {len(property_results)} properties, monitored {total_locks} locks, found {total_low_battery} low battery alerts, {total_warnings} warnings, sent {reports_sent} reports, encountered {len(total_errors)} errors")
        
        # Return success response
        status_code = 200 if len(total_errors) == 0 else 207  # 207 = Multi-Status (partial success)
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=status_code,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_msg = f"Unexpected error in battery monitoring function: {str(e)}"
        logger.error(error_msg)
        
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=500,
            mimetype="application/json"
        )
