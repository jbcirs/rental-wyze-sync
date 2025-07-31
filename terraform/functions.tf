resource "azurerm_linux_function_app" "sync_locks_functions" {
  name                       = "${var.app_name}-functions"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  service_plan_id            = azurerm_service_plan.app_service_plan.id
  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }
  
  site_config {
    application_stack {
      python_version = "3.9"
    }
    application_insights_connection_string = azurerm_application_insights.app_insights.connection_string
    application_insights_key = azurerm_application_insights.app_insights.instrumentation_key
  }

  app_settings = {
    "TIMEZONE" = var.timezone
    FUNCTIONS_WORKER_RUNTIME = "python"
    "WEBSITE_RUN_FROM_PACKAGE" = "1"
    VAULT_URL = azurerm_key_vault.key_vault.vault_uri
    SLACK_CHANNEL = var.slack_channel
    CHECK_IN_OFFSET_HOURS = var.check_in_offset_hours
    CHECK_OUT_OFFSET_HOURS = var.check_out_offset_hours
    NON_PROD = var.non_prod
    LOCAL_DEVELOPMENT = var.local_development
    TEST_PROPERTY_NAME = var.test_property_name
    WYZE_API_DELAY_SECONDS = var.wyze_api_delay_seconds
    SMARTTHINGS_API_DELAY_SECONDS = var.smartthings_api_delay_seconds
    LIGHT_VERIFY_MAX_ATTEMPTS = var.light_verify_max_attempts
    STORAGE_ACCOUNT_NAME = azurerm_storage_account.storage.name
    ALWAYS_SEND_SLACK_SUMMARY = var.always_send_slack_summary
    SMARTTHINGS_TOKEN = var.smartthings_token
    APPINSIGHTS_INSTRUMENTATIONKEY = azurerm_application_insights.app_insights.instrumentation_key
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.app_insights.connection_string
  }

  depends_on = [
    azurerm_service_plan.app_service_plan
  ]

  tags = {
    App = var.app_name
    Environment = var.environment
  }
}