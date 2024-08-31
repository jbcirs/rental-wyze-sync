from logger import Logger
import os
import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

VAULT_URL = os.environ["VAULT_URL"]
TIMEZONE = os.environ['TIMEZONE']
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'

logger = Logger()


if LOCAL_DEVELOPMENT:
    WYZE_EMAIL = os.environ.get("WYZE_EMAIL")
    WYZE_PASSWORD = os.environ.get("WYZE_PASSWORD")
    WYZE_KEY_ID = os.environ.get("WYZE_KEY_ID")
    WYZE_API_KEY = os.environ.get("WYZE_API_KEY")
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    WYZE_EMAIL = client.get_secret("WYZE-EMAIL").value
    WYZE_PASSWORD = client.get_secret("WYZE-PASSWORD").value
    WYZE_KEY_ID = client.get_secret("WYZE-KEY-ID").value
    WYZE_API_KEY = client.get_secret("WYZE-API-KEY").value