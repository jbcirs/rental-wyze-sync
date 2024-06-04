resource "azurerm_function_app" "sync_locks_job" {
  name                       = "${var.resource_name}-job"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  app_service_plan_id        = azurerm_app_service_plan.app_service_plan.id
  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  os_type                    = "Linux"
  version                    = "~4"
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    VAULT_URL = azurerm_key_vault.key_vault.vault_uri
    SLACK_CHANNEL = var.slack_channel
    DELETE_ALL_GUEST_CODES = var.delete_all_guest_codes
    CHECK_IN_OFFSET_HOURS = var.check_in_offset_hours
    CHECK_OUT_OFFSET_HOURS = var.check_out_offset_hours
    TEST = var.test
    TEST_PROPERTY_NAME = var.test_property_name
  }
}

resource "azurerm_function_app" "sync_locks_trigger" {
  name                       = "${var.resource_name}-trigger"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  app_service_plan_id        = azurerm_app_service_plan.app_service_plan.id
  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  os_type                    = "Linux"
  version                    = "~4"
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    VAULT_URL = azurerm_key_vault.key_vault.vault_uri
    SLACK_CHANNEL = var.slack_channel
    DELETE_ALL_GUEST_CODES = var.delete_all_guest_codes
    CHECK_IN_OFFSET_HOURS = var.check_in_offset_hours
    CHECK_OUT_OFFSET_HOURS = var.check_out_offset_hours
    TEST = var.test
    TEST_PROPERTY_NAME = var.test_property_name
  }
}
