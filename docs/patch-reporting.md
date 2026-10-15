# Patch Reporting

The structured AAP/JSON result is the authoritative source of truth. CSV is the
concise operational report. Markdown is the human-readable summary.

Do not infer historical actions from final machine state. A compliant host does
not prove AAP patched it. A rebooted host does not prove AAP performed the
reboot.

Optional SMTP delivery is provided by `roles/report_email/` and is disabled by
default. See [operations.md](operations.md).

Unreachable hosts remain in the aggregate report as `failed` / `UNREACHABLE`.
Missing host evidence is `not_available` (not a confirmed `false` or `0`).
JSON, CSV, Markdown, and optional SMTP are produced before the Full Patch job
fails for that result. `degraded`, `exempt`, and `blocked` are not automatic
job failures.

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

`already_compliant` means no installation was needed, a successful update
search returned zero applicable updates, and required final checks are
satisfactory (no pending reboot, no unhealthy postcheck). Missing, skipped,
failed, or unverified search evidence is `unknown`, not `already_compliant`.
`found_update_count` alone is not proof of a successful search. Unknown
installation counts stay `not_available` and are never reported as `0`. It is
not a synonym of `success`.

Exemption uses Git `patching_exception_enabled` /
`patching_reboot_exception_enabled` and AAP groups
`windows_patch_exempt_temp` / `windows_reboot_exempt_temp`. The resolved
`patching_exception_active` is true when any active patch or reboot exemption
applies. Combined JSON fields stay for compatibility: `patching_exception_kind`
(`patch`, `reboot`, `patch_and_reboot`, `none`), `patching_exception_source`
(`inventory` or `aap_group`), `patching_exception_status` (`active`,
`expired`, `invalid`, `none`), reference, and temporary expiration.

Independent patch and reboot snapshot fields are authoritative for historical
audit reporting:

- `patching_exception_patch_source` / `patching_exception_patch_reference` /
  `patching_exception_patch_expires_at`
- `patching_reboot_exception_source` / `patching_reboot_exception_reference` /
  `patching_reboot_exception_expires_at`

A permanent Git reboot exemption plus a temporary AAP patch exemption therefore
records both sources. Combined `patching_exception_source`,
`patching_exception_reference`, and `patching_exception_expires_at` remain for
compatibility and may summarize multiple active exemption sources. Combined
`patching_exception_source` remains `inventory` when any Git exemption applies.
CSV columns and the `exempt` result vocabulary are unchanged.

### Canonical `result` values

| Result | Meaning |
| --- | --- |
| `success` | This execution installed updates, postcheck evidence is present and healthy, no applicable updates remain, and no reboot is pending |
| `already_compliant` | No applicable updates remain and required final checks are satisfactory |
| `exempt` | Permanent Git or active temporary AAP exemption prevented remediation |
| `blocked` | Precheck or safety policy prevented remediation |
| `failed` | A required patch/reboot/remediation operation failed |
| `degraded` | Follow-up is required. May occur when updates were installed (`patched: true`) or when no updates were installed (`patched: false`), including an unresolved pending reboot |
| `unknown` | A reliable execution outcome cannot be established |

`reboot_required` / `pending_reboot` are attributes, not results. Warnings stay
in details unless they meet a terminal result above.

Precedence: exempt → unreachable/failed → precheck blocked → patched without
postcheck unknown → unhealthy postcheck / partial install / pending reboot
degraded → patched success (postcheck present, remaining=0, not pending) →
already_compliant only when remaining=0 and no reboot/health follow-up remains
→ remaining updates not installed blocked → otherwise unknown.

`patched` stays true whenever Apply history proves installs, even when `result`
is `degraded`, `failed`, or `unknown`.

### Identity and location

| Field | Source |
| --- | --- |
| `hostname` | Windows CSName when collected; otherwise inventory hostname |
| `fqdn` | Windows DNS hostname + domain when collected |
| `os_release` | Windows OS caption (final/post-patch collection) |
| `os_version` | Existing `windows_os_version` fact (Windows `Version`, for example `10.0.17763`) |
| `os_build` | Post-patch / final Windows build (`BuildNumber.UBR` when collected) |
| `os_build_pre` | Precheck snapshot of the same build field; `not_available` if precheck did not collect it |
| `location` | Optional inventory/group_vars `patch_location` |
| `snow_ci_sys_id` | Optional inventory ServiceNow CMDB CI sys_id (stable host join key) |
| `patch_environment` | Optional inventory `LAB` / `IST` / `UAT` / `PROD` |
| `platform` | `windows` on this report |
| `updates_installed_kbs` / `updates_failed_kbs` | Compact KB ids from `win_updates.updates`. `[]` means the module returned no matching KBs. `not_available` means install evidence was not produced. |

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
| `PENDING_REBOOT` | A reboot is pending and requires follow-up |
| `POSTCHECK_MISSING` | Postcheck evidence is missing |
| `UNREACHABLE` | Host unreachable. Causes the Full Patch AAP job to fail after reporting |
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
pending_reboot: false
result: already_compliant
```

Degraded after a successful install:

```
patched: true
result: degraded
```

Degraded with no install this job (pending reboot):

```
patched: false
pending_reboot: true
result: degraded
reason_code: PENDING_REBOOT
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
14. Reason Code
15. Pending Reboot
16. Manual Follow-up Required

