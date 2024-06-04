resource "azurerm_resource_group" "rg" {
  name     = var.resource_name
  location = "Central US"
}



resource "azurerm_app_service_plan" "app_service_plan" {
  name                = "${var.resource_name}-appserviceplan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku {
    tier = "Free"
    size = "F1"
  }
}
