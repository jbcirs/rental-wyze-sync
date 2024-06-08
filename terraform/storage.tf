resource "azurerm_storage_account" "storage" {
  name                     = "${var.app_name_no_spaces}storageacct"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags = {
    App = var.app_name
    Environment = var.environment
  }
}

resource "azurerm_storage_table" "locks" {
  name                = "locks"
  storage_account_name = azurerm_storage_account.storage.name
}