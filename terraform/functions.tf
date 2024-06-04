resource "azurerm_function_app" "function" {
  name                       = "${var.resource_name}-job"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  app_service_plan_id        = azurerm_app_service_plan.app_service_plan.id
  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  os_type                    = "linux"

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    VAULT_URL = azurerm_key_vault.key_vault.vault_uri
  }
}

resource "azurerm_function_app" "function" {
  name                       = "${var.resource_name}-trigger"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  app_service_plan_id        = azurerm_app_service_plan.app_service_plan.id
  storage_account_name       = azurerm_storage_account.storage.name
  storage_account_access_key = azurerm_storage_account.storage.primary_access_key
  os_type                    = "linux"
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    VAULT_URL = azurerm_key_vault.key_vault.vault_uri
  }
}
