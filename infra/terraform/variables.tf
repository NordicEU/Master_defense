variable "auth_url" {
  type        = string
  description = "OpenStack auth URL"
}

variable "region" {
  type        = string
  default     = "RegionOne"
  description = "OpenStack region"
}

variable "application_credential_id" {
  type        = string
  description = "OpenStack application credential ID"
}

variable "application_credential_secret" {
  type        = string
  sensitive   = true
  description = "OpenStack application credential secret"
}

variable "image_name" {
  type        = string
  default     = "Ubuntu 22.04"
  description = "OpenStack image name"
}

variable "flavor_name" {
  type        = string
  default     = "m1.small"
  description = "OpenStack flavor name"
}

variable "network_name" {
  type        = string
  default     = "oslomet"
  description = "OpenStack network name"
}

variable "keypair_name" {
  type        = string
  description = "Existing OpenStack keypair name"
}

variable "security_group_name" {
  type        = string
  default     = "default"
  description = "OpenStack security group name"
}

variable "instance_name" {
  type        = string
  default     = "containment-admin"
  description = "Containment admin VM name"
}
