# Operations

## Normal Patch Cycle

1. **Precheck** — Read-only. Resolves WSUS assignment, inspects health, searches
   updates, and records pending reboot. Fails the job on critical conditions.
2. **Pre-Patch Reboot If Required** — Reboots when this phase's inventory reboot
   mode and every reboot control pass. `if_required` (default) reboots only when
   Windows reports pending reboot. `always` reboots when those safety gates pass
   even if pending reboot is false.
3. **Discovery** — Search-only update discovery against WSUS. Never installs.
4. **Apply** — Installs only when `operator_authorize_patch_install` is true and
   in-job readiness gates pass. `win_updates` always uses `reboot: false`.
5. **Post-Patch Reboot If Required** — Same reboot rules as the pre-patch phase
   (`if_required` or `always`), with its own operator flag.
6. **Postcheck** — Read-only validation after apply/reboot.
7. **Final Patch Report** — Consumes upstream phase artifacts and runs fresh
   read-only end-state checks. See [patch-reporting.md](patch-reporting.md).

Configure WSUS is run separately when registry assignment must be written.

## Variable Ownership

Controller objects that supply Inventory, Limit, Survey, and Credential values
are defined in the separate Controller configuration-as-code repository.

| Layer | Owns |
| --- | --- |
| Git | Playbooks, roles, safety policy, approved target list |
| Inventory | Hosts, groups, WSUS URLs/mode, `patching_reboot_allowed`, reboot mode |
| Limit | Patch wave / launch population |
| Survey | Per-run authorization, maintenance window, temporary exceptions |
| Credential | Windows and external-service secrets |

## Targeting

All Windows patch jobs require an explicit AAP Limit. Blank Limit, `all`, and
`*` fail.

`windows_hosts` is only the playbook `hosts:` boundary.

Apply and reboot jobs also require the Limit to be in `approved_patch_targets`
(`windows_canary`, `windows_wave_1`). `windows_hosts` is not an approved wave.

## WSUS Assignment

Provider is inventory-derived. Assignment groups match `windows_wsus_*`.

| Inventory membership | Result |
| --- | --- |
| Exactly one `windows_wsus_*` group | Provider `wsus` |
| No assignment group | Provider `unknown`; remediation blocked |
| More than one assignment group | Job fails closed |

URLs come from assignment group_vars (`windows_wsus_server_url`,
`windows_wsus_status_url`). Operators do not choose a WSUS server in a survey.

Configure WSUS can write the client registry when inventory mode is `enforce`.
Recurring patch jobs (`validate` only) compare registry to inventory and do not
repair drift.

Compared values:

- `WUServer`
- `WUStatusServer`
- `UseWUServer` (must be `1`)

Precheck fails when a WSUS-assigned host is not `matched`. Remediating Apply
fails closed unless `windows_wsus_config_match` is true.

## Patch Authorization

`operator_authorize_patch_install` controls whether Apply can remediate.

When false, Apply stays non-installing. When true, Apply still fails unless
WSUS match, approved Limit, supported OS policy, maintenance window, and no
pending reboot also pass. Install authorization does not authorize reboot.

## Reboots

A reboot runs only when all of the following are true:

- This phase's inventory reboot mode is `always`, or Windows reports a pending
  reboot (`if_required`, default)
- The operator authorized that phase (`operator_allow_pre_patch_reboot` or
  `operator_allow_post_patch_reboot`)
- Inventory `patching_reboot_allowed` is true
- The host is not under a patch-cycle exception
- The maintenance window is acknowledged and currently open

`windows_pre_patch_reboot_mode` and `windows_post_patch_reboot_mode` are
inventory policy (`if_required` or `always`). They are not survey controls.

Inventory policy wins over survey authorization. A survey cannot normally
override `patching_reboot_allowed: false`.

If reboot is required but inventory denies it, the reboot job skips the reboot,
sets `manual_followup_required`, and does not fail solely for that reason.

## Temporary Patch Exceptions

Supplied per patch cycle through the workflow survey:

- `patching_exception_hosts` — comma-separated inventory hostnames
- `patching_exception_reference` — required when hosts are listed

Each listed host must be in the current Limit. The excluded host is still
inspected and reported. Remediation and reboot are skipped
(`patch_status` / `final_status` = `excluded`).

Exceptions do not persist to the next launch. Do not remove excepted hosts from
inventory groups.

## Maintenance Window

Required for Apply (when installing) and for actual reboot operations:

- `maintenance_window_start` / `maintenance_window_end` — UTC ISO-8601
  `YYYY-MM-DDTHH:MM:SSZ`
- `maintenance_window_acknowledged` — must be true
- Current UTC must fall inside the window

Precheck reports window status and does not enforce it.

## Failure Behavior

| Condition | Result |
| --- | --- |
| Missing, blank, `all`, or `*` Limit | Job fails |
| Apply/reboot Limit not in `approved_patch_targets` | Job fails |
| Multiple `windows_wsus_*` groups | Job fails closed |
| No `windows_wsus_*` group | Provider `unknown`; Apply cannot remediate. Precheck fails if install is authorized. |
| WSUS registry mismatch | Precheck fails. Remediating Apply fails. Run Configure WSUS (`enforce`) to repair. |
| Pending reboot before remediating Apply | Apply fails closed. It does not reboot. |
| Invalid or closed maintenance window | Remediating Apply and actual reboot operations fail |
| Invalid `windows_*_patch_reboot_mode` | Reboot job fails closed |
| `patching_reboot_allowed: false` | Reboot skipped; `manual_followup_required`. Job does not fail solely for this. |
| Temporary exception | Host reported as `excluded`; install and reboot skipped |
| Client PowerShell precheck failed (when enabled) | Precheck fails. Remediating Apply fails. |
| Unsupported OS policy | Remediating Apply fails |

## PowerShell Client Precheck

Disabled by default (`windows_powershell_precheck_enabled: false`).

`client_precheck.ps1` is the integration point. Replace it with the approved
client script before enabling.

When enabled, malformed output, execution failure, `critical_failed=true`, or
`overall_health=failed` blocks remediation. Minimum required fields:

- `critical_failed`
- `overall_health`

## ServiceNow

Integration is optional. `snow_enabled` defaults to `false`. The ServiceNow
role is an adapter boundary. The client-specific ServiceNow contract is
implemented separately.
