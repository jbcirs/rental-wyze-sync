resource "azurerm_service_plan" "app_service_plan" {
  name                = "${var.app_name}-appserviceplan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "Y1"
  tags = {
    App = var.app_name
    Enviorment = var.enviorment
  }
}
