variable "resource_group_name" {
  description = "The name of the resource group"
  type        = string
}

variable "location" {
  description = "The location of the resource group"
  type        = string
}

variable "resource_name" {
  description = "The location of the resource group"
  default = "sync_locks"
  type        = string
}
