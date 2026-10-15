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
   in-job readiness gates pass. `win_updates` always uses `reboot: false`. The
   install task uses ansible-core `timeout` (`windows_apply_timeout`, default
   7200 seconds) on Linux AAP controllers (ansible-core 2.16 TaskExecutor,
   SIGALRM). There is no automatic Apply retry and no async/poll. If the
   module does not return `installed_update_count`, the report keeps
   `not_available` rather than `0`.
6. **Post-Reboot** — Same reboot rules as the pre-patch phase (`if_required` or
   `always`), with its own operator flag.
7. **Postcheck** — Read-only validation after apply/reboot.
8. **Per-host final report / ITSM update** — Builds `patch_final_result` from
   preserved phase history and current host facts. `patched` is true only when
   Apply history proves this job installed updates. `already_compliant` requires
   no applicable updates and satisfactory final checks. `degraded` may occur
   when no updates were installed if follow-up remains, including
   `PENDING_REBOOT`. Updates ServiceNow work notes when `snow_enabled=true`.
9. **Final aggregate report** — One Limit-wide JSON/CSV/Markdown and AAP
   `set_stats` artifact after every host in the Limit has finished Play 1.
   CSV is the concise operational report and includes Reason Code, Pending
   Reboot, and Manual Follow-up Required. JSON is the richer authoritative
   artifact. Optional SMTP runs next. If any host result is `failed`, including
   `UNREACHABLE`, the AAP job fails after those reports. See
   [patch-reporting.md](patch-reporting.md).

Standalone troubleshooting/readiness: `playbooks/windows/precheck.yml`. That
playbook is fail-closed and never remediates.

WSUS client configuration is owned by the client's provisioning/post-provisioning
process. The Windows patching repository validates the effective WSUS
configuration before patch discovery or remediation but does not assign or
configure WSUS servers.

## Variable Ownership

This repository owns the AAP Project and Job Templates in `controller_cac/`.
Inventories and credentials remain external references.

| Layer | Owns |
| --- | --- |
| Git | Playbooks, roles, safety policy, approved target list, application CaC |
| Inventory | Hosts, groups, reboot policy, exceptions, optional `patch_location`, optional `snow_ci_sys_id` / `patch_environment`, WinRM |
| Limit | Patch wave / launch population (`patch_wave_name`) |
| Survey | Per-run authorization, maintenance window, change display number, temporary exemptions |
| Job Template extra-vars / RBAC | `snow_require_change_validation`, `snow_enabled`, `snow_shared_role`, `patch_require_maintenance_window` |
| Credential | Windows and external-service secrets |

## Targeting

All Windows patch jobs require an explicit AAP Limit. Blank Limit, `all`, and
`*` fail.

`windows_hosts` is only the playbook `hosts:` boundary.

Full Patch also requires the Limit to be in `approved_patch_targets`
(`windows_canary`, `windows_wave_1` … `windows_wave_20`, exact names).
`windows_hosts` is not an approved wave. Standalone Precheck does not enforce
that approved-target list. `patch_wave_name` is set from that Limit.

An approved Limit that intersects **zero** hosts never runs play tasks
(including fail-closed asserts). Empty waves must be rejected by inventory or
Controller acceptance, not by assertions inside Full Patch. See
[controller_cac/README.md](../controller_cac/README.md).

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
WSUS validation is `valid`, approved Limit, supported OS policy, no pending
reboot, and — when `patch_require_maintenance_window` is true — an open
acknowledged maintenance window also pass. Install authorization does not
authorize reboot.

## Reboots

A reboot runs only when all of the following are true:

- This phase's inventory reboot mode is `always`, or Windows reports a pending
  reboot (`if_required`, default)
- The operator authorized that phase (`operator_allow_pre_patch_reboot` or
  `operator_allow_post_patch_reboot`)
- Inventory `patching_reboot_allowed` is true
- The host is not under a patch-cycle exception
- When `patch_require_maintenance_window` is true, the maintenance window is
  acknowledged and currently open

`windows_pre_patch_reboot_mode` and `windows_post_patch_reboot_mode` are
inventory policy (`if_required` or `always`). They are not survey controls.

Inventory policy wins over survey authorization. A survey cannot normally
override `patching_reboot_allowed: false`.

If reboot is required but inventory denies it, the reboot phase skips the reboot,
sets `manual_followup_required`, and does not fail solely for that reason.

## Patch and reboot exemptions

