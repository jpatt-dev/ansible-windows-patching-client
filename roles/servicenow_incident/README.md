# servicenow_incident

Small role for ServiceNow incidents opened when a patching workflow reports a failed host. It follows the same controller-only pattern as `servicenow_patching_change`. It is not an incident framework, and it does not decide which hosts failed.

The role uses `servicenow.itsm.incident`, `servicenow.itsm.incident_info`, and `servicenow.itsm.api_info`. Credentials are the AAP custom credential that injects `SN_HOST`, `SN_USERNAME`, and `SN_PASSWORD`. The role passes `SN_HOST` into the module and does not pre-check those names with `lookup('env')`. A rejected API login fails the task. TLS certificate verification stays on. API tasks are `no_log`. `snow_incident_caller` is required to create. `snow_incident_assignment_group` and `snow_incident_priority` are sent only when set.

Call it from a localhost play, or from Full Patch play 2. Do not attach it to the Windows host pattern without `run_once`. `delegate_to: localhost` and `run_once: true` make each API call run once on the controller. `set_fact` writes `snow_incident_result` on the current inventory host for that run. A job Limit that names only Windows hosts skips `hosts: localhost`, so Full Patch calls this role from its existing aggregation play and copies `snow_incident_result` before the next host.

Full Patch passes `snow_incident_correlation_id` as `aap-patch:<change number>:<hostname>:<reason code>`. That overrides the default key, which includes the AAP job id. A rerun with the same change, host, and reason reuses the incident. The job id is still written in the incident text. Two creates at the same moment can both insert. A closed incident with that correlation id is reused; this role does not reopen it.

## Operations

Set `snow_incident_operation` to one of:

| Operation | What it does |
| --- | --- |
| `read` | Returns one incident by number. Fails when the number is missing or not unique. |
| `create` | Opens one incident in New, unless the same correlation id already exists. Requires `snow_incident_allow_create: true`. |
| `update` | Updates only the fields you pass, and can append a work note. Does not change state. |
| `close` | Requests state Closed, then reads the incident. Success requires the follow-up read to show `closed`. Requires `snow_incident_allow_close: true`. |

## Idempotency

`read` is idempotent.

`create` looks up `correlation_id` before inserting. Hostname, change number, correlation id, assignment group, and job id are rejected when they contain `^` or a line break. The default id is `aap-patch:<hostname>:<change number>:<job id>`. A retry with that same id returns the existing incident and does not open another one, including when that incident is already closed. Pass a new `snow_incident_correlation_id` to open another incident after closure. Two creates racing at the same moment can still both insert. A second distinct failure in the same job, for the same host and change, also reuses the first incident unless the caller supplies a different correlation id. Without a hostname or an explicit correlation id, create is refused.

`update` field changes are safe to repeat. Work notes, including the `AAP job` line, are appended again on every run that includes them.

`close` is confirmed only when a follow-up read shows state `closed`. The module response alone is not success. This role does not walk New, In Progress, or Resolved. An instance that requires those steps rejects the close, or the follow-up read fails the task when the state is not `closed`.

## Inputs

| Variable | Default | Used by |
| --- | --- | --- |
| `snow_incident_operation` | `""` | All. Required. |
| `snow_incident_number` | `""` | read, update, close |
| `snow_incident_hostname` | `""` | create text and the default correlation id |
| `snow_incident_change_number` | `""` | create text and the default correlation id |
| `snow_incident_failure` | `""` | create text. On update it is appended as a work note. |
| `snow_incident_short_description` | `""` | create, update |
| `snow_incident_description` | `""` | create, update |
| `snow_incident_work_notes` | `""` | create, update. Sent as `other.work_notes`. |
| `snow_incident_aap_job_id` | `""` | create, update. Falls back to `tower_job_id` or `awx_job_id`. |
| `snow_incident_ci_sys_id` | `""` | create, update. Optional 32-character sys_id copied to `cmdb_ci`. |
| `snow_incident_assignment_group` | `""` | create, update, close. Group name. The role sends the sys_id. |
| `snow_incident_caller` | `""` | create. User id, usually `first.last`. Required. |
| `snow_incident_priority` | `""` | create, update, close. Forwarded unchanged. |
| `snow_incident_correlation_id` | `""` | create. Overrides the default retry key. |
| `snow_incident_fields` | `{}` | create, update, close. `impact` and `urgency` are module arguments. |
| `snow_incident_allow_create` | `false` | create |
| `snow_incident_allow_close` | `false` | close |
| `snow_incident_close_code` | `""` | close |
| `snow_incident_close_notes` | `""` | close |

`snow_incident_ci_sys_id` is a format check. It does not prove the configuration item exists, and this role does not create or modify configuration items.

`snow_incident_caller` is the user id the collection looks up. It is not a free-text display name.

`snow_incident_priority` is the instance's own value, often `1` through `5`. This role does not translate labels. Some instances calculate priority from impact and urgency and ignore this field.

`snow_incident_fields` may include `impact` and `urgency` (`high`, `medium`, `low` on an unmodified instance) and client columns such as `u_*`. These keys are rejected: `state`, `hold_reason`, `close_code`, `close_notes`, `work_notes`, `number`, `sys_id`, `caller`, `caller_id`, `correlation_id`, `cmdb_ci`, `assignment_group`, `priority`, `attachments`, `incident_mapping`. Use the dedicated variables for those.

