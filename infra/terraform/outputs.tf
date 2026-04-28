output "containment_admin_name" {
  value = openstack_compute_instance_v2.containment_admin.name
}

output "containment_admin_ip" {
  value = openstack_compute_instance_v2.containment_admin.access_ip_v4
}
