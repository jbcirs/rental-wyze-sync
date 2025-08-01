from logger import Logger
import os
from typing import List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

SLACK_CHANNEL = os.environ['SLACK_CHANNEL']
SLACK_ERRORS_CHANNEL = os.environ['SLACK_ERRORS_CHANNEL']
VAULT_URL = os.environ["VAULT_URL"]
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

logger = Logger()

if LOCAL_DEVELOPMENT:
    SLACK_TOKEN = os.environ.get("SLACK_TOKEN")
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    SLACK_TOKEN = client.get_secret("SLACK-TOKEN").value

# Initialize Slack client
slack_client = WebClient(token=SLACK_TOKEN)

def send_slack_message(message, channel=None):
    """
    Send a message to a Slack channel.
    
    Args:
        message: Message text to send
        channel: Channel name (uses default if None)
    
    Returns:
        Boolean indicating success or failure
    """
    if channel:
        slack_channel = channel
    else:
        slack_channel = SLACK_CHANNEL
    
    logger.info(f"Sending Slack message to #{slack_channel}")
    
    try:
        response = slack_client.chat_postMessage(channel=slack_channel, text=message)
        if response['ok']:
            logger.info(f"Successfully sent message to #{slack_channel}")
            return True
        else:
            logger.error(f"Failed to send message: {response['error']}")
            return False
    except SlackApiError as e:
        logger.error(f"Slack API Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Slack message: {str(e)}")
        return False

def send_summary_slack_message(property_name, deletions, updates, additions, errors):
    """
    Send a formatted summary message about property changes to Slack.
    
    Args:
        property_name: Name of the rental property
        deletions: List of deleted items
        updates: List of updated items
        additions: List of added items
        errors: List of errors
    """
    logger.info(f"Preparing summary message for property: {property_name}")
    
    message = f"Property: {property_name}\n"
    if not deletions and not updates and not additions and not errors:
        message += "_No Changes_"
    else:
        message += "Deleted:\n" + ("\n".join([f"`{item}`" for item in deletions]) if deletions else "_-None-_") + "\n"
        message += "Updated:\n" + ("\n".join([f"`{item}`" for item in updates]) if updates else "_-None-_") + "\n"
        message += "Added:\n" + ("\n".join([f"`{item}`" for item in additions]) if additions else "_-None-_") + "\n"
        message += "Errors:\n" + ("\n".join([f"`{item}`" for item in errors]) if errors else "_-None-_") + "\n"
    
    result = send_slack_message(message)
    if not result:
        logger.warning(f"Failed to send summary message for {property_name}")

def send_config_error_message(property_name: str, errors: List[str]) -> bool:
    """
    Send a configuration validation error message to the dedicated errors channel.
    
    Args:
        property_name: Name of the rental property with configuration errors
        errors: List of validation error messages
        
    Returns:
        Boolean indicating success or failure
    """
    logger.info(f"Preparing configuration error message for property: {property_name}")
    
    # Format the error message
    message = f"🚨 **Configuration Validation Failed**\n"
    message += f"**Property:** {property_name}\n"
    message += f"**Error Count:** {len(errors)}\n\n"
    message += "**Validation Errors:**\n"
    
    for i, error in enumerate(errors, 1):
        message += f"{i}. `{error}`\n"
    
    message += f"\n❗ Property `{property_name}` has been **skipped** from processing until configuration is fixed."
    
    # Send to the dedicated errors channel
    result = send_slack_message(message, channel=SLACK_ERRORS_CHANNEL)
    if result:
        logger.info(f"Configuration error notification sent for {property_name}")
    else:
        logger.error(f"Failed to send configuration error notification for {property_name}")
    
    return result
