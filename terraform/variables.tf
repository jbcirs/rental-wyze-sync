variable "resource_name" {
  description = "The location of the resource group"
  default = "sync_locks"
  type        = string
}


variable "subscription_id" {
  description = "The Subscription ID of the Azure subscription"
  type = string
}

variable "client_id" {
  description = "The Client ID of the Azure Active Directory Application"
  type = string
}

variable "client_secret" {
  description = "The Client Secret of the Azure Active Directory Application"
  type = string
}

variable "tenant_id" {
  description = "The Tenant ID of the Azure Active Directory"
  type = string
}