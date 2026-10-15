# AAP Controller Setup

This repository owns its AAP **Project**, **Job Templates**, and **survey
specs**. Declarative objects live in [controller_cac/](../controller_cac/).
Survey questions stay in `surveys/` and are not copied into CaC YAML.

Organizations, inventories, credentials, and Execution Environments are
referenced by name. They are not created here.

Controller API dispatch is **blocked** until the client verifies an AAP 2.7
Controller collection. See [controller_cac/README.md](../controller_cac/README.md).

## Project

Point an AAP Project at this repository. Use the production SCM URL and
credential owned by the client. Enable **Update Revision on Launch**.

Assign the approved Windows patch Execution Environment to every Windows job
template. Runtime collections come from that EE, not from a project
`collections/` directory.

## Inventory

Create **separate** AAP Inventory objects for LAB, IST, UAT, and PROD and
attach each Job Template to exactly one of them (`ask_inventory_on_launch:
false`). Inside each inventory, define groups:

| Group | Role |
| --- | --- |
| `windows_hosts` | Playbook `hosts:` boundary. Not a patch wave. |
| `windows_canary` | Approved Limit target |
| `windows_wave_1` … `windows_wave_20` | Approved Limit targets (`N` unpadded) |
| `windows_patch_exempt_temp` | Temporary patch exemption (Ops-managed) |
| `windows_reboot_exempt_temp` | Temporary reboot exemption (Ops-managed) |

See [external-contracts.md](external-contracts.md) for the inventory variable
contract. This repository does not ship host inventories.

AAP **Limit** selects the hosts that actually run. Effective hosts are
`windows_hosts` ∩ Limit.

Do not put the Inventory object name in Limit. Do not put a group name in the
job template Inventory field. Do not survey Limit or wave targeting.

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

Permanent exemptions belong in the Git inventory repository
(`patching_exception_enabled` / `patching_exception_reference` and
`patching_reboot_exception_enabled` / `patching_reboot_exception_reference`).
Temporary exemptions are AAP group membership plus expiration metadata, not
survey fields. Full Patch never modifies those groups.

High-latency / WAN WinRM hosts should use inventory group_vars, not a global
`ansible.cfg` change. See `inventory/group_vars/windows_remote_sites.yml` for
`ansible_winrm_operation_timeout_sec`, `ansible_winrm_read_timeout_sec`, and
`ansible_winrm_connection_timeout`. The sample uses **600/720** second
operation/read timeouts, not a 60/90 baseline; do not silently lower them.
Apply that group only to remote sites.

## Credentials

Attach a Windows **Machine** credential for WinRM. Attach a Source Control
credential on the Project. Secrets stay in AAP Credentials, not in git.

Optional SMTP report email uses `report_email_*` extra variables on the Full
Patch job template (not survey fields). Inject SMTP username/password from a
custom AAP Credential or credential environment
(`REPORT_EMAIL_SMTP_USERNAME` / `REPORT_EMAIL_SMTP_PASSWORD`). Rebuild the
Windows patch Execution Environment after adding `community.general`.

WinRM authentication, including Kerberos, is environment-specific and is
configured during production implementation.

## Job Templates

Declared in `controller_cac/vars/job_templates.yml`. **Prompt on launch** for
Limit only (`ask_limit_on_launch: true`). Extra-var prompting stays off
(`ask_variables_on_launch: false`). `job_slice_count` is `1`.

