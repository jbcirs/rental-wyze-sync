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
    SEAM_API_KEY = os.environ.get("SEAM_API_KEY")
else:
    # Azure Key Vault client
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)

    # Fetch secrets from Key Vault
    SEAM_API_KEY = client.get_secret("WYZE-API-KEY").value

def get_seam_token():
    return SEAM_API_KEY