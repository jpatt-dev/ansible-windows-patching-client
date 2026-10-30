# External inventory and ServiceNow contracts

This repository does not own AAP inventory objects or ServiceNow REST
implementation. Hosts, environment values, and wave membership stay in the
inventory workstream. Change lookup, approval, window, and CI-scope API calls
stay in the unpublished shared ServiceNow role.

## Inventory groups

Exact Limit names. No wildcards.

| Group | Role |
| --- | --- |
| `windows_hosts` | Playbook `hosts:` boundary. Never an approved Limit. |
| `windows_wave_1` … `windows_wave_20` | Approved patch waves. `N` is 1-20 with **no** zero-padding. |
| `windows_patch_exempt_temp` | AAP-managed temporary patch exemption. Ops playbooks own membership. |
| `windows_reboot_exempt_temp` | AAP-managed temporary reboot exemption. Ops playbooks own membership. |

Effective hosts are `windows_hosts` ∩ Limit. Inventory creates these groups.
This repository's `approved_patch_targets` must list the same exact names.
Adding `windows_wave_21` requires a Git allowlist change here and a matching
inventory group.

## Inventory variables

Required on host or group:

- `patching_reboot_allowed`
- `windows_pre_patch_reboot_mode` / `windows_post_patch_reboot_mode` (`if_required` or `always`)

Optional:

- `patching_exception_enabled` — Git inventory input for a **permanent patch** exemption
- `patching_exception_reference` — permanent Git patch exemption/request reference
- `patching_reboot_exception_enabled` — Git inventory input for a **permanent reboot** exemption
- `patching_reboot_exception_reference` — permanent Git reboot exemption/request reference
- `patching_exception_active` — resolved by this job (permanent Git **or** active
  temporary AAP group). Do not treat this as a Git write contract.
- `patch_temp_reference` / `patch_temp_expires_at` — required AAP hostvars when
  the host is in `windows_patch_exempt_temp` (real UTC calendar datetime,
  `YYYY-MM-DDTHH:MM:SSZ`)
- `reboot_temp_reference` / `reboot_temp_expires_at` — required AAP hostvars when
  the host is in `windows_reboot_exempt_temp` (real UTC calendar datetime,
  `YYYY-MM-DDTHH:MM:SSZ`)
- `patch_location`
- `patch_environment` (`LAB`, `IST`, `UAT`, or `PROD`) — reporting/correlation only.
  Job Templates bind one inventory each. The inventory repository must keep
  LAB/IST/UAT/PROD membership from overlapping.
- `sys_id` — CMDB configuration item sys_id synchronized onto the Windows
  host. The final JSON copies it to `snow_ci_sys_id`. Change preparation
  reads `hostvars[hostname].sys_id`. Pre-remediation validation uses that
  same value when `snow_ci_sys_id` is empty, and keeps an already set
  `snow_ci_sys_id`. Populate `sys_id` on every Windows host. This repository
  does not sync CMDB and does not add a second CI variable.
- WinRM connection facts from AAP inventory + Machine credential

### Build verification metadata

Build verification does not query ServiceNow. The normalized inventory
variables and the CSV contract are in `docs/build-verification-contract.md`.

This repository reads `inventory_hostname`, `fqdn`, `os`, `location`,
`environment`, and `sys_id` for both Windows and Linux build verification.
It does not sync those values from ServiceNow. The client inventory
workstream maps the CMDB columns onto these names. A missing value does not
stop live OS collection. Live OS names are not copied into those fields.
`os` is the CMDB release. The live OS version and current build stay
collected from the host.

Adding these variables must not rebuild `windows_wave_*`, exemption groups, or
`patch_temp_*` / `reboot_temp_*` hostvars. That overwrite risk is the blocking
dependency below.

High-latency sample: `inventory/group_vars/windows_remote_sites.yml` uses
operation/read timeouts of **600/720 seconds**, not a 60/90 baseline. Do not
change those values here to match a shorter recommendation.

Not inventory: Limit, operator authorize flags, maintenance-window survey
fields, `approved_patch_targets`, ServiceNow secrets. Permanent host exemptions
belong in the inventory Git repository. Temporary exemptions belong in AAP
groups managed by Ops playbooks. This Windows patching repository never
modifies AAP group membership.

`patching_reboot_allowed` is an independent reboot **permission**. A missing or
denied value is not an approved exemption.

## BLOCKING: ServiceNow inventory synchronization

ServiceNow CMDB is the source of truth for **server records**. AAP groups
(`windows_wave_1`–`20`, `windows_patch_exempt_temp`,
`windows_reboot_exempt_temp`) and AAP hostvars (`patch_temp_*`, `reboot_temp_*`)
are **not** CMDB attributes.

If the inventory workstream's ServiceNow synchronization rebuilds or overwrites
AAP groups or hostvars from CMDB, wave membership and temporary exemptions will
be removed or reset. That is a **blocking external inventory dependency**. Do
not implement CMDB sync, group persistence, or expiration cleanup in this
repository. The inventory/Ops workstream must persist AAP-managed groups and
metadata across CMDB sync.

