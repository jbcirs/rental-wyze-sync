resource "azurerm_storage_account" "storage" {
  name                     = "${var.app_name_no_spaces}storageacct"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags = {
    App = var.app_name
    Enviorment = var.enviorment
  }
}

resource "azurerm_storage_table" "locks" {
  name                = "locks"
  storage_account_name = azurerm_storage_account.storage.name
}

output "storage_account_name" {
  value = azurerm_storage_account.storage.name
}

output "storage_account_primary_access_key" {
  value = azurerm_storage_account.storage.primary_access_key
}