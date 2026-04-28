resource "openstack_compute_instance_v2" "containment_admin" {
  name            = var.instance_name
  image_name      = var.image_name
  flavor_name     = var.flavor_name
  key_pair        = var.keypair_name
  security_groups = [var.security_group_name]

  network {
    name = var.network_name
  }
}