CSV fields are RFC 4180 quoted. Commas, double quotes, and empty strings are
preserved. `Reason Code`, `Pending Reboot`, and `Manual Follow-up Required`
come from the host result record. Unknown reboot state is `not_available`,
not `False`. Internal WSUS registry details, gate booleans,
reboot-authorization controls, and artifact internals stay in JSON/AAP output
only.

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
- Degraded (only hosts with `patched: false`)
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

`patch_workflow_report` is one record per Full Patch job that reaches Play 2.
`hosts[]` is one record per targeted host. Schema stays `3`. Additive envelope
fields: `report_source` (`windows_full_patch`), `platform` (`windows`),
`patch_environment`, `patch_environments`, `git_revision`. Do not rename
existing fields.

Run-level `patch_environment` is the unique host `patch_environment` set, not
the first host. One value is copied as-is. An empty set is `""`. Mixed values
set `patch_environment: inconsistent` and list the distinct values in
`patch_environments`.

`git_revision` is the existing `GIT_COMMIT` / `CI_COMMIT_SHA` value already
recorded on host results (`not_available` when unset). Do not invent a
revision. Do not duplicate AAP job status, timestamps, duration, inventory
identity, Job Template, or launched-by; the ingest collector reads those from
the job API.

Files under `/tmp/aap-patch-reports` inside the Execution Environment are
ephemeral convenience exports. Same-job Play 2 attach uses `patch_report_files`
from that directory. A later AAP workflow node will not see those paths; keep
attach in this job. The unpublished shared ServiceNow role should consume
`patch_workflow_report` / `set_stats` plus those same-job paths. `patch_wave`
in the report is the validated AAP Limit.

## Historical reporting (Power BI) — outside this repository

This repository does not implement Power BI REST, a historical database, or
CMDB synchronization. Ingest `patch_workflow_report` from the AAP job API.

**Retrieve**

`GET /api/v2/jobs/{id}/` → `artifacts.patch_workflow_report`

Ingest **Full Patch** jobs. Standalone Precheck does not build the aggregate
report.

**Stamp from the AAP job API at ingest time (do not duplicate in playbooks)**

| API field | Use |
| --- | --- |
| `status` | `successful` / `failed` / `canceled` |
| `started` / `finished` / `elapsed` | Job timestamps and duration |
| `inventory` | Inventory name/id. Do not substitute playbook first-host environment |
| `job_template` | Template name (LAB/IST/UAT/PROD) |
| `limit` | Wave Limit |
| `summary_fields.created_by` | Operator |

**Retention**

`set_stats` exists only while AAP retains the job. Copy the artifact plus API
fields into an external store **independent of AAP job retention**. Power BI
reads that store.

**Failed / cancelled / zero-host jobs**

- Failed jobs that reach Play 2 still emit JSON, then fail. Keep host `result`
  values; join API `status=failed`.
- Cancelled before Play 2: no JSON. Job-level API row only (`hosts=[]`).
- Empty Limit (`windows_hosts` ∩ wave = 0): no play tasks and no `set_stats`.
  Represent from the AAP job. Do not treat a skipped play as a successful wave.

**CMDB reconciliation**

Inventory must populate `snow_ci_sys_id` and `patch_environment` on Windows
hosts. Power BI left-joins the ServiceNow Windows CI list to historical host
rows:

| Question | Join |
| --- | --- |
| Never targeted | CMDB CIs in env minus any stored host row for that `snow_ci_sys_id` |
| Targeted, never patched | Host rows with `patched=false` and `result` not `success` or `already_compliant` |
| Exempt / blocked / failed | Existing `result` plus exemption snapshot as of that execution |
| Missing CI id | Inventory gap; hostname/FQDN fallback is unstable |

Do not sync CMDB from this playbook. Linux/database reports should reuse the
same job/host envelope with a different `report_source` / `platform`.
