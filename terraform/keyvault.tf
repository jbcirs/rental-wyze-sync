resource "azurerm_key_vault" "key_vault" {
  name                        = "${var.resource_name}-keyvault"
  location                    = azurerm_resource_group.rg.location
  resource_group_name         = azurerm_resource_group.rg.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days = 5
  purge_protection_enabled    = false
}

resource "azurerm_key_vault_access_policy" "access_policy" {
  key_vault_id = azurerm_key_vault.key_vault.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_function_app.function.identity[0].principal_id

  secret_permissions = [
    "get",
  ]
}

resource "azurerm_key_vault_secret" "hospitable_email" {
  name         = "HOSPITABLE_EMAIL"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "hospitable_password" {
  name         = "HOSPITABLE_PASSWORD"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "wyze_email" {
  name         = "WYZE_EMAIL"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "wyze_password" {
  name         = "WYZE_PASSWORD"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "wyze_key_id" {
  name         = "WYZE_KEY_ID"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "wyze_api_key" {
  name         = "WYZE_API_KEY"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}

resource "azurerm_key_vault_secret" "slack_token" {
  name         = "SLACK_TOKEN"
  value        = "your_secret"
  key_vault_id = azurerm_key_vault.key_vault.id
}