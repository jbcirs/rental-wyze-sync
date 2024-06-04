variable "resource_name" {
  description = "The location of the resource group"
  default = "sync-locks"
  type        = string
}

variable "terraform_resource_group_name" {
  description = "Terraform Resource group name"
  type = string
}

variable "terraform_storage_account_name" {
  description = "Terraform storge account"
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