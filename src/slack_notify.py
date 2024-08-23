from logger import Logger
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

SLACK_CHANNEL = os.environ['SLACK_CHANNEL']
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

def send_slack_message(message):
    try:
        slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
    except SlackApiError as e:
        logger.error(f"Slack API Error: {str(e)}")

def send_summary_slack_message(property_name, deletions, updates, additions, errors):
    message = f"Property: {property_name}\n"
    if not deletions and not updates and not additions and not errors:
        message += "_No Changes_"
    else:
        message += "Deleted:\n" + ("\n".join([f"`{item}`" for item in deletions]) if deletions else "_-None-_") + "\n"
        message += "Updated:\n" + ("\n".join([f"`{item}`" for item in updates]) if updates else "_-None-_") + "\n"
        message += "Added:\n" + ("\n".join([f"`{item}`" for item in additions]) if additions else "_-None-_") + "\n"
        message += "Errors:\n" + ("\n".join([f"`{item}`" for item in errors]) if errors else "_-None-_") + "\n"
    send_slack_message(message)
