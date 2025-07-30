
# Syncing Rental Wyze Devices

This app will synchronize Wyze devices for rental use. This Azure Function looks one week in advance from your Hospitable calendar and adds, updates, or deletes codes into Wyze or SmartThings locks.

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
SLACK_SIGNING_SECRET
SMARTTHINGS_TOKEN
```

- `AZURE_AD_CLIENT_ID` is the app_id from the JSON object in step 2.
- `AZURE_AD_CLIENT_SECRET` is the password from the JSON object in step 2.
- `AZURE_AD_TENANT_ID` is from the JSON object in step 2.
- `AZURE_SUBSCRIPTION_ID` is your Azure subscription id you used in step 2.
- `AAD_OBJECTID_ADMIN` is your Object ID to access Key Vault secrets in the portal. You can get this from Microsoft by selecting the user.
- `RESOURCE_GROUP` can be named anything as this is the main name of your app, e.g., `lock-sync`.
- `SLACK_TOKEN` will start with `xoxb-`
- `SLACK_SIGNING_SECRET` this will be used to verify that requests come from Slack.
- `SMARTTHINGS_TOKEN` this is the personal access token to your [SmartThings](https://account.smartthings.com/tokens) account.

### 7. Deploy the Azure Functions

Run the `Deploy Prod` GitHub Action to deploy the Azure Functions and start running them.

### 8. Cleanup Deployment

Run `Cleanup Prod` to remove the deployment.


### 9. Adding Properties, Locks, and Thermostats to Azure Storage Table

Each device (lock, light, thermostat) should be added to the Azure Storage Table called `properties`.

- PartitionKey: PMS property name
- RowKey: PMS System
- BrandSettings: List of all settings needed for a brand to run
- Location: GPS coordinates needed for sunset and sunrise times
- Active: `true` or `false` flag
- Locks: List of locks by brand and lock name
- Lights: List of SmartThings lights. You can set to start with sunrise/sunset and/or set a time. Can also be set to only during reservations.
- Thermostats: List of thermostats with full configuration (see below)

#### Thermostat Configuration (with Frequency and Alerts)

You can now control when thermostat changes are made during reservations using the `frequency` field, and configure Slack alerts for temperature setpoints using the `alerts` field.

**Frequency Options:**
- `"first_day"` (default): Only apply changes on the check-in day
- `"daily"`: Apply changes every day during the reservation

**Alert Options:**
- `cool_below`: Alert if cooling setpoint is below this value
- `cool_above`: Alert if cooling setpoint is above this value
- `heat_below`: Alert if heating setpoint is below this value
- `heat_above`: Alert if heating setpoint is above this value
- `enabled`: Boolean to enable/disable alerts (default: true)
- `slack_channel`: Optional custom Slack channel for alerts

**Example Table Object in JSON:**
```json
{
  "PartitionKey": "Boston - Main St",
  "RowKey": "Hospitable",
  "Active": true,
  "BrandSettings": [ { "brand": "smartthings", "location": "Boston Main St" } ],
  "Lights": [
    {"brand": "smartthings", "name": "String Lights", "when": "reservations_only", "minutes_before_sunset": 30, "minutes_after_sunrise": 30, "start_time": null, "stop_time": "23:00"}
  ],
  "Location": {"latitude": "42.3554334", "longitude": "-71.060511"},
  "Locks": [
    { "brand": "wyze", "name": "Boston - Main St - FD" },
    { "brand": "smartthings", "name": "Backdoor" }
  ],
  "Thermostats": [
    {
      "brand": "smartthings",
      "manufacture": "ecobee",
      "name": "Upstairs",
      "temperatures": [
        {
          "when": "reservations_only",
          "mode": "cool",
          "cool_temp": 72,
          "heat_temp": 68,
          "frequency": "first_day",
          "alerts": {
            "cool_below": 70,
            "cool_above": 78,
            "heat_below": 65,
            "heat_above": 75,
            "enabled": true,
            "slack_channel": "#thermostat-alerts"
          }
        },
        {
          "when": "reservations_only",
          "mode": "heat",
          "cool_temp": 78,
          "heat_temp": 72,
          "frequency": "daily",
          "alerts": {
            "cool_below": 75,
            "cool_above": 82,
            "heat_below": 68,
            "heat_above": 75,
            "enabled": true
          }
        },
        {
          "when": "non_reservations",
          "mode": "cool",
          "cool_temp": 85,
          "heat_temp": 50,
          "freeze_protection": {
            "freeze_temp": 32,
            "heat_temp": 70
          }
        }
      ],
      "rest_times": ["01:00", "16:00"]
    }
  ]
}
```

**Alert Message Example:**
```
🌡️ Thermostat Alert - Boston - Main St
Thermostat: Upstairs
Current Mode: cool
Current Settings: Cool 68°F, Heat 70°F
Violations:
• 🔵 Cool setpoint 68°F is below threshold 70°F
```


## Azure Functions

You will get two Azure Functions:

1. **Hourly Cron Job:** This function runs hourly and will message you only if there are actions taken. To always get a message, set `ALWAYS_SEND_SLACK_SUMMARY` to true.
2. **HTTP Post Trigger:** This function can delete all guest codes. Use this URL:
   ```
   https://{{app-name}}-functions.azurewebsites.net/api/trigger_sync?delete_all_guest_codes=false
   ```
   All guest codes will be displayed with the word Guest, first name, and start date of reservation, e.g., `Guest Robert 20240412`.

## Known Issues with Wyze Locks

- **API Call Delays:** API calls include timers to slow down the process as the system requires time when calling the locks.
- **Code Name Formatting:** Occasionally, spaces in the names of the codes are removed.
- **Name Display Issues:** Sometimes, names do not appear, but they are present if you check via the API.
- **Synchronization Problems:** If something gets out of sync, you may need to delete all guest codes and re-sync.

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