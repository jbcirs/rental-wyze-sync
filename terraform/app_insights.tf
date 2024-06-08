resource "azurerm_application_insights" "app_insights" {
  name                = "${var.app_name}-appinsights"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  retention_in_days   = 30
  tags = {
    App = var.app_name
    Enviorment = var.enviorment
  }
}