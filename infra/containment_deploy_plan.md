# Containment Deploy Plan

## Purpose
This appendix deploys the containment component of the thesis prototype in the simplest possible way for demonstration and evaluation.

## Quick deploy path
If a Linux host already has:
- Docker
- kubectl
- access to a Kubernetes cluster
- the repository cloned at `/home/ubuntu/master_defense`

then the containment component can be deployed with:

```bash
cd ~/master_defense/infra/ansible
cp inventory.ini.example inventory.ini
# edit inventory.ini with the correct IP
ansible-playbook deploy_containment.yml
