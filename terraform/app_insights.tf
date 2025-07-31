resource "azurerm_application_insights" "app_insights" {
  name                = "${var.app_name}-appinsights"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  retention_in_days   = 30
  tags = {
    App = var.app_name
    Environment = var.environment
  }
  lifecycle {
    replace_triggered_by = [
      # Force replacement if we need to remove workspace_id
      null_resource.app_insights_reset.id
    ]
  }
}

# This resource forces Application Insights to be recreated
resource "null_resource" "app_insights_reset" {
  triggers = {
    # Change this value to force recreation
    reset = "remove_workspace_id_v1"
  }
}