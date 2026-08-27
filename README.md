# AAP Windows Patching

## Overview

Red Hat Ansible Automation Platform (AAP) orchestrates Windows OS patching.
WSUS remains the update source. AAP controls targeting, authorization, reboot
handling, validation, and reporting.

This repository contains the Windows patching automation. AAP Controller
configuration-as-code is maintained separately. Projects, Inventories,
Credentials, Job Templates, Workflow Job Templates, Surveys, Schedules, and
RBAC are owned by that Controller repository. This repository documents the
runtime variables and expectations that configuration must provide.

Jobs do not install updates or reboot unless the operator authorizes those
actions for the current run.

## Workflow

```
Precheck
→ Pre-Patch Reboot If Required
→ Discovery
→ Apply
→ Post-Patch Reboot If Required
→ Postcheck
→ Final Patch Report
```

Each node is a separate AAP job. Pending reboot, WSUS assignment, exceptions,
and other critical state are re-evaluated in the job that needs them.

Configure WSUS is a separate job template. It is not part of this chain.

## Repository Structure

```
README.md
docs/
playbooks/windows/            # Precheck, reboot, discovery, apply, postcheck, Configure WSUS
playbooks/orchestration/     # Final Patch Report
roles/
surveys/                     # transitional; final survey ownership moves to Controller CaC
execution-environments/
```

## Runtime Ownership

| Layer | Owns |
| --- | --- |
| Git | Stable automation logic and policy |
| AAP Inventory | Infrastructure truth (hosts, groups, WSUS assignment, reboot policy) |
| AAP Limit | Hosts targeted for the run |
| Workflow survey | Per-run operator authorization |
| AAP Credential | Authentication and secrets |

Normal patch operations do not require Git changes.

## Safety Controls

- Explicit Limit required. Blank, `all`, and `*` fail.
- Remediation Limits must be in the approved patch target list.
- WSUS assignment is inventory-derived (`windows_wsus_*`).
- Maintenance window is enforced for Apply and actual reboots.
- `operator_authorize_patch_install` must be true to install.
- Pre-patch and post-patch reboot each require their own operator flag.
- `patching_reboot_allowed` is inventory-owned. A survey cannot override `false`.
- Inventory `windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode` are `if_required` (default) or `always`. Not survey controls.
- Temporary patch-cycle exceptions skip install and reboot for listed hosts.
- Apply fails closed when a pending reboot remains.

## Documentation

- [AAP Controller setup](docs/aap-controller-setup.md)
- [Operations](docs/operations.md)
- [Patch reporting](docs/patch-reporting.md)
