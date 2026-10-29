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

Read-only Linux distribution and running-kernel snapshot:

`playbooks/linux/build_verification.yml`

All Windows patching playbooks use `hosts: windows_hosts`. Effective hosts are
`windows_hosts` ∩ Limit. Full Patch and Precheck still reject a blank Limit,
`all`, and `*`. Build Verification allows those Limits because it is read-only
and never leaves its platform group (`windows_hosts` or `linux_hosts`).

## Build verification

Windows and Linux each have a collection playbook. Both include
`playbooks/build_verification/tasks/` for one CSV, the AAP artifacts, and
optional email. There is no separate reporting role.

The job does not query ServiceNow. The reporting contract is
`docs/build-verification-contract.md`. Windows reads `inventory_hostname`,
`cmdb_fqdn`, `cmdb_os_release`, `patch_location`, `patch_environment`, and
`sys_id`. A missing CMDB value does not stop the live build query, and the
live OS caption or DNS name does not fill that value. The current build is
not a compliance result.

| Field | Source |
| --- | --- |
| Hostname | `inventory_hostname` |
| FQDN | `cmdb_fqdn` |
| Platform | `windows` |
| OS Release | `cmdb_os_release` |
| OS Version | Live Windows version |
| Current Build / Kernel | Live `BuildNumber.UBR` |
| Location | `patch_location` (empty when unset) |
| Environment | `patch_environment` |
| Collection Status | `success`, `failed`, or `unreachable` |
| Collection Time | Ansible |
| Diagnostic | Ansible |

`sys_id` is copied to `snow_ci_sys_id` in the JSON artifact only.

### Windows - Build Verification

| Setting | Value |
| --- | --- |
| Playbook | `playbooks/windows/build_verification.yml` |
| Inventory | Existing LAB, IST, UAT, or PROD Windows inventory |
| Credential | Existing Windows WinRM credential |
| Execution environment | Windows patching EE |
| Limit | Optional. Blank, `all`, `*`, hosts, or an inventory group. |
| Job slicing | `1`. Slicing would send more than one CSV and email. |

The Windows play keeps its PowerShell query for OS version and
`BuildNumber.UBR`. Native Windows facts do not include UBR. The job does not
install updates, reboot, change WSUS, or call ServiceNow. After the report and
optional email, the job fails when any targeted host is `failed` or
`unreachable`. Missing CMDB values and a missing UBR do not fail the job.

AAP artifacts: `windows_build_verification_report` and
`windows_build_verification_csv`.

### Linux - Build Verification

| Setting | Value |
| --- | --- |
| Playbook | `playbooks/linux/build_verification.yml` |
| Inventory | LAB, IST, UAT, or PROD inventory that contains `linux_hosts` |
| Credential | Existing Linux SSH credential |
| Execution environment | An EE that can SSH to Linux. The Windows patching EE is sufficient when SSH is allowed. |
| Limit | Optional. Blank, `all`, `*`, hosts, or an inventory group. |
| Job slicing | `1` |

The Linux play gathers minimal facts (`gather_subset: min`) and records
`ansible_distribution_version` and `ansible_kernel`. Current Build / Kernel is
the running kernel. The job does not update packages or reboot.

AAP artifacts: `linux_build_verification_report` and
`linux_build_verification_csv`.

### Report behavior

Email is disabled unless the job sets `report_email_enabled: true`. The same
SMTP variable names as patch reporting are used. Neither build-verification
play calls `roles/report_email`. SMTP tasks load only when email is enabled.

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

The CSV is UTF-8 with a byte order mark and CRLF. Schema version is `2`.
Column names and the per-host JSON are in `docs/build-verification-contract.md`.
A successful collection with a full build still names any missing CMDB field
in `Diagnostic`. Values that start with `=`, `+`, `-`, `@`, a tab, or a
carriage return are prefixed with an apostrophe so Excel does not treat them
as formulas. Missing collected facts are `not_available`. A missing
`patch_location` is an empty location. Per-host rows stay in the JSON
artifact. One run produces one CSV and, when email is enabled, one message.

AAP LAB, after the inventory variables exist on the Windows inventory:

1. Job template `Windows - Build Verification`, playbook
   `playbooks/windows/build_verification.yml`, Windows patching EE, existing
   WinRM credential, LAB inventory, `job_slice_count: 1`.
2. Run with a blank Limit and again with a small host Limit. Confirm the job
   stays inside `windows_hosts` and does not install updates or reboot.
3. Confirm hostname, FQDN, OS release, location, environment, and sys_id match
   inventory, and that OS version and `BuildNumber.UBR` came from the host.
4. Include one unreachable or failed host and confirm its row is still in the
   CSV, then confirm the job finishes failed. Open the CSV in Excel and
   confirm a formula-like value is text. A host that only lacks CMDB metadata
   or UBR should leave the job successful.
5. Enable email only with the internal relay variables and confirm one message.

Client configuration still required: map the ServiceNow CMDB columns onto
`cmdb_fqdn`, `cmdb_os_release`, `patch_location`, `patch_environment`, and
`sys_id` without rebuilding wave or exemption data. Set the SMTP extra
variables only when email is wanted. Create the AAP job template if it is
not already present. This repository does not declare that template in
controller CaC.

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
