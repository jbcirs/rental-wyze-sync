resource "azurerm_resource_group" "rg" {
  name     = var.app_name
  location = "Central US"
  tags = {
    App = var.app_name
    Enviorment = var.enviorment
  }
}