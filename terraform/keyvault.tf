resource "azurerm_key_vault" "key_vault" {
  name                        = "${var.app_name}-keyvault"
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false

  tags = {
    App        = var.app_name
    Environment = var.environment
  }
}

# Grant the service principal access to the Key Vault
resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.key_vault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Purge"
  ]
  depends_on = [azurerm_key_vault.key_vault]
}

resource "azurerm_key_vault_access_policy" "current_user" {
  key_vault_id = azurerm_key_vault.key_vault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Set", "Get", "Delete", "Purge", "List"
  ]

  depends_on = [azurerm_key_vault.key_vault]
}

resource "azurerm_key_vault_access_policy" "admin" {
  key_vault_id = azurerm_key_vault.key_vault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = var.aad_objectId_admin

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Recover", "Backup", "Restore", "Purge"
  ]

  depends_on = [azurerm_key_vault.key_vault]
}

resource "azurerm_key_vault_access_policy" "sync_locks_functions_access_policy" {
  key_vault_id = azurerm_key_vault.key_vault.id
  tenant_id    = azurerm_linux_function_app.sync_locks_functions.identity.0.tenant_id
  object_id    = azurerm_linux_function_app.sync_locks_functions.identity.0.principal_id

  secret_permissions = [
    "Get"
  ]

  depends_on = [azurerm_key_vault.key_vault]
}

resource "azurerm_key_vault_secret" "hospitable_email" {
  name         = "HOSPITABLE-EMAIL"
  value        = var.hospitable_email
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "hospitable_password" {
  name         = "HOSPITABLE-PASSWORD"
  value        = var.hospitable_password
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "wyze_email" {
  name         = "WYZE-EMAIL"
  value        = var.wyze_email
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "wyze_password" {
  name         = "WYZE-PASSWORD"
  value        = var.wyze_password
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "wyze_key_id" {
  name         = "WYZE-KEY-ID"
  value        = var.wyze_key_id
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "wyze_api_key" {
  name         = "WYZE-API-KEY"
  value        = var.wyze_api_key
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "slack_token" {
  name         = "SLACK-TOKEN"
  value        = var.slack_token
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "STORAGE_ACCOUNT_KEY" {
  name         = "STORAGE-ACCOUNT-KEY"
  value        = azurerm_storage_account.storage.primary_access_key
  key_vault_id = azurerm_key_vault.key_vault.id

  depends_on = [azurerm_key_vault.key_vault, azurerm_key_vault_access_policy.terraform]
}
