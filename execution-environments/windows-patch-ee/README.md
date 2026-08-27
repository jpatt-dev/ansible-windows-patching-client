# windows-patch-ee

Ansible Automation Platform **2.7** Execution Environment for this Windows
patching solution. Declares `ansible.windows` in `requirements.yml`
(aligned with the repository root collection requirements).

Collections are **declared** only — they are **not** vendored into this git
repository.

`servicenow.itsm` is **not** included (URI stubs in-repo). Add it in a client
fork if you replace EXAMPLE ServiceNow tasks.

## Build with ansible-builder

From this directory:

```bash
ansible-builder build \
  -f execution-environment.yml \
  -t windows-patch-ee:latest \
  --prune-images
```

Pull the base image from `registry.redhat.io` with a Red Hat login on the
build host (credentials stay on the builder, not in git).

## Test locally with ansible-navigator

```bash
# From the repository root (example: Windows precheck)
# Pass the client Inventory path or AAP-exported inventory with -i
ansible-navigator run \
  playbooks/windows/precheck.yml \
  -i /path/to/client-inventory \
  --eei windows-patch-ee:latest \
  --mode stdout
```

## Push to Private Automation Hub or an approved registry

```bash
# Placeholder registry — replace with the client PAH / quay / approved registry
podman tag windows-patch-ee:latest registry.example.com/aap/windows-patch-ee:latest
podman push registry.example.com/aap/windows-patch-ee:latest
```

Do not commit registry passwords or pull secrets.

## Select the EE on AAP Job Templates

1. **Administration → Execution Environments → Add**
2. Name: `windows-patch-ee`
3. Image: `registry.example.com/aap/windows-patch-ee:latest`
4. Pull credential: client-owned (if private)
5. On each Job Template: set **Execution Environment** to `windows-patch-ee`

See [`docs/aap-controller-setup.md`](../../docs/aap-controller-setup.md).