Permanent exemptions live in the Git inventory repository. Set per host or group:

- `patching_exception_enabled` / `patching_exception_reference` — permanent patch exemption
- `patching_reboot_exception_enabled` / `patching_reboot_exception_reference` — permanent reboot exemption

Temporary exemptions are AAP group membership, managed by separate Ops
playbooks. Full Patch only consumes them:

- `windows_patch_exempt_temp` with `patch_temp_reference` and `patch_temp_expires_at`
- `windows_reboot_exempt_temp` with `reboot_temp_reference` and `reboot_temp_expires_at`

Timestamps must be real UTC calendar datetimes (`YYYY-MM-DDTHH:MM:SSZ`).
Matching the ISO-8601 Z shape is not enough; impossible dates such as
February 30, 24:00, or February 29 on a non-leap year fail closed before
remediation. A correctly expired membership no longer grants exemption; the
job reports stale membership and does not modify AAP groups.

`patching_exception_active` is the resolved result (permanent or active
temporary, patch or reboot). Permanent Git flags and references are never
disabled or overwritten by temporary AAP metadata.
`patching_exception_source` is `inventory` when any Git exemption applies,
otherwise `aap_group` for a temporary-only exemption.

An active patch exemption skips patch installation and both reboot phases.
An active reboot exemption skips both reboot phases and blocks patch
installation so the cycle cannot complete halfway. `patching_reboot_allowed`
remains an independent inventory permission and is not an exemption.

Exempt hosts are still inspected and reported (`patched: false`,
`exempt: true`, `result: exempt`).

## Maintenance Window

`patch_require_maintenance_window` (default `true`) is an administrative Job
Template or scheduled-execution extra variable. Do not put it on the operator
survey. Recurring AAP schedules can own execution timing; set the flag
`false` on those templates so operators do not maintain UTC start/end for
each run.

When `patch_require_maintenance_window` is `true`, Apply (when installing) and
actual reboot operations require:

- `maintenance_window_start` / `maintenance_window_end` — UTC ISO-8601
  `YYYY-MM-DDTHH:MM:SSZ`
- `maintenance_window_acknowledged` — must be true
- Current UTC must fall inside the window

When `patch_require_maintenance_window` is `false`, start, end, and
acknowledgement are not required. Authorized install and reboot still use
Limit, install/reboot authorization, host reboot policy, exemptions, and
WSUS checks. Precheck always reports window status and does not enforce it.

Fit an open window by shrinking the Limit or increasing approved concurrency
(`patch_serial` / `forks`). Reducing `patch_serial` (default `1`) **increases**
wall-clock time because Play 1 processes fewer hosts at once. See
[aap-controller-setup.md](aap-controller-setup.md).

## Failure Behavior

| Condition | Result |
| --- | --- |
| Missing, blank, `all`, or `*` Limit | Job fails |
| Full Patch Limit not in `approved_patch_targets` | Job fails |
| Missing or invalid WSUS client configuration | Standalone Precheck fails. Full Patch marks the host ineligible and continues reporting. Remediating Apply fails. Repair WSUS in provisioning; this repository does not configure it. |
| Pending reboot before remediating Apply | Apply fails closed. It does not reboot. |
| Invalid or closed maintenance window | Remediating Apply and actual reboot operations fail when `patch_require_maintenance_window` is true |
| Invalid `windows_*_patch_reboot_mode` | Reboot phase fails closed |
| `patching_reboot_allowed: false` | Reboot skipped; `manual_followup_required`. Job does not fail solely for this. |
| Unreachable Windows host | Host remains in the Limit and is reported as `failed` / `UNREACHABLE`. Missing probe evidence is `not_available`, not a confirmed healthy or zero value. JSON/CSV/Markdown and optional SMTP still run. The Full Patch job then fails. `degraded`, `exempt`, `blocked`, `already_compliant`, and `unknown` do not fail the job by themselves. |
| Update search failed after retries | Search does not coerce a zero count. Remaining updates are `not_available` (not `already_compliant`). Discovery records evidence, then fails closed so Apply is skipped. Precheck marks the host ineligible. Final reporting still runs. |
| Apply install failed or hit `windows_apply_timeout` (default 7200s) | Installation evidence is recorded (`updates_installed` stays `not_available` when the count is unknown, never coerced to `0`). The host then fails closed. No automatic Apply retry or async/poll. JSON/CSV/Markdown still run; the AAP job fails afterward. |
| Temporary exception | Host reported as `exempt`; `patched: false`; install and reboot skipped. Does not fail the job solely because it is exempt. |
| Client PowerShell precheck failed (when enabled) | Standalone Precheck fails. Full Patch marks the host ineligible. Remediating Apply fails. |
| Unsupported OS policy | Remediating Apply fails |
| Production CR validation required but shared ServiceNow role absent, failed, or unknown | Eligible host skips remaining remediation. Final JSON/CSV/Markdown still run. The Full Patch job then fails. Lab templates with `snow_require_change_validation=false` do not require ServiceNow. |

