# AAP Windows Patching

## Overview

Red Hat Ansible Automation Platform (AAP) orchestrates Windows OS patching.
WSUS remains the update source. AAP controls targeting, authorization, reboot
handling, validation, and reporting.

This repository contains the Windows patching automation and its application
Controller CaC (`controller_cac/`): the AAP Project and Full Patch plus
Precheck Job Templates for LAB, IST, UAT, and PROD. Surveys stay in `surveys/`.
Inventories, credentials, organizations, and Execution Environments are
referenced by name from central platform CaC and the inventory repository.

Jobs do not install updates or reboot unless the operator authorizes those
actions for the current run.

## Supported playbooks

Primary operational playbook:

`playbooks/windows/full_patch.yml`

Read-only standalone validation/troubleshooting:

`playbooks/windows/precheck.yml`

Read-only current-build snapshot, independent of the patch lifecycle:

`playbooks/windows/build_verification.yml`

All Windows playbooks use `hosts: windows_hosts`. Launch with an explicit AAP
Limit. Effective hosts are `windows_hosts` ∩ Limit.

## Windows build verification

Job template name: `Windows - Build Verification`.

| Setting | Value |
| --- | --- |
| Playbook | `playbooks/windows/build_verification.yml` |
| Inventory | Existing LAB, IST, UAT, or PROD Windows inventory |
| Credential | Existing Windows WinRM credential |
| Execution environment | Windows patching EE |
| Limit | Required at launch. Hosts or an inventory group. Blank, `all`, and `*` fail. |

The job reads the current OS caption, version, and `BuildNumber.UBR`. It does
not install updates, reboot, change WSUS, or call ServiceNow. Location comes
from inventory `patch_location`. The environment label comes from inventory
`patch_environment`.

Email is disabled unless the job sets `report_email_enabled: true`. The same
SMTP variable names as patch reporting are used. This job does not call
`roles/report_email`.

```yaml
report_email_enabled: false
report_email_smtp_host: ""
report_email_smtp_port: 25
report_email_smtp_secure: never
report_email_from: ""
report_email_to: []
report_email_attach_csv: true
report_email_fail_on_error: true
```

AAP artifacts: `windows_build_verification_report` and
`windows_build_verification_csv`. The CSV is UTF-8 with a byte order mark so
Microsoft Excel opens it as text. Missing collected facts are `not_available`.
A missing `patch_location` is an empty location, not a fabricated site.

## Full Patch lifecycle

`playbooks/windows/full_patch.yml` is one AAP Job Template. It runs:

```
Precheck
→ eligibility
→ Pre-Reboot
→ Discovery
→ Apply
→ Post-Reboot
→ Postcheck
→ per-host final report / ITSM update
→ final aggregate report
```

Blocked or failed Precheck hosts skip remediation and remain in the job for
reporting. Historical actions such as `patch_attempted`, `updates_installed`,
and `reboot_performed` come from the phase that performed them. Missing phases
are reported as `not_available`. `patched` is true only when this job installed
updates; an already compliant host is `patched: false` with
`result: already_compliant`. JSON is the richer authoritative artifact; CSV is
the concise operational report.

WSUS client configuration is owned by the client's provisioning/post-provisioning
process. This repository validates the effective WSUS configuration before patch
discovery or remediation but does not assign or configure WSUS servers.

## Repository Structure

```
README.md
docs/
playbooks/windows/            # full_patch, precheck, and build verification
roles/
surveys/                     # Full Patch and Precheck operator surveys
controller_cac/              # Project and Job Template declarations
execution-environments/
```

## Runtime Ownership

| Layer | Owns |
| --- | --- |
| Git | Playbooks, roles, allowlist, application Controller CaC |
| AAP Inventory | Hosts, wave groups, reboot policy, permanent Git exemptions (inventory repo) |
| AAP Limit | Wave launch population |
| AAP exemption groups | Temporary patch/reboot exemptions and expiration metadata (Ops playbooks) |
| Full Patch survey | Per-run operator authorization, maintenance window, and change ticket |
| Job Template extra-vars | Per-environment CR and maintenance-window policy |
| AAP Credential | Authentication and secrets (central CaC) |

Normal patch operations do not require Git changes.

## Safety Controls

- Explicit Limit required. Blank, `all`, and `*` fail.
- Full Patch remediation Limits must be in the approved patch target list.
- WSUS client configuration is validated on the host. This repository does not assign or configure WSUS servers.
- Apply fails closed when WSUS validation is not `valid`.
- Maintenance window is enforced for Apply and actual reboots.
- `operator_authorize_patch_install` must be true to install.
- Pre-patch and post-patch reboot each require their own operator flag.
- `patching_reboot_allowed` is inventory-owned. A survey cannot override `false`.
- Inventory `windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode` are `if_required` (default) or `always`. Not survey controls.
- Permanent Git and active temporary AAP exemptions skip install and both reboot phases.
- Apply fails closed when a pending reboot remains.
- Standalone Precheck is fail-closed on `precheck_status` `blocked` or `failed`.

## Documentation

- [AAP Controller setup](docs/aap-controller-setup.md)
- [Controller CaC](controller_cac/README.md)
- [Operations](docs/operations.md)
- [Patch reporting](docs/patch-reporting.md)
- [External inventory and ServiceNow contracts](docs/external-contracts.md)
