# Patch Reporting

The structured AAP/JSON result is the authoritative source of truth. CSV is the
concise operational report. Markdown is the human-readable summary.

Do not infer historical actions from final machine state. A compliant host does
not prove AAP patched it. A rebooted host does not prove AAP performed the
reboot.

SMTP/email is not implemented in this repository. Report files are suitable for
a later `report_email` consumer.

## Phase history

`playbooks/windows/full_patch.yml` preserves host-local phase history in the
same AAP job after each phase, before the next phase overwrites `patch_result`:

| Phase | Artifact key |
| --- | --- |
| Precheck | `patch_phase_precheck` |
| Pre-Patch Reboot | `patch_phase_reboot_pre` |
| Discovery | `patch_phase_discovery` |
| Apply | `patch_phase_apply` |
| Post-Patch Reboot | `patch_phase_reboot_post` |
| Postcheck | `patch_phase_postcheck` |

A host is treated as present for a phase only when that map exists and contains
the inventory hostname. Missing history is `not_available`.

Blocked, failed, or exempt hosts that skip later phases keep only the phases
that actually ran.

Standalone Precheck publishes per-host `patch_result` only. It does not build
the final aggregate report.

## Canonical per-host result

Full Patch builds `patch_final_result` after each host lifecycle, then
aggregates once in Play 2.

`patched` means this AAP execution installed one or more updates, proven by
Apply history (`patch_attempted` and `updates_installed > 0`). It is not inferred
from a healthy final machine.

`already_compliant` means no installation was needed / no applicable updates
remained. It requires a successful update search that returned zero applicable
updates. Missing, skipped, or failed search evidence is `unknown`, not
`already_compliant`. It is not a synonym of `success`.

Exemption uses inventory `patching_exception_enabled` and/or
`patching_exception_active`. It does not use a surveyed host list.

### Canonical `result` values

| Result | Meaning |
| --- | --- |
| `success` | This execution installed updates, postcheck evidence is present and healthy, no applicable updates remain, and no reboot is pending |
| `already_compliant` | No patch installation was needed |
| `exempt` | Inventory exemption prevented remediation |
| `blocked` | Precheck or safety policy prevented remediation |
| `failed` | A required patch/reboot/remediation operation failed |
| `degraded` | Updates were installed (`patched: true`) but postcheck is unhealthy, updates remain, or a reboot is still pending |
| `unknown` | A reliable execution outcome cannot be established |

`reboot_required` / `pending_reboot` are attributes, not results. Warnings stay
in details unless they meet a terminal result above.

Precedence: exempt → unreachable/failed → precheck blocked → patched without
postcheck unknown → patched+unhealthy/partial/pending-reboot degraded → patched
success (postcheck present, remaining=0, not pending) → no remaining updates
already_compliant → remaining updates not installed blocked → otherwise unknown.

`patched` stays true whenever Apply history proves installs, even when `result`
is `degraded`, `failed`, or `unknown`.

### Identity and location

| Field | Source |
| --- | --- |
| `hostname` | Windows CSName when collected; otherwise inventory hostname |
| `fqdn` | Windows DNS hostname + domain when collected |
| `os_release` | Windows OS caption (final/post-patch collection) |
| `os_build` | Windows build including UBR when collected (`BuildNumber.UBR`); `BuildNumber` only when UBR is unavailable |
| `location` | Optional inventory/group_vars `patch_location` |

`patch_location` is a generic label. Examples: `Lexington Datacenter`, `London`,
`vCenter-East`, `Azure-East-US`, `Physical`. If unset, the report uses an empty
string. This repository does not integrate with vCenter.

### Reason codes

| Code | Typical reason text |
| --- | --- |
| `PATCH_SUCCEEDED` | Updates installed successfully |
| `NO_APPLICABLE_UPDATES` | No applicable updates |
| `PATCH_EXEMPTION` | Approved exemption |
| `PRECHECK_BLOCKED` | Precheck blocked remediation |
| `INSTALL_NOT_AUTHORIZED` | Patch installation was not authorized |
| `PATCH_INSTALL_FAILED` | Update installation failed |
| `REBOOT_FAILED` | Pre-patch or post-patch reboot failed |
| `POSTCHECK_DEGRADED` | Postcheck detected unhealthy services |
| `PARTIAL_PATCH` | Updates remain after installation |
| `PENDING_REBOOT` | Updates installed; reboot still pending |
| `POSTCHECK_MISSING` | Postcheck evidence is missing |
| `UNREACHABLE` | Host unreachable |
| `UNKNOWN_RESULT` | Reliable execution outcome cannot be established |

### Required host examples

Exempt:

```
patched: false
exempt: true
result: exempt
```

Blocked:

```
patched: false
exempt: false
result: blocked
```

Already compliant:

```
patched: false
result: already_compliant
```

Degraded after a successful install:

```
patched: true
result: degraded
```

## Business CSV

Primary CSV columns:

1. Hostname
2. FQDN
3. OS Release
4. Post-Patch Kernel/Build
5. Location
6. Patched
7. Exempt
8. Result
9. Reason
10. Updates Installed
11. Updates Remaining
12. Change Ticket
13. Patch Wave

CSV fields are RFC 4180 quoted. Commas, double quotes, and empty strings are
preserved. Internal WSUS registry details, gate booleans, reboot-authorization
controls, and artifact internals stay in JSON/AAP output only.

## Aggregate summary

Primary counts:

- Systems Targeted / Total Systems
- Systems Patched (`patched: true`, including degraded hosts that were patched)
- Systems Not Patched

Not Patched breakdown:

- Exempt
- Already Compliant
- Blocked
- Failed
- Unknown

`Systems Patched + Systems Not Patched = Total Systems`.

Every host in the targeted play population appears in CSV, JSON, and Markdown.
If `patch_final_result` is missing, the aggregate inserts a minimal
`result: unknown` row (`UNKNOWN_RESULT` / "Final result was not produced for
this host"). Degraded hosts that were patched are counted under Systems Patched.

Structured JSON `status_counts` and the Markdown result-counts section expose
all canonical results: `success`, `already_compliant`, `exempt`, `blocked`,
`failed`, `degraded`, `unknown`. Those extra result counts are not added to
the primary CSV.

## JSON / AAP structured result

JSON remains richer than CSV. Useful audit fields include AAP job ID, Limit,
patch wave, change ticket, timestamps, `patch_attempted`, updates
installed/failed, reboot required/performed, precheck/postcheck, exemption
information, reason code, and WSUS/provider evidence.

AAP `set_stats` publishes:

- per-host `patch_final_result`
- aggregate `patch_workflow_report` / `patch_workflow_report_json`
- convenience `patch_workflow_report_csv`

Files under `/tmp/aap-patch-reports` inside the Execution Environment are
ephemeral convenience exports.
