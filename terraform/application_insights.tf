resource "azurerm_application_insights" "app_insights" {
  name                = "${var.app_name}-appinsights"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
  retention_in_days   = 90

  tags = {
    App         = var.app_name
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [
      workspace_id  # Ignore changes to workspace_id since it can't be removed once set
    ]
  }
}

# Output the instrumentation key and connection string for use in other resources
output "application_insights_instrumentation_key" {
  value = azurerm_application_insights.app_insights.instrumentation_key
  sensitive = true
}

output "application_insights_connection_string" {
  value = azurerm_application_insights.app_insights.connection_string
  sensitive = true
}
