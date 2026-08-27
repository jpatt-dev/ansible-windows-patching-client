# AAP Controller Setup

AAP Controller objects (Projects, Inventories, Credentials, Job Templates,
Workflow Job Templates, Surveys, Schedules, and RBAC) are owned by a separate
configuration-as-code repository. This document is the runtime contract that
configuration must satisfy.

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
| `windows_wsus_*` | WSUS assignment (URL and mode in group_vars) |

AAP **Limit** selects the hosts that actually run. Effective hosts are
`windows_hosts` ∩ Limit.

Do not put the Inventory object name in Limit. Do not put a group name in the
job template Inventory field. Do not survey a host list.

Each host must belong to **exactly one** `windows_wsus_*` assignment group.
Wave groups (`windows_canary`, `windows_wave_1`) control when a host is
patched, not where updates come from.

Inventory/group_vars may set `windows_pre_patch_reboot_mode` and
`windows_post_patch_reboot_mode` (`if_required` default, or `always`).
Do not put these on surveys.

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
| Windows - Configure WSUS | `playbooks/windows/configure_wsus.yml` | none |
| Windows - Precheck | `playbooks/windows/precheck.yml` | yes |
| Windows - Pre-Patch Reboot If Required | `playbooks/windows/pre_patch_reboot_if_required.yml` | yes |
| Windows - Patch Discovery | `playbooks/windows/patch_discovery.yml` | yes |
| Windows - Apply Updates | `playbooks/windows/apply.yml` | yes |
| Windows - Post-Patch Reboot If Required | `playbooks/windows/post_patch_reboot_if_required.yml` | yes |
| Windows - Postcheck | `playbooks/windows/postcheck.yml` | yes |
| Windows - Final Patch Report | `playbooks/orchestration/patch_compliance_report.yml` | yes |

Configure WSUS never installs updates and never reboots. Mode
(`validate` or `enforce`) comes from inventory, not a survey.

## Workflow

**Windows Patch Workflow** (and **Windows Canary Patch Workflow**, same nodes):

```
Precheck
→ Pre-Patch Reboot If Required
→ Discovery
→ Apply
→ Post-Patch Reboot If Required
→ Postcheck
→ Final Patch Report
```

Workflow nodes do not preserve host facts. Each job re-collects what it needs.

Apply job-template survey answers do not automatically reach Reboot, Postcheck,
or Report. Set shared operator inputs on the **workflow** survey.

The Controller workflow is defined in the separate CaC repository. Production
may use Always transitions so later validation and reporting can still run
after a failed phase. Do not add edges that allow Apply or reboot after a
failed safety control.

Confirm Limit and survey-variable propagation during Controller acceptance.

## Workflow Survey

Operator-facing inputs for the workflow:

| Variable | Default | Meaning |
| --- | --- | --- |
| `change_ticket_id` | empty | Change ticket reference |
| `maintenance_window_start` | empty | UTC ISO-8601 start (`YYYY-MM-DDTHH:MM:SSZ`) |
| `maintenance_window_end` | empty | UTC ISO-8601 end |
| `maintenance_window_acknowledged` | `false` | Operator acknowledgement |
| `operator_authorize_patch_install` | `false` | Authorize install. Does not authorize reboot. |
| `operator_allow_pre_patch_reboot` | `false` | Authorize this phase's pre-patch reboot (inventory mode still applies) |
| `operator_allow_post_patch_reboot` | `false` | Authorize this phase's post-patch reboot (inventory mode still applies) |
| `patching_exception_hosts` | empty | Comma-separated inventory hostnames for this run |
| `patching_exception_reference` | empty | Required when hosts are listed |
| `snow_enabled` | `false` | Optional ServiceNow adapter |

Do not survey WSUS URLs, provider, patch mode, reboot policy
(`windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode`),
`patching_reboot_allowed`, `patching_exception_active`, or a host-targeting
variable.

## Launch

Every node requires an explicit AAP Limit. Typical values:

- `windows_canary`
- `windows_wave_1`

Leave all operator flags `false` for a dry run. Authorize install and each
reboot phase only when those actions are intended for the current window.
