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
  }

  app_settings = {
    "APPINSIGHTS_INSTRUMENTATIONKEY" = azurerm_application_insights.app_insights.instrumentation_key
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.app_insights.connection_string
    "ApplicationInsightsAgent_EXTENSION_VERSION" = "~2"
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
    STORAGE_ACCOUNT_NAME = azurerm_storage_account.storage.name
  }

  depends_on = [
    azurerm_application_insights.app_insights,
    azurerm_service_plan.app_service_plan
  ]

  tags = {
    App = var.app_name
    Environment = var.environment
  }
}