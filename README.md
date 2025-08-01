# Rental Device Sync - Smart Home Automation for Short-Term Rentals

This Azure Functions application automatically synchronizes smart home devices for rental properties. Built on Python 3.11 with Azure Functions v2, it integrates with Hospitable calendars to manage Wyze and SmartThings devices, looking one week in advance to add, update, or delete access codes and control lighting and thermostats based on reservation schedules.

## Key Features

### 🔒 **Smart Lock Management**

- Automatic guest code creation using last 4 digits of phone numbers
- Retry logic with configurable attempts for reliable code deployment
- Time-based code activation during reservation periods
- Comprehensive error handling and Slack notifications

### 💡 **Intelligent Light Control**

- Sunrise/sunset automation with configurable offsets
- Fixed time schedules with priority-based logic
- Reservation-aware lighting (on during stays, off when vacant)
- Retry verification for reliable state changes
- Detailed before/after Slack notifications

### 🌡️ **Advanced Thermostat Management**

- **Brand-Agnostic Architecture**: Generic coordination layer that works with any thermostat brand
- **Intelligent Frequency Control**: "first_day" vs "daily" processing to optimize API calls and energy management
- **Real-Time Cost Control**: Monitors actual device settings (not targets) to catch expensive guest changes
- **Smart Alert System**: Customizable temperature thresholds with detailed Slack notifications
- **Freeze Protection**: Automatic pipe protection during non-reservation periods with weather integration
- **Template System**: Easy addition of new thermostat brands using established patterns
- **Comprehensive Error Handling**: Graceful degradation and robust retry logic

### 📊 **Application Insights Integration**

- Comprehensive telemetry tracking for all function executions
- Custom metrics for execution times and performance monitoring
- Exception tracking with detailed error analysis
- Event tracking for function starts, completions, and failures
- Dashboard-ready metrics for operational insights

### 📱 **Enhanced Slack Integration**

- Consistent notification format across all device types
- Before/after state tracking for all changes
- Retry attempt reporting for transparency
- Error categorization with helpful emoji indicators
- Customizable alert channels for different notification types

### ⚡ **Modern Python 3.11 Runtime**

- Enhanced performance with up to 25% speed improvements over Python 3.9
- Better error messages and debugging capabilities
- Latest security patches and stability improvements
- Azure Functions v2 programming model for optimal cloud performance
- Improved dependency isolation and faster cold starts

## Setup

This code is set up with Terraform for infrastructure as code, using GitHub build workflows for deployment.

### 1. Fork the Code

Fork the repository to your GitHub account for deployment to Azure.

### 2. Setup Azure for GitHub Deployment

Use App Registrations in Azure. Run these commands from Azure PowerShell in the portal or locally:

#### Get Subscription GUID

```sh
az account show --query id
```

#### Setup App Registration

```sh
az ad sp create-for-rbac --name terraform-github-rental-sync --role Contributor --scopes /subscriptions/00000000-0000-0000-0000-000000000000
```

The JSON object you receive will be needed for the GitHub secrets. In the portal, open the new App Registration, navigate to **Certificates & Secrets**, and set up Federated credentials for the GitHub repo.

### 3. Create an Azure Storage Account

Create an Azure Storage Account to store Terraform state files.

