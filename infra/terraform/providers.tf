terraform {
  required_version = ">= 1.5.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 1.54"
    }
  }
}

provider "openstack" {
  auth_url                      = var.auth_url
  region                        = var.region
  application_credential_id     = var.application_credential_id
  application_credential_secret = var.application_credential_secret
}
