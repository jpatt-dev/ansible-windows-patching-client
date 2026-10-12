# Operations

## Normal Patch Cycle

Primary operational playbook: `playbooks/windows/full_patch.yml` runs the
complete lifecycle in one AAP Job Template.

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

1. **Precheck** — Read-only. Validates the host WSUS configuration, inspects health, searches
   updates, and records pending reboot. Inside Full Patch this does not fail the
   job on blocked/failed status; those hosts are marked ineligible.
2. **Eligibility** — `passed` and `warning` continue. `blocked`, `failed`,
   missing, and unknown skip remediation and remain available for reporting.
3. **Pre-Reboot** — Reboots when this phase's inventory reboot mode and every
   reboot control pass. `if_required` (default) reboots only when Windows reports
   pending reboot. `always` reboots when those safety gates pass even if pending
   reboot is false.
4. **Discovery** — Search-only update discovery against WSUS. Never installs.
5. **Apply** — Installs only when `operator_authorize_patch_install` is true and
   in-job readiness gates pass. `win_updates` always uses `reboot: false`.
6. **Post-Reboot** — Same reboot rules as the pre-patch phase (`if_required` or
   `always`), with its own operator flag.
7. **Postcheck** — Read-only validation after apply/reboot.
8. **Per-host final report / ITSM update** — Builds `patch_final_result` from
   preserved phase history and current host facts. `patched` is true only when
   Apply history proves this job installed updates. Updates ServiceNow work notes
   when `snow_enabled=true`.
9. **Final aggregate report** — One Limit-wide JSON/CSV/Markdown and AAP
   `set_stats` artifact after every host in the Limit has finished Play 1.
   CSV is the concise operational report; JSON is the richer authoritative
   artifact. See [patch-reporting.md](patch-reporting.md).

Standalone troubleshooting/readiness: `playbooks/windows/precheck.yml`. That
playbook is fail-closed and never remediates.

WSUS client configuration is owned by the client's provisioning/post-provisioning
process. The Windows patching repository validates the effective WSUS
configuration before patch discovery or remediation but does not assign or
configure WSUS servers.

## Variable Ownership

Controller objects that supply Inventory, Limit, Survey, and Credential values
are defined in the separate Controller configuration-as-code repository.

| Layer | Owns |
| --- | --- |
| Git | Playbooks, roles, safety policy, approved target list |
| Inventory | Hosts, groups, `patching_reboot_allowed`, reboot mode, optional `patch_location` |
| Limit | Patch wave / launch population |
| Survey | Per-run authorization, maintenance window, temporary exceptions |
| Credential | Windows and external-service secrets |

## Targeting

All Windows patch jobs require an explicit AAP Limit. Blank Limit, `all`, and
`*` fail.

`windows_hosts` is only the playbook `hosts:` boundary.

Full Patch also requires the Limit to be in `approved_patch_targets`
(`windows_canary`, `windows_wave_1`). `windows_hosts` is not an approved wave.
Standalone Precheck does not enforce that approved-target list.

## WSUS Validation

WSUS client configuration is owned by the client's provisioning/post-provisioning
process. This repository only reads the host registry and validates it.

A host is `valid` when:

- `WUServer` exists and is non-empty
- `WUStatusServer` exists and is non-empty
- `UseWUServer` is `1`
- both values are structurally valid `http://` or `https://` URLs
- `WUServer` and `WUStatusServer` match (case-insensitive)

| Validation status | Result |
| --- | --- |
| `valid` | Provider `wsus`; `windows_wsus_configured` is true |
| `missing` | Required registry values absent; `windows_wsus_configured` is false; provider `unknown` |
| `invalid` | Values present but not a usable WSUS client config; `windows_wsus_configured` is true; provider `unknown` |

Operators do not choose a WSUS server in a survey. Leftover inventory
`windows_wsus_*` groups or URL group_vars are unused and do not affect
provider or gates.

Standalone Precheck fails when validation is not `valid`. Remediating Apply
fails closed unless the host already has a valid WSUS configuration. This
repository does not write WSUS registry values.

## Patch Authorization

`operator_authorize_patch_install` controls whether Apply can remediate.

When false, Apply stays non-installing. When true, Apply still fails unless
WSUS validation is `valid`, approved Limit, supported OS policy, maintenance
window, and no pending reboot also pass. Install authorization does not
authorize reboot.

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

If reboot is required but inventory denies it, the reboot phase skips the reboot,
sets `manual_followup_required`, and does not fail solely for that reason.

## Temporary Patch Exceptions

Exemption is inventory-derived. Set per host or group:

- `patching_exception_enabled` — true when the host is exempt
- `patching_exception_active` — equivalent inventory truth used by reporting and remediation gates

The exempt host is still inspected and reported. Remediation and reboot are skipped
(`patched: false`, `exempt: true`, `result: exempt`).

Do not use a surveyed host list for Full Patch reporting.

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
| Full Patch Limit not in `approved_patch_targets` | Job fails |
| Missing or invalid WSUS client configuration | Standalone Precheck fails. Full Patch marks the host ineligible and continues reporting. Remediating Apply fails. Repair WSUS in provisioning; this repository does not configure it. |
| Pending reboot before remediating Apply | Apply fails closed. It does not reboot. |
| Invalid or closed maintenance window | Remediating Apply and actual reboot operations fail |
| Invalid `windows_*_patch_reboot_mode` | Reboot phase fails closed |
| `patching_reboot_allowed: false` | Reboot skipped; `manual_followup_required`. Job does not fail solely for this. |
| Temporary exception | Host reported as `exempt`; `patched: false`; install and reboot skipped |
| Client PowerShell precheck failed (when enabled) | Standalone Precheck fails. Full Patch marks the host ineligible. Remediating Apply fails. |
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

When enabled, Full Patch validates the change once before eligible remediation
and updates work notes after each host's final result. It does not emit
per-phase ServiceNow chatter.
