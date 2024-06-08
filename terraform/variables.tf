variable "app_name" {
  description = "The location of the resource group"
  type        = string
}

variable "app_name_no_spaces" {
  description = "The location of the resource group"
  type        = string
}

variable "slack_channel" {
  description = "The slack channel"
  default = "#notifications"
  type = string
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

variable "non_prod" {
  description = "Non Prod"
  type = bool
}

variable "local_development" {
  description = "Running local development"
  default = false
  type = bool
}

variable "test_property_name" {
  description = "Check out offset hours"
  default = "Paradise Cove Enchanted Oaks - FD"
  type = string
}

variable "hospitable_email" {
  description = "Hospitable email"
  type        = string
}

variable "hospitable_password" {
  description = "Hospitable password"
  type        = string
}

variable "wyze_email" {
  description = "Wyze email"
  type        = string
}

variable "wyze_password" {
  description = "Wyze password"
  type        = string
}

variable "wyze_key_id" {
  description = "Wyze key ID"
  type        = string
}

variable "wyze_api_key" {
  description = "Wyze API key"
  type        = string
}

variable "slack_token" {
  description = "Slack token"
  type        = string
}

variable "aad_objectId_admin" {
  description    = "AAD Object Id for Policies"
  type           = string
}

variable "wyze_api_delay_seconds" {
  description = "Wyze API call delay"
  default = 5
  type = number
}

variable "environment" {
  description    = "Environment being used"
  type           = string
}

variable "timezone" {
  description    = "Timezone of the app"
  type           = string
}