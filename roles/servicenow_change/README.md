# servicenow_change

Thin adapter. This role does **not** implement ServiceNow REST APIs.

Work notes and attach use `snow_shared_role` after that unpublished shared
ServiceNow Change role is published. This repository does not name that
collection or version.

## Policy

| Variable | Surveyed? | Default | Meaning |
| --- | --- | --- | --- |
| `snow_require_change_validation` | **No** | `false` | Production CR gate. Lab leaves false. |
| `snow_enabled` | **No** | `false` | Optional work notes/attach after the shared role exists |
| `snow_shared_role` | **No** | empty | FQCN supplied by Controller/EE when published |

See [docs/external-contracts.md](../../docs/external-contracts.md).

## Identifiers

- Display number: `snow_change_number` or survey `change_ticket_id`
- sys_id: `snow_change_sys_id` or legacy `snow_change_id`
- Host CI: inventory `snow_ci_sys_id`

## Confirmation fact

Until the shared workstream publishes its schema, this adapter treats
validation as confirmed only when `snow_change_validation_ok` is true.
Undefined is unknown and fails closed when the production policy is enabled.

## Authentication (AAP only)

Do **not** commit secrets. Inject via AAP Credential environment variables
when the shared role needs them:

| Auth | Required env |
| --- | --- |
| `basic` | `SNOW_INSTANCE_URL`, `SNOW_USERNAME`, `SNOW_PASSWORD` |
| `bearer` | `SNOW_INSTANCE_URL`, `SNOW_TOKEN` |
