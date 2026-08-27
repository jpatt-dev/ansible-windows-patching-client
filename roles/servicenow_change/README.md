# servicenow_change

Optional ServiceNow change-management hooks for AAP patching workflows.

URI tasks are marked EXAMPLE and must be mapped to the client's tables, fields,
and allowed state transitions before enabling `snow_enabled` in production.

## Safety

| Gate | Default | Behavior |
| --- | --- | --- |
| `snow_enabled` | `false` | Skip all ServiceNow work (safe default) |
| `snow_fail_on_invalid_change` | `true` | Fail when API validation fails |

Safe default disabled (`snow_enabled=false`). ServiceNow is never required.

## Phases (`snow_phase`)

| Phase | Task file | Typical hook |
| --- | --- | --- |
| `validate` | `validate_change.yml` | Before apply / reboot / DB maintenance |
| `work_notes` | `update_work_notes.yml` | After precheck / apply / postcheck |
| `attach_report` | `attach_report.yml` | After compliance report (`snow_attach_report`) |
| `close_task` | `close_or_complete_task.yml` | End of remediation (`snow_close_task`) |

## Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `snow_enabled` | `false` | Master opt-in |
| `snow_instance_url` | `""` | Or env `SNOW_INSTANCE_URL` |
| `snow_auth_type` | `basic` | `basic` or `bearer` |
| `snow_change_id` | `""` | Change sys_id / number per client |
| `snow_change_task_id` | `""` | Required for `close_task` |
| `snow_validate_window` | `true` | Placeholder window check note |
| `snow_update_work_notes` | `true` | Allow work-notes phase |
| `snow_attach_report` | `false` | Allow attach phase |
| `snow_fail_on_invalid_change` | `true` | Fail vs warn on API errors |
| `snow_close_task` | `false` | Allow close-task phase |
| `snow_work_note_message` | `""` | Text for work notes |
| `snow_report_path` | `""` | Local report path for attach |

## Authentication (AAP only)

Do **not** commit secrets. Inject via AAP Credential environment variables:

| Auth | Required env |
| --- | --- |
| `basic` | `SNOW_INSTANCE_URL`, `SNOW_USERNAME`, `SNOW_PASSWORD` |
| `bearer` | `SNOW_INSTANCE_URL`, `SNOW_TOKEN` |

## Client must provide

- Target table / process (change vs task vs custom)
- Required fields and query keys
- Allowed state transitions
- Dev/test instance
- Authentication method

## Optional collection

This role uses `ansible.builtin.uri` so Execution Environments need no ServiceNow
collection. Client forks may replace EXAMPLE tasks with `servicenow.itsm`
(or similar) after pinning the collection in their EE.