`patch_wave_name` is set from the validated AAP Limit. Do not set it in
inventory.

## ServiceNow adapter interface

This repository's `servicenow_change` role is a thin adapter. It does not
implement REST. Work notes and attach wait for the unpublished shared role.
This repository does not name that collection or version.

**Identifiers**

| Field | Meaning |
| --- | --- |
| `snow_change_number` / `change_ticket_id` | Display number (`CHG…`) |
| `snow_change_sys_id` / legacy `snow_change_id` | sys_id |
| `snow_ci_sys_id` | Host CI sys_id for scope checks. Uses inventory `sys_id` when this value is empty |

**Shared role must eventually perform**

1. Lookup by display change number (and sys_id when provided)
2. Approval/state validation
3. Maintenance-window validation
4. Approved CI scope for **this host** (`snow_ci_sys_id`, from inventory `sys_id` when empty, plus Limit membership)

**This repository's confirmation fact** (not the unpublished collection schema):
the shared role, or a later mapping task, must set
`snow_change_validation_ok: true` when validation succeeded. Undefined,
false, or any other result is treated as **unknown** and fails closed.

**Policy (administrator Job Template extra-vars / RBAC, not survey)**

| Variable | Lab default | Production JT |
| --- | --- | --- |
| `snow_require_change_validation` | `false` | `true` |
| `snow_enabled` | `false` | `false`. Not the Full Patch reporting switch |
| `snow_shared_role` | empty | FQCN of the unpublished validation role. Not `servicenow_patching_change` |
| `snow_attach_report` | `false` | Retired for Full Patch. Use `snow_patching_attach_reports_enabled` |
| `snow_patching_update_cr_enabled` | `false` | `true` only after the ServiceNow credential and EE are ready |
| `snow_patching_attach_reports_enabled` | `false` | `true` only after the ServiceNow credential and EE are ready |
| `snow_patching_create_incidents_enabled` | `false` | `true` only with a caller, the credential, and the EE, and only for hosts that need follow-up |
| `snow_incident_caller` | empty | ServiceNow user id. Required when incident creation is enabled and at least one host needs follow-up |
| `snow_incident_assignment_group` | empty | Optional group name. Omitted when empty |
| `snow_incident_priority` | empty | Optional instance priority. Omitted when empty |
| `ask_variables_on_launch` | `false` | `false` |

Production eligible remediation fails closed when the policy is true and the
shared role is absent, fails, or does not confirm validation. Validation is
**not** required for a host with an effective exemption
(`patching_exception_active`) or when this job has not authorized install or
pre/post reboot. Remediating production hosts still fail closed without a
valid CR. Validation runs **per eligible host** (no `run_once`) so serial
batches and CI scope stay host-specific. Play 1 rescue still builds
`patch_final_result`; Play 2 still writes JSON/CSV/Markdown and optional SMTP,
then fails the job.

Lab Job Templates leave `snow_require_change_validation=false` so remediation
can run without ServiceNow until the shared role is delivered.

## Report consumption

Same-job Play 2 order: aggregate → write → optional change work note →
optional report attachment → optional follow-up incidents → SMTP → fail if
patching or an enabled ServiceNow operation failed.

Durable artifacts: AAP `set_stats` (`patch_final_result`,
`patch_workflow_report`, `patch_workflow_report_json`,
`patch_workflow_report_csv`).

Ephemeral EE files: `patch_report_files` under `/tmp/aap-patch-reports`
(JSON, Markdown, CSV). Attach must use those paths in **this** job. A later
workflow node will not see the files.

`snow_patching_attach_reports_enabled` passes `patch_report_files` to
`servicenow_patching_change` as `snow_report_files`. It does not regenerate
the reports. Do not add a second Job Template for attach. The Windows Full
Patch Job Template needs the existing ServiceNow credential and an Execution
Environment that provides `servicenow.itsm`. Leave both reporting switches
false until that credential and image are in place. Approval validation is
unchanged.

## AAP objects

This repository's `controller_cac/` declares:

- Project `Windows Patching` (SCM URL placeholder)
- Job Templates: Full Patch and Precheck for LAB, IST, UAT, and PROD.
  Prompt Limit only. `ask_inventory_on_launch: false`. `job_slice_count: 1`.
- Surveys loaded from `surveys/` (not duplicated in CaC)

Referenced, not created here:

- Inventory objects from the inventory repository (separate LAB, IST, UAT,
  and PROD inventories)
- Machine credential (WinRM) and optional ServiceNow credential env injection
- Approved Execution Environment `windows-patch-ee` (plus the shared
  ServiceNow role once published)
- Organization, instance groups

Operators cannot survey or extra-var-prompt `snow_require_change_validation`
or `approved_patch_targets`. Dispatcher apply is blocked until the client
verifies a Controller collection; see [controller_cac/README.md](../controller_cac/README.md).