## PowerShell Client Precheck

Disabled by default (`windows_powershell_precheck_enabled: false`).

`client_precheck.ps1` is the integration point. Replace it with the approved
client script before enabling.

When enabled, malformed output, execution failure, `critical_failed=true`, or
`overall_health=failed` blocks remediation. Minimum required fields:

- `critical_failed`
- `overall_health`

## ServiceNow

See [external-contracts.md](external-contracts.md). EXAMPLE URI tasks stay
disabled. `snow_enabled` and `snow_require_change_validation` are
administrator Job Template extra-vars, not survey fields.

Lab Job Template extra-vars: `snow_require_change_validation=false` so
authorized testing can run without the unpublished shared role. Production
must set it `true` with `snow_shared_role` empty until that role is in the
EE; remediating hosts then fail closed. Eligible hosts validate **per host**
(CI scope) before pre-reboot. Failures skip that host's remaining
remediation, keep final reporting, then fail the job.

## SMTP Reporting

Optional. Disabled by default (`report_email_enabled: false`). When enabled,
Full Patch sends one plain-text summary after the aggregate CSV is written.
It does not change patching results. Files written inside the Execution
Environment are ephemeral; emailing a report does not satisfy enterprise
evidence-retention requirements.

Enable with extra-vars or Controller extra variables. Do not survey SMTP
secrets. Do not store passwords in Git or inventory.

| Variable | Default | Meaning |
| --- | --- | --- |
| `report_email_enabled` | `false` | Send the summary email |
| `report_email_smtp_host` | empty | SMTP relay hostname (required when enabled) |
| `report_email_smtp_port` | `587` | SMTP port |
| `report_email_smtp_secure` | `starttls` | `starttls`, `always` (implicit TLS), or `never` (plaintext) |
| `report_email_smtp_username` | empty | Optional SMTP username |
| `report_email_smtp_password` | empty | Optional SMTP password |
| `report_email_from` | empty | From address (required when enabled) |
| `report_email_to` | `[]` | Recipient list (required when enabled) |
| `report_email_attach_csv` | `true` | Attach the existing CSV report |
| `report_email_fail_on_error` | `false` | If `true`, SMTP failure fails the job after reporting |

Authenticated SMTP requires both username and password. Leave both empty for
an unauthenticated relay. Inject credentials from an AAP Credential (custom
credential type or extra-var/environment injection:
`REPORT_EMAIL_SMTP_USERNAME` / `REPORT_EMAIL_SMTP_PASSWORD`). TLS certificate
validation remains enabled for `starttls` and `always`. Use `never` only for
isolated capture servers such as Mailpit.

The Execution Environment must reach the SMTP host. Rebuild
`windows-patch-ee` after adding `community.general` so `community.general.mail`
is available.

CSV attachment uses `patch_final_report_csv_path` from `final_write.yml`. It
is not regenerated. If the file is missing, email is not sent.

SMTP failure records `report_email_delivery_status=failed`, warns the
operator, and leaves patch results unchanged. The job continues unless
`report_email_fail_on_error=true`.

### Mailpit / homelab

Supply host and port externally. Example extra-vars (placeholder IP only):

```yaml
report_email_enabled: true
report_email_smtp_host: "192.168.4.X"
report_email_smtp_port: 1025
report_email_smtp_secure: never
report_email_from: "aap-test@example.test"
report_email_to:
  - "patch-reports@example.test"
report_email_attach_csv: true
```

### Client SMTP relay

```yaml
report_email_enabled: true
report_email_smtp_host: "smtp.example.client.tld"
report_email_smtp_port: 587
report_email_smtp_secure: starttls
report_email_from: "aap-windows-patch@example.client.tld"
report_email_to:
  - "patch-reports@example.client.tld"
```

Set username/password through AAP Credentials, not in this file.