The change number is written in the incident description. This role does not create a ServiceNow related-record link.

Collection 2.6.3 knows these close-code labels: `Duplicate`, `Known error`, `Resolved by caller`, `Resolved by change`, `Resolved by problem`, `Solution provided`, `Workaround provided`, `User error`. Any other non-empty code is forwarded, and the instance can reject it.

The job id is the first non-empty value among `snow_incident_aap_job_id`, `tower_job_id`, and `awx_job_id`. A missing job id does not fail the task.

## Returned variable

`snow_incident_result` is set on localhost. It is separate from the change role's `snow_result`. Copy it before the next role call if you still need it.

| Key | Meaning |
| --- | --- |
| `operation` | The operation that ran |
| `success` | `true` only after the operation's own checks pass |
| `number` | Incident number |
| `sys_id` | Incident sys_id |
| `state` | Collection label when it recognizes the value (`new`, `in_progress`, `on_hold`, `resolved`, `closed`, `canceled`) |
| `short_description` | Summary returned by ServiceNow |
| `correlation_id` | Present on create, and on read when ServiceNow returned it |
| `hostname` | Present on create. The hostname the caller supplied. |
| `reused` | Present on create. `true` when an existing correlation id was returned instead of inserting. |
| `closure_confirmed` | Present on close. `true` only when the follow-up read showed `closed`. |
| `message` | Short status |

A failed operation stops the play and does not publish a successful result. Close publishes a result only after the follow-up read shows `closed`.

## Examples

Create an incident for one failed host. The patching workflow chooses the host. This role does not classify a degraded host as a failure.

```yaml
- name: Open an incident for a failed host
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Create the incident
      ansible.builtin.include_role:
        name: servicenow_incident
      vars:
        snow_incident_operation: create
        snow_incident_allow_create: true
        snow_incident_caller: "{{ patch_caller }}"
        snow_incident_hostname: WIN-TEST-02
        snow_incident_aap_job_id: "830"
        snow_incident_change_number: CHG0001234
        snow_incident_failure: Windows patching failed
        snow_incident_assignment_group: "{{ patch_assignment_group }}"

    - name: Keep the incident number
      ansible.builtin.set_fact:
        failed_host_incident: "{{ snow_incident_result.number }}"
```

Update that incident without changing its state:

```yaml
- name: Add a work note to the incident
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Update the incident
      ansible.builtin.include_role:
        name: servicenow_incident
      vars:
        snow_incident_operation: update
        snow_incident_number: "{{ failed_host_incident }}"
        snow_incident_work_notes: "Collected the Windows patch log."
```

Close only when the client's process allows it:

```yaml
- name: Close the incident
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Close and verify
      ansible.builtin.include_role:
        name: servicenow_incident
      vars:
        snow_incident_operation: close
        snow_incident_allow_close: true
        snow_incident_number: "{{ failed_host_incident }}"
        snow_incident_close_code: "Solution provided"
        snow_incident_close_notes: "Patching completed on a later run."
```

## Test playbook

From the repository root, with `ANSIBLE_ROLES_PATH=common/roles` if Ansible ignores `ansible.cfg`:

```bash
ansible-playbook common/tests/snow_incident_test.yml \
  -e snow_incident_test_read_number=INC0000123
```

Create, read, update, and close stay off unless you set the matching flag. Create also needs a real caller id and hostname:

```bash
ansible-playbook common/tests/snow_incident_test.yml \
  -e snow_incident_test_enable_create=true \
  -e snow_incident_test_caller=first.last \
  -e snow_incident_test_hostname=WIN-TEST-02 \
  -e snow_incident_test_change_number=CHG0001234 \
  -e snow_incident_test_job_id=830 \
  -e snow_incident_test_failure='Windows patching failed'
```

A second create with the same hostname, change, and job id returns the first incident. The playbook reads the new incident and checks the short description. Update reads the incident again and checks the new summary. Close reads it again and requires state `closed`.

AAP job template: playbook `common/tests/snow_incident_test.yml`, localhost, the same ServiceNow credential type, and only the flags you mean to run. Leave the enable flags false for a read-only job.

## Limitations

- No live ServiceNow call was made while adding this role. Syntax-check and ansible-lint do not prove the instance accepts the close transition or the caller's user id.
- Create stays off unless `snow_incident_allow_create` is true. The check-then-insert correlation lookup is not a lock.
- The default correlation id is one incident per hostname, change number, and job id. A different failure in that same job needs its own `snow_incident_correlation_id`.
- Reusing a correlation id returns a closed incident instead of opening a new one. The result state says so.
- Close expects the collection's default state label `closed`. A custom incident state model can make a successful module call fail this role's follow-up check. `incident_mapping` is not exposed.
- The role does not delete incidents.
- Assignment group lookup uses `name=<group>` on `sys_user_group` and requires one exact name match. `api_info` rows are accepted from `record` or `records`, whether that value is one mapping or a list.
- Execution environment files are temporary and are not shared between AAP jobs. This role does not attach reports. Attach patch reports with `servicenow_patching_change` and `attach_reports` in the job that created the files.
