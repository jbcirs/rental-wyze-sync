terraform {
  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      version = "3.75.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
       prevent_deletion_if_contains_resources = false
     }
  }
}

data "azurerm_client_config" "current" {}

terraform {
  backend "azurerm" {
    resource_group_name   = "terraform"
    storage_account_name  = "terraformsgithub"
    container_name        = "tfstate"
    key                   = "terraform.tfstate"
  }
}