variable "resource_name" {
  description = "The location of the resource group"
  default = "sync-locks"
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

variable "slack_channel" {
  description = "The slack channel"
  default = "#notifications"
  type = string
}

variable "delete_all_guest_codes" {
  description = "Delete all guest starting codes"
  default = false
  type = bool
}

variable "check_in_offset_hours" {
  description = "Check in offset hours"
  default = -1
  type = number
}

variable "check_out_offset_hours" {
  description = "Check out offset hours"
  default = 1
  type = number
}

variable "test" {
  description = "Testing"
  default = true
  type = bool
}

variable "test_property_name" {
  description = "Check out offset hours"
  default = "Paradise Cove Enchanted Oaks - FD"
  type = string
}