| Job Template | Playbook | Survey file | Inventory |
| --- | --- | --- | --- |
| Windows Full Patch LAB | `playbooks/windows/full_patch.yml` | `surveys/windows_patch_workflow_survey.yml` | LAB inventory object |
| Windows Full Patch IST | `playbooks/windows/full_patch.yml` | `surveys/windows_patch_workflow_survey.yml` | IST inventory object |
| Windows Full Patch UAT | `playbooks/windows/full_patch.yml` | `surveys/windows_patch_workflow_survey.yml` | UAT inventory object |
| Windows Full Patch PROD | `playbooks/windows/full_patch.yml` | `surveys/windows_patch_workflow_survey.yml` | PROD inventory object |
| Windows Precheck LAB | `playbooks/windows/precheck.yml` | `surveys/windows_precheck_survey.yml` | LAB inventory object |
| Windows Precheck IST | `playbooks/windows/precheck.yml` | `surveys/windows_precheck_survey.yml` | IST inventory object |
| Windows Precheck UAT | `playbooks/windows/precheck.yml` | `surveys/windows_precheck_survey.yml` | UAT inventory object |
| Windows Precheck PROD | `playbooks/windows/precheck.yml` | `surveys/windows_precheck_survey.yml` | PROD inventory object |

LAB and IST extra-vars: `snow_require_change_validation=false`,
`patch_require_maintenance_window=false`. UAT and PROD Full Patch extra-vars:
`snow_require_change_validation=true`,
`patch_require_maintenance_window=true`, `snow_shared_role` empty until the
shared role is in the EE (remediating hosts fail closed). Precheck stays
read-only (`snow_require_change_validation=false`) and is bound to the same
environment inventory (`ask_inventory_on_launch: false`).

DEV is a reserved label with no Job Templates. Do not create one Job Template
per wave. Operators set Limit to `windows_canary` or `windows_wave_1` …
`windows_wave_20`.

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

Do not survey WSUS URLs, provider, patch mode, reboot policy
(`windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode`),
`patching_reboot_allowed`, `patching_exception_enabled`,
`patching_reboot_exception_enabled`, `patching_exception_active`,
`patch_require_maintenance_window`, `snow_enabled`,
`snow_require_change_validation`, `approved_patch_targets`, Limit/wave
targeting, or temporary exemption hostnames. Ops playbooks manage AAP
exemption groups.

Set `snow_require_change_validation=true` on production Full Patch Job
Template extra-vars (RBAC, not survey). Leave it `false` on lab templates
until the shared ServiceNow role is in the Execution Environment.

Set `patch_require_maintenance_window` on the Job Template or schedule extra
variables (default `true`). For recurring AAP schedules, set it `false` so
the schedule controls timing and survey start/end/acknowledgement are not
required. Other safety controls remain in force.

Standalone **Windows - Precheck** uses a smaller read-only survey
(`change_ticket_id`). It does not authorize install or reboot.

## Launch

Every job requires an explicit AAP Limit. Typical values:

- `windows_canary`
- `windows_wave_1` through `windows_wave_20`

Leave all operator flags `false` for a dry run. Authorize install and each
reboot only when those actions are intended for the current window.

## Job Template timeout and `patch_serial`

Full Patch Play 1 uses `serial: "{{ patch_serial | default(1) }}"`. Wall-clock
time is approximately:

`ceil(host_count / patch_serial) * per_host_worst_case + reporting_buffer`

`per_host_worst_case` includes precheck/discovery search retries, Apply
(`windows_apply_timeout`, default 7200 seconds), and up to two reboot waits
(`windows_reboot_timeout`, default 3600 seconds each) when those phases are
authorized.

Reducing `patch_serial` **increases** processing time because fewer hosts run
concurrently. Do not lower `patch_serial` to fit a maintenance window. Fit the
window by reducing Limit host count or by increasing **approved** concurrency
(`patch_serial` / `forks`) after change approval.

When `patch_require_maintenance_window` is true, Apply and reboot still fail
closed if the window expires before those tasks run. Size the Limit and
approved concurrency so the job can finish while the window is open.
`controller_cac` sets Job Template `timeout` (placeholder seconds in
`vars/settings.yml`); size it above the formula per wave host count from the
inventory repository.

An approved Limit with zero hosts skips the Full Patch play entirely. Empty
waves are an inventory/Controller acceptance failure, not an in-play assert.
See [controller_cac/README.md](../controller_cac/README.md).
