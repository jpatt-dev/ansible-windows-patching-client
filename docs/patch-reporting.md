# Patch Reporting

## Phase Results

Each workflow node is an independent AAP job. Host facts do not carry forward.
Each phase records its own result for:

| Phase | Artifact key |
| --- | --- |
| Precheck | `patch_phase_precheck` |
| Pre-Patch Reboot | `patch_phase_reboot_pre` |
| Discovery | `patch_phase_discovery` |
| Apply | `patch_phase_apply` |
| Post-Patch Reboot | `patch_phase_reboot_post` |
| Postcheck | `patch_phase_postcheck` |

A host is treated as present for a phase only when that map exists and contains
the inventory hostname. Missing history is `not_available`. It is not inferred
from later end-state.

## Final Patch Report

Final Patch Report:

- Consumes available upstream phase artifacts
- Performs fresh read-only final-state checks (connectivity, WSUS validate,
  update search, pending reboot, exception resolution)
- Builds per-host `patch_final_result`
- Builds aggregate `patch_workflow_report`

It does not install updates, reboot, or change WSUS configuration.

## Durable Evidence

AAP Job Details / Artifacts (`set_stats`) are the authoritative structured
result.

Human-readable output is available in job output.

JSON, CSV, and Markdown files written inside the Execution Environment
(default `/tmp/aap-patch-reports`) are convenience exports. They are not
durable Controller storage unless exported elsewhere.

## Important Fields

| Field | Meaning |
| --- | --- |
| `host` | Inventory hostname |
| `change_ticket_id` | Change ticket from the workflow survey |
| `patch_status` / `final_status` | Phase result or Final Report status |
| `updates_found` | Updates found in that job |
| `updates_installed` | Installed in Apply; otherwise `0` or `not_available` |
| `updates_remaining` | Remaining after the measuring job |
| `reboot_required` | Pending reboot detected in that job |
| `reboot_performed` | Reboot actually completed |
| `reboot_mode` | Effective reboot policy for that reboot phase (`if_required` or `always`) |
| `manual_followup_required` | Operator follow-up needed |
| `patching_exception_active` | Temporary cycle exception |
| `patching_exception_reference` | Exception/request ID |
| `patching_reboot_allowed` | Inventory reboot policy (reboot phases and Final Report) |
| `windows_wsus_configured` | True when required WSUS policy values are present (`valid` or `invalid`) |
| `windows_wsus_validation_status` | `valid`, `missing`, or `invalid` |
| `windows_wsus_server_effective` | Discovered `WUServer` from the host |
| `windows_wsus_status_server_effective` | Discovered `WUStatusServer` from the host |
| `windows_wsus_use_server_effective` | Discovered `UseWUServer` from the host |

## Status Interpretation

Final Report precedence: `failed` → `excluded` → `degraded` → `compliant`.

| Status | Meaning |
| --- | --- |
| `failed` | Connectivity failed, Apply `patch_status=failed`, or postcheck `failed` |
| `excluded` | Temporary patch-cycle exception. Remaining updates or pending reboot stay `excluded`. |
| `degraded` | Non-excluded host needs attention (pending reboot, remaining updates, invalid/missing WSUS, unknown provider, follow-up, or postcheck issues) |
| `compliant` | Non-excluded host: provider/WSUS OK, no remaining updates, no pending reboot, postcheck acceptable |
