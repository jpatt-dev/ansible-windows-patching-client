# AAP Controller Setup

AAP Controller objects (Projects, Inventories, Credentials, Job Templates,
Surveys, Schedules, and RBAC) are owned by a separate configuration-as-code
repository. This document is the runtime contract that configuration must
satisfy.

`surveys/` in this repository is transitional reference. Final survey objects
belong in the Controller CaC repository. The variable names below remain this
automation's contract.

## Project

Point an AAP Project at this repository. Use the production SCM URL and
credential owned by the client. Enable **Update Revision on Launch**.

Assign the approved Windows patch Execution Environment to every Windows job
template. Runtime collections come from that EE, not from a project
`collections/` directory.

## Inventory

Create an AAP Inventory **object** and attach it on job templates. Inside that
inventory, define groups:

| Group | Role |
| --- | --- |
| `windows_hosts` | Playbook `hosts:` boundary. Not a patch wave. |
| `windows_canary` | Approved Limit target |
| `windows_wave_1` | Approved Limit target |

AAP **Limit** selects the hosts that actually run. Effective hosts are
`windows_hosts` ∩ Limit.

Do not put the Inventory object name in Limit. Do not put a group name in the
job template Inventory field. Do not survey a host list.

Wave groups (`windows_canary`, `windows_wave_1`) control when a host is
patched. WSUS client configuration is owned by the client's
provisioning/post-provisioning process. This repository validates the
effective WSUS configuration before patch discovery or remediation but does
not assign or configure WSUS servers. Leftover `windows_wsus_*` inventory
groups do not affect provider or gates.

Inventory/group_vars may set `windows_pre_patch_reboot_mode` and
`windows_post_patch_reboot_mode` (`if_required` default, or `always`).
Do not put these on surveys.

Optional inventory/group_vars `patch_location` is a generic location label for
the final report (for example `Lexington Datacenter` or `Azure-East-US`). If
unset, the report uses an empty string. Do not survey this value.

Inventory/group_vars may set `patching_exception_enabled` and/or
`patching_exception_active` for a host exemption. Full Patch reporting uses
those inventory facts, not a surveyed host list.

## Credentials

Attach a Windows **Machine** credential for WinRM. Attach a Source Control
credential on the Project. Secrets stay in AAP Credentials, not in git.

WinRM authentication, including Kerberos, is environment-specific and is
configured during production implementation.

## Job Templates

Production templates: **Prompt on launch** for Limit only
(`ask_limit_on_launch: true`). Leave extra-var prompting off
(`ask_variables_on_launch: false`).

| Job Template | Playbook | Survey |
| --- | --- | --- |
| Windows - Full Patch | `playbooks/windows/full_patch.yml` | yes |
| Windows - Precheck | `playbooks/windows/precheck.yml` | yes |

Do not create separate Job Templates for Pre-Reboot, Discovery, Apply,
Post-Reboot, Postcheck, or Final Report against this repository. Those phases
run inside Full Patch.

Do not create a Configure WSUS job template against this repository. This
project does not assign or write WSUS client registry values. If an external
Controller configuration still lists `playbooks/windows/configure_wsus.yml` or
the old standalone phase playbooks, remove those job templates.

## Full Patch survey

Operator-facing inputs for **Windows - Full Patch**:

| Variable | Default | Meaning |
| --- | --- | --- |
| `change_ticket_id` | empty | Change ticket reference |
| `maintenance_window_start` | empty | UTC ISO-8601 start (`YYYY-MM-DDTHH:MM:SSZ`) |
| `maintenance_window_end` | empty | UTC ISO-8601 end |
| `maintenance_window_acknowledged` | `false` | Operator acknowledgement |
| `operator_authorize_patch_install` | `false` | Authorize install. Does not authorize reboot. |
| `operator_allow_pre_patch_reboot` | `false` | Authorize this job's pre-patch reboot (inventory mode still applies) |
| `operator_allow_post_patch_reboot` | `false` | Authorize this job's post-patch reboot (inventory mode still applies) |
| `snow_enabled` | `false` | Optional ServiceNow adapter |

Do not survey WSUS URLs, provider, patch mode, reboot policy
(`windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode`),
`patching_reboot_allowed`, `patching_exception_active`, or a host-targeting
variable.

Standalone **Windows - Precheck** uses a smaller read-only survey (`change_ticket_id`,
`snow_enabled`). It does not authorize install or reboot.

## Launch

Every job requires an explicit AAP Limit. Typical values:

- `windows_canary`
- `windows_wave_1`

Leave all operator flags `false` for a dry run. Authorize install and each
reboot only when those actions are intended for the current window.
