
# Syncing Rental Wyze Devices

This app will synchronize Wyze devices for rental use. This Azure Function looks one week in advance from your Hospitable calendar and adds, updates, or deletes codes into Wyze locks.

## Setup

This code is set up with Terraform for infrastructure as code, using GitHub build workflows for deployment.

### 1. Fork the Code

Fork the repository to your GitHub account for deployment to Azure.

### 2. Setup Azure for GitHub Deployment

Use App Registrations in Azure. Run these commands from Azure PowerShell in the portal or locally:

**Get Subscription GUID**
```sh
az account show --query id
```

**Setup App Registration**
```sh
az ad sp create-for-rbac --name terraform-github-rental-sync --role Contributor --scopes /subscriptions/00000000-0000-0000-0000-000000000000
```

The JSON object you receive will be needed for the GitHub secrets. In the portal, open the new App Registration, navigate to **Certificates & Secrets**, and set up Federated credentials for the GitHub repo.

### 3. Create an Azure Storage Account

Create an Azure Storage Account to store Terraform state files.

1. Open the new storage account.
2. Add a `tfstate` folder in Blob Storage under Storage Browser.

   Follow these [Microsoft Instructions](https://learn.microsoft.com/en-us/devops/deliver/iac-github-actions) for more details.

3. Update `storage_account_name` in `./terrafromprofivers.tf ` with the storage account name you created.

### 4. Setup Slack Bot

Set up a Slack Bot and give it the appropriate access. Add the correct channels (`#lock` or `lock-np`).

### 5. Create Wyze Developer API

Create a Wyze developer API from the [Wyze Developer Portal](https://developer-api-console.wyze.com/).

### 6. Add GitHub Action Secrets

Add the following GitHub Action Secrets:

```
AAD_OBJECTID_ADMIN
AZURE_AD_CLIENT_ID
AZURE_AD_CLIENT_SECRET
AZURE_AD_TENANT_ID
AZURE_SUBSCRIPTION_ID
HOSPITABLE_EMAIL
HOSPITABLE_PASSWORD
RESOURCE_GROUP
SLACK_TOKEN
WYZE_API_KEY
WYZE_EMAIL
WYZE_KEY_ID
WYZE_PASSWORD
```

- `AZURE_AD_CLIENT_ID` is the app_id from the JSON object in step 2.
- `AZURE_AD_CLIENT_SECRET` is the password from the JSON object in step 2.
- `AZURE_AD_TENANT_ID` is from the JSON object in step 2.
- `AZURE_SUBSCRIPTION_ID` is your Azure subscription id you used in step 2.
- `AAD_OBJECTID_ADMIN` is your Object ID to access Key Vault secrets in the portal. You can get this from Microsoft by selecting the user.
- `RESOURCE_GROUP` can be named anything as this is the main name of your app, e.g., `lock-sync`.
- `SLACK_TOKEN` wil start with `xoxb-`

### 7. Deploy the Azure Functions

Run the `Deploy Prod` GitHub Action to deploy the Azure Functions and start running them.

### 8. Cleanup Deployment

Run `Cleanup Prod` to remove the deployment.

### 9. Ensure Property Name Consistency

Make sure all your properties in Hospitable and the Wyze Locks are named the same. The Wyze app locks need to end with `- FD`.

Example:
- Hospitable Name: `Boston - Main St`
- Wyze Lock Name: `Boston - Main St - FD`

## Azure Functions

You will get two Azure Functions:

1. **Hourly Cron Job:** This function runs hourly and will message you only if there are actions taken. To always get a message, set `ALWAYS_SEND_SLACK_SUMMARY` to true.
2. **HTTP Post Trigger:** This function can delete all guest codes. Use this URL:
   ```
   https://{{app-name}}-functions.azurewebsites.net/api/trigger_sync?delete_all_guest_codes=false
   ```
   All guest codes will be displayed with the word Guest, first name, and start date of reservation, e.g., `Guest Robert 20240412`.



### First Time Local

For first time run of any scripts use

```
chmod +x ./scripts/<filename>.sh
```

### Setup Enviorment Local

```
python3 -m venv .venv
. .venv/bin/activate
```