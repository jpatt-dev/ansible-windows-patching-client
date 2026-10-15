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
| `windows_canary` | Approved canary Limit |
| `windows_wave_1` … `windows_wave_20` | Approved production waves. `N` is 1-20 with **no** zero-padding. |
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
- `snow_ci_sys_id` — CMDB CI sys_id for approved CI scope **and** the stable
  Power BI/historical join key. Populate it on every Windows host. The final
  JSON emits it; this repository does not sync CMDB.
- WinRM connection facts from AAP inventory + Machine credential

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
(`windows_canary`, `windows_wave_1`–`20`, `windows_patch_exempt_temp`,
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
implement REST. EXAMPLE `uri` tasks remain disabled
(`snow_example_integrations_enabled: false`) until the shared role is
published. This repository does not name that collection or version.

**Identifiers**

| Field | Meaning |
| --- | --- |
| `snow_change_number` / `change_ticket_id` | Display number (`CHG…`) |
| `snow_change_sys_id` / legacy `snow_change_id` | sys_id |
| `snow_ci_sys_id` | Host CI sys_id for scope checks |

**Shared role must eventually perform**

1. Lookup by display change number (and sys_id when provided)
2. Approval/state validation
3. Maintenance-window validation
4. Approved CI scope for **this host** (`snow_ci_sys_id` + Limit membership)

**This repository's confirmation fact** (not the unpublished collection schema):
the shared role, or a later mapping task, must set
`snow_change_validation_ok: true` when validation succeeded. Undefined,
false, or any other result is treated as **unknown** and fails closed.

**Policy (administrator Job Template extra-vars / RBAC, not survey)**

| Variable | Lab default | Production JT |
| --- | --- | --- |
| `snow_require_change_validation` | `false` | `true` |
| `snow_enabled` | `false` | `true` when work notes/attach should run |
| `snow_shared_role` | empty | FQCN after the shared role is in the EE |
| `snow_attach_report` | `false` | `true` when attaching same-job files |
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

Same-job Play 2 order is unchanged: aggregate → write → SMTP → attach →
fail-if-failed.

Durable artifacts: AAP `set_stats` (`patch_final_result`,
`patch_workflow_report`, `patch_workflow_report_json`,
`patch_workflow_report_csv`).

Ephemeral EE files: `patch_report_files` under `/tmp/aap-patch-reports`
(JSON, Markdown, CSV). Attach must use those paths in **this** job. A later
workflow node will not see the files.

When the shared role is published, `snow_phase=attach_report` should consume
`snow_report_path` / `patch_report_files` and `patch_workflow_report` from
this job. Do not add a second Job Template for attach.

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
