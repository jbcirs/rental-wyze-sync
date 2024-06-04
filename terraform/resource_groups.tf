resource "azurerm_resource_group" "rg" {
  name     = var.resource_name
  location = "Central US"
}