1. Open the new storage account.
2. Add a `tfstate` folder in Blob Storage under Storage Browser.

   Follow these [Microsoft Instructions](https://learn.microsoft.com/en-us/devops/deliver/iac-github-actions) for more details.

3. Update `storage_account_name` in `./terraform/providers.tf` with the storage account name you created.

### 4. Setup Slack Bot

Set up a Slack Bot and give it the appropriate access. Add the correct channels (`#lock` or `lock-np`).

### 5. Create Wyze Developer API

Create a Wyze developer API from the [Wyze Developer Portal](https://developer-api-console.wyze.com/).

### 6. Add GitHub Action Secrets

Add the following GitHub Action Secrets:

```env
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
OPENWEATHERMAP_KEY
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
- `OPENWEATHERMAP_KEY` API key from [OpenWeatherMap](https://openweathermap.org/api) for weather data.

### Environment Variables Configuration

The following environment variables can be configured in your Terraform variables:

#### API Delays and Retry Settings

- `WYZE_API_DELAY_SECONDS`: Delay between Wyze API calls (default: 10)
- `SMARTTHINGS_API_DELAY_SECONDS`: Delay between SmartThings API calls (default: 3)
- `LOCK_CODE_ADD_MAX_ATTEMPTS`: Maximum attempts to add a lock code (default: 3)
- `LOCK_CODE_VERIFY_MAX_ATTEMPTS`: Maximum attempts to verify a lock code (default: 3)
- `LIGHT_VERIFY_MAX_ATTEMPTS`: Maximum attempts to verify light state changes (default: 3)

#### Recent Changes

- SmartThings lock code refreshes are now minimized to avoid API throttling and errors. Lock status is retrieved without forcing a refresh except when absolutely necessary.

#### Slack Message Format Update

- All lock code Slack messages now include the lock name for clarity. Example:
  `:key: Added Lock code for John at Paradise Cove Enchanted Oaks on Master Bath Closet Door Lock (verified on attempt 2)`

#### Time and Location Settings

- `TIMEZONE`: Timezone for time calculations (e.g., "America/Chicago")
- `CHECK_IN_OFFSET_HOURS`: Hours to offset check-in time (default: -1)
- `CHECK_OUT_OFFSET_HOURS`: Hours to offset check-out time (default: 1)

#### Notification Settings

- `SLACK_CHANNEL`: Slack channel for notifications (e.g., "#rentals")
- `ALWAYS_SEND_SLACK_SUMMARY`: Always send summary messages (default: false)

#### Timer and Environment Settings

- `NON_PROD`: Set to true for non-production environments (default: false)
- `LOCAL_DEVELOPMENT`: Set to true for local development (default: false)

> **Note**: The scheduled timer function runs every 30 minutes **only in production environments** (`NON_PROD=false`). In non-production environments, the timer is completely disabled to prevent accidental executions. Use the HTTP trigger endpoints for manual testing in non-production.

### 7. Deploy the Azure Functions

Run the `Deploy Prod` GitHub Action to deploy the Azure Functions and start running them.

### 8. Monitor with Application Insights

Your deployment now includes Azure Application Insights for comprehensive monitoring:

#### Available Metrics and Insights

- **Function Execution Times**: Track how long each sync operation takes
- **Error Tracking**: Automatic exception capture with stack traces
- **Custom Events**: Function start/completion/failure events with context
- **Performance Metrics**: Execution time trends and performance analysis
- **Live Metrics**: Real-time function execution monitoring
- **Dependency Tracking**: Monitor calls to external APIs (Wyze, SmartThings, Slack)

#### Access Application Insights

1. Navigate to your Azure resource group in the Azure portal
2. Open the Application Insights resource named `{app_name}-appinsights`
3. Use the **Logs** section to query custom telemetry data
4. Check **Live Metrics** for real-time monitoring
5. Review **Failures** for exception details and stack traces

#### Example Queries

```kusto
// Function execution times over the last 24 hours
customEvents
| where timestamp > ago(24h)
| where name contains "Completed"
| extend ExecutionTime = todouble(customDimensions["execution_time_seconds"])
| summarize avg(ExecutionTime), max(ExecutionTime), min(ExecutionTime) by name

// Failed executions with error details
customEvents
| where timestamp > ago(7d)
| where name contains "Failed"
| project timestamp, name, customDimensions["error"]
```

### 9. Cleanup Deployment

Run `Cleanup Prod` to remove the deployment.

### 10. Adding Properties, Locks, Lights, and Thermostats to Azure Storage Table

Each device (lock, light, thermostat) should be added to the Azure Storage Table called `properties`.

- PartitionKey: PMS property name
- RowKey: PMS System
- BrandSettings: List of all settings needed for a brand to run
- Location: GPS coordinates needed for sunset and sunrise times
- Active: `true` or `false` flag
- Locks: List of locks by brand and lock name
- Lights: List of SmartThings lights with time-based controls (see below)
- Thermostats: List of thermostats with full configuration (see below)

#### Light Configuration

SmartThings lights can be controlled based on time schedules, sunrise/sunset calculations, and reservation status. The system includes retry logic and comprehensive Slack notifications.

##### Light Configuration Fields

- `brand`: Always "smartthings" for SmartThings lights
- `name`: The exact device name as it appears in SmartThings
- `when`: When the light should operate
  - `"reservations_only"`: Only during active reservations
  - `"non_reservations"`: Only when property is vacant
- `minutes_before_sunset`: Turn light ON X minutes before actual sunset (optional)
- `minutes_after_sunrise`: Turn light OFF X minutes after actual sunrise (optional)
- `start_time`: Fixed time to turn light ON (format: "HH:MM", 24-hour) (optional)
- `stop_time`: Fixed time to turn light OFF (format: "HH:MM", 24-hour) (optional)

##### Light Logic Priority

1. **Stop Time** (highest): If `stop_time` is reached, light turns OFF regardless of other conditions
2. **Explicit Time Window**: If `start_time`/`stop_time` are set, follows this schedule
3. **Sunrise/Sunset with Offsets**: Uses calculated sunrise/sunset times with configured offsets
4. **Default**: Light remains OFF if no conditions are met

##### Light Examples

```json
"Lights": [
  {
    "brand": "smartthings", 
    "name": "String Lights",
    "when": "reservations_only",
    "minutes_before_sunset": 30,
    "minutes_after_sunrise": 30,
    "start_time": null,
    "stop_time": "23:00"
  },
  {
    "brand": "smartthings",
    "name": "Porch Light", 
    "when": "reservations_only",
    "start_time": "18:00",
    "stop_time": "22:00"
  },
  {
    "brand": "smartthings",
    "name": "Garden Lights",
    "when": "non_reservations", 
    "minutes_before_sunset": 15,
    "minutes_after_sunrise": 15
  }
]
```

##### Light Slack Notifications

- Successful changes: `💡 Updated Lights 'String Lights' at 'Paradise Cove': OFF → ON`
- With retries: `💡 Updated Lights 'String Lights' at 'Paradise Cove': OFF → ON (verified on attempt 2)`
- Failures: `⚠️ Failed to update Lights 'String Lights' at 'Paradise Cove' to ON after 3 attempts`

#### Thermostat Configuration (Advanced Features)

The thermostat system now features a **clean brand-agnostic architecture** with advanced frequency control and intelligent cost monitoring during guest stays.

##### Key Features

- **Generic Coordination**: Main logic works with any thermostat brand through dynamic routing
- **Frequency Control**: Choose between "first_day" (API-efficient) or "daily" (maximum control) processing
- **Cost Control Alerts**: Monitor actual device settings to catch expensive guest temperature changes
- **Brand Flexibility**: Easy addition of new brands using template system

##### Frequency Options

- `"first_day"` (default): Apply changes only on check-in day - reduces API calls and prevents throttling
- `"daily"`: Apply changes every day during reservation - maximum control for variable weather

##### Alert System

Monitor actual thermostat settings (not target settings) to catch when guests set extreme temperatures:

- `cool_below`/`cool_above`: Cooling setpoint thresholds
- `heat_below`/`heat_above`: Heating setpoint thresholds  
- `enabled`: Enable/disable alerts (default: true if thresholds exist)
- `slack_channel`: Optional custom channel for alerts

##### Enhanced Configuration Example

```json
{
  "PartitionKey": "Mountain Cabin Resort",
  "RowKey": "Hospitable", 
  "Active": true,
  "Location": {"latitude": 40.7128, "longitude": -74.0060},
  "BrandSettings": "[{\"brand\":\"smartthings\",\"location\":\"Cabin Location\"}]",
  "Thermostats": [
    {
      "brand": "smartthings",
      "manufacture": "ecobee",
      "name": "Main Floor Thermostat",
      "temperatures": [
        {
          "when": "reservations_only",
          "mode": "auto",
          "cool_temp": 74,
          "heat_temp": 70,
          "frequency": "daily",
          "alerts": {
            "cool_below": 72,
            "cool_above": 78,
            "heat_below": 67,
            "heat_above": 76,
            "enabled": true,
            "slack_channel": "#energy-alerts"
          }
        },
        {
          "when": "non_reservations",
          "mode": "auto",
          "cool_temp": 85,
          "heat_temp": 50,
          "freeze_protection": {
            "freeze_temp": 32,
            "heat_temp": 55
          }
        }
      ]
    }
  ]
}
```

##### Supported Brands

- **SmartThings**: JSON configuration with location-based device lookup
- **Wyze**: Client-based with MAC address identification  
- **Template System**: Easy pattern for adding new brands (see `src/brands/__template__/`)

##### Alert Message Examples

**Cost Control Alert:**
```
🌡️ Thermostat Alert - Mountain Cabin Resort
Thermostat: Main Floor Thermostat
Current Mode: cool
Current Settings: Cool 68°F, Heat 70°F
Violations:
• 🔵 Cool setpoint 68°F is below threshold 72°F
```

**Temperature Change Notification:**
```
🌡️ Updated Thermostat 'Main Floor' at 'Mountain Cabin'
Current Temperature: 73°F
Changes Made:
• Mode: heat → cool
• Cool: 78°F → 74°F
• Heat: 72°F → 70°F
```

## Azure Functions

You will get two Azure Functions:

1. **5-Minute Timer Cron Job:** This function runs every 30 minutes and will message you only if there are actions taken. To always get a message, set `ALWAYS_SEND_SLACK_SUMMARY` to true.
2. **HTTP Post Trigger:** This function can delete all guest codes. Use this URL:
   ```
   https://{{app-name}}-functions.azurewebsites.net/api/trigger_sync?delete_all_guest_codes=false
   ```
   All guest codes will be displayed with the word Guest, first name, and start date of reservation, e.g., `Guest Robert 20240412`.

## Runtime Requirements

### Python 3.11

This application requires **Python 3.11** for:

- Enhanced performance and faster execution
- Better error handling and debugging
- Latest security features
- Compatibility with Azure Functions v2 programming model

### Local Development Setup

For local development, ensure you have Python 3.11 installed:

```bash
# Check Python version
python --version  # Should show 3.11.x

# Navigate to function app
cd src

# Install dependencies
pip install -r requirements.txt

# Start the function locally
func start
```

## Known Issues with Wyze Locks

- **API Call Delays:** API calls include timers to slow down the process as the system requires time when calling the locks.
- **Code Name Formatting:** Occasionally, spaces in the names of the codes are removed.
- **Name Display Issues:** Sometimes, names do not appear, but they are present if you check via the API.
- **Synchronization Problems:** If something gets out of sync, you may need to delete all guest codes and re-sync.

## Manual Azure Resource Purge Before Redeploy

If you need to manually purge resources in Azure before redeploying, run the following Azure CLI commands:

```sh
az group delete --name "rental-sync" --yes --no-wait
az keyvault purge --name rental-sync-keyvault
```

- The first command deletes the resource group and all resources within it.
- The second command purges the soft-deleted Key Vault so it can be recreated immediately.

> **Azure CLI Note:**
> When running `az keyvault purge --name rental-sync-keyvault`, the command may appear to hang or run forever. This is a known Azure bug. After a couple of minutes, cancel the command, then re-run `az group delete --name "rental-sync" --yes --no-wait` to ensure the resource group is deleted. You may need to repeat this process until the Key Vault is fully purged and the group deletion succeeds.

> **Note:** You must have sufficient permissions in Azure to run these commands. Purging is required if you see errors about existing or soft-deleted Key Vaults during redeployment.

## Properties Import Tool

For bulk importing property configurations into Azure Table Storage, use the properties import script located in `scripts/properties-import/import.py`.

### Prerequisites

Install required Python packages:

```sh
pip install pandas azure-data-tables
```

**For Key Vault URL usage:**

- You must be logged in with `az login`
- You must have permissions to read the Key Vault secret

### Usage

1. Create a `properties.csv` file in the `scripts/properties-import/` directory with your property data
2. Get your Azure Storage Account connection string from the Azure portal OR use a Key Vault secret URL
3. Run the import script:

#### Option 1: Direct connection string

```sh
cd scripts/properties-import
python import.py "DefaultEndpointsProtocol=https;AccountName=<your-account>;AccountKey=<your-key>;EndpointSuffix=core.windows.net"
```

#### Option 2: Key Vault secret URL

```sh
cd scripts/properties-import
python import.py "https://<vault>.vault.azure.net/secrets/<secret-name>/<version>"
```

### CSV Format

The CSV file should include at minimum:

- `PartitionKey`: PMS property name
- `RowKey`: PMS System (e.g., "Hospitable")

Additional columns will be imported as entity properties. Complex JSON objects (like Locks, Lights, Thermostats) should be properly formatted JSON strings in the CSV.

### Features

- Creates the 'properties' table if it doesn't exist
- Upserts entities (updates existing, creates new)
- Progress reporting every 10 uploads
- Error handling for individual row failures
- Validates connection string and file existence

### First Time Local

For first time run of any scripts use:

```bash
chmod +x ./scripts/<filename>.sh
```

### Setup Environment Local

```bash
python3 -m venv .venv
. .venv/bin/activate
```
