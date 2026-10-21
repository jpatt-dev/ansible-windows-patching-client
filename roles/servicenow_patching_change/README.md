# servicenow_patching_change

Small role for ServiceNow change requests. Windows, Linux, and database patching jobs can call it from a localhost play. It is not a change-management framework.

The role uses `servicenow.itsm` modules: `change_request`, `change_request_info`, `api`, `api_info`, and `attachment_upload`. It does not ship a separate REST client.

## Collection and execution environment

- Ansible Automation Platform 2.7 supported execution environments use ansible-core 2.16.
- Collection: `servicenow.itsm` 2.6.3 or newer.
- The arguments this role sends were compared on 2.6.3, 2.7.0, 2.9.0, 2.13.2, and 2.16.0. They match.
- The collection has no extra collection or Python dependencies.
- Confirm the job template's execution environment includes the collection. Add it when `ee-supported` does not.

Example execution-environment requirement:

```yaml
collections:
  - name: servicenow.itsm
    version: "2.6.3"
```

Pin the certified version you have tested. `common/tests/requirements.yml` records the same floor for local installs.

Install the corporate CA into the execution environment image. The role forces TLS certificate verification and does not provide a switch to turn it off.

## AAP credential

Create a custom credential type. Input configuration:

```yaml
fields:
  - id: SN_HOST
    type: string
    label: ServiceNow instance URL
  - id: SN_USERNAME
    type: string
    label: Username
  - id: SN_PASSWORD
    type: string
    label: Password
    secret: true
required:
  - SN_HOST
  - SN_USERNAME
  - SN_PASSWORD
```

Injector configuration:

```yaml
env:
  SN_HOST: "{{ SN_HOST }}"
  SN_USERNAME: "{{ SN_USERNAME }}"
  SN_PASSWORD: "{{ SN_PASSWORD }}"
```

`SN_HOST` is the instance URL and must start with `https://`. Do not put a username or password in the URL.

Assign that credential to the job template. The collection reads `SN_USERNAME` and `SN_PASSWORD` from the environment. The role passes `SN_HOST` into the module so the instance URL is explicit, and it does not accept the password as a playbook variable. It does not pre-check those names with `lookup('env')`, because that check can fail while the same AAP credential still authenticates the module. A rejected API login fails the task. API tasks are `no_log`, so the URL and secret are not written to the normal job log. TLS certificate verification stays on.

Optional collection variable: `SN_TIMEOUT` (seconds). The collection default is 10. Leave `SN_VALIDATE_CERTS` unset. The role sends `validate_certs: true`, which keeps verification on.

## Operations

Set `snow_operation` to one of:

| Operation | What it does |
| --- | --- |
| `read` | Returns one change by number. Fails when the number is missing or not unique. |
| `create` | Opens one normal change in New. Requires `snow_allow_create: true`. |
| `update` | Updates only the fields you pass, and can append a work note. An AAP job id, when present, is added to that note. |
| `close` | Requests state Closed. Requires `snow_allow_close: true`, close notes, and a close code. |
| `add_cis` | Links existing configuration item sys_ids through `task_ci`. Skips a CI that is already linked, then re-reads each relationship. |
| `attach_reports` | Uploads existing report files to the change. The file name is the attachment identity. |
| `validate` | Fails closed. This is the future patch-authorization check. |

`create` always inserts a new record. Duplicate protection is a future requirement. A retry creates another change.

`create` sends `type: normal` and `state: new`. It does not send a standard-change template, and it does not approve the record. The collection copies `type` into `chg_model`.

`update` does not change approval or state. Closure goes through `close`. On update, the work note is `snow_work_notes` plus `AAP job <id>` when a job id is available. The id is the first non-empty value among `snow_aap_job_id`, `tower_job_id`, and `awx_job_id`. Those AAP variables are optional. A missing job id does not fail the update.

`add_cis` reads the change, confirms each sys_id exists in `cmdb_ci`, then queries `task_ci` for `task=<change sys_id>^ci_item=<CI sys_id>`. `servicenow.itsm` 2.6.3 returns that list from `api_info` as `record`. The role posts a row only when that list is empty, then reads `task_ci` again. A reference field may be a sys_id string or a mapping with `value`. Success requires the follow-up read to show exactly one matching relationship. The POST response is not proof. Set `snow_task_ci_diagnostics: true` to log row counts and field types without the payload. The 32-character hexadecimal check happens before any API call and only checks format. This role does not create configuration items and it does not set the change `cmdb_ci` field.

`attach_reports` reads the change, checks that each path is a readable file on the controller, and uploads those files with `servicenow.itsm.attachment_upload` to table `change_request` and that change's sys_id. It then reads `sys_attachment` and checks the file name, table, sys_id, and byte size. The collection treats the file name as the attachment identity: the same name and the same bytes are left unchanged, and the same name with different bytes overwrites that attachment. A repeated run does not create a second attachment of the same name. This operation does not update other change fields and does not close the change.

Report files exist only on the execution node for the job that created them. A later AAP job does not see those paths. Generate the reports and attach them in the same job, or place them somewhere that job can read. This role does not copy files between jobs.

`close` sends `state: closed` plus the close code and notes. It does not move the change through Assess, Authorize, Scheduled, Implement, or Review, and it does not set approval. When ServiceNow rejects the transition, the task fails with the collection error.

`validate` records `snow_result.success: false` and then fails. A retrieved change is not permission to patch. Approval rules, the maintenance window, and configuration-item scope still have to be implemented before this operation can succeed.

## Input variables

| Variable | Default | Used by |
| --- | --- | --- |
| `snow_operation` | `""` | All. Required. |
| `snow_change_number` | `""` | read, update, close, add_cis, attach_reports |
| `snow_change_sys_id` | `""` | add_cis, instead of or together with the number |
| `snow_ci_sys_ids` | `[]` | add_cis. List of CI sys_ids. Format is checked first, then `cmdb_ci`. |
| `snow_task_ci_diagnostics` | `false` | add_cis. Logs row counts and field types when confirmation fails. |
| `snow_report_files` | `[]` | attach_reports. Controller paths. File names must be unique. |
| `snow_aap_job_id` | `""` | update. Preferred job id for the work note. |
| `snow_short_description` | `""` | create (required), update (optional) |
| `snow_description` | `""` | create, update |
| `snow_work_notes` | `""` | create, update. Close ignores it. |
| `snow_change_fields` | `{}` | create, update, close. Includes `assignment_group` and client columns. |
| `snow_allow_create` | `false` | create |
| `snow_allow_close` | `false` | close |
| `snow_close_code` | `""` | close |
| `snow_close_notes` | `""` | close |

`snow_close_code` must be `successful`, `successful_issues`, or `unsuccessful`. Those are the choices on `servicenow.itsm.change_request`. This role does not map client-specific labels.

`snow_change_fields` keys that match the module are sent as module arguments:

- `requested_by` (user name the collection can look up)
- `assignment_group` (group name, not a sys_id)
- `assignment_group_id` (sys_id; do not also set `assignment_group`)
- `category`, `priority`, `risk`, `impact`, `urgency`
- `short_description`, `description` (explicit `snow_short_description` and `snow_description` win on create and update)
- `on_hold`, `hold_reason` (update only; `on_hold: true` requires `hold_reason`)

Any other key is sent through the module's `other` parameter. That is how client columns such as `cmdb_ci`, `justification`, `implementation_plan`, `backout_plan`, `test_plan`, `start_date`, `end_date`, and `u_*` fields are supplied without hardcoding them in the role.

These keys are rejected: `approval`, `approval_history`, `approval_set`, `upon_approval`, `upon_reject`, `state`, `type`, `chg_model`, `template`, `std_change_producer_version`, `number`, `sys_id`, `close_code`, `close_notes`, `work_notes`.

Empty strings are treated as unset. Collection labels for the common choice fields are:

- priority: `critical`, `high`, `moderate`, `low`
- risk: `very_high`, `high`, `moderate`, `low`
- impact and urgency: `high`, `medium`, `low`

An instance that renamed those choices needs a future `change_request_mapping` input. Unrecognized values are forwarded and the collection warns.

On create and update, work notes are sent as `other.work_notes` because `change_request` has no `work_notes` argument. ServiceNow appends the journal entry. Running the same update again appends another copy, including another `AAP job` line when a job id is still set.

## Returned variable

`snow_result` is set on localhost when the operation completes:

| Key | Meaning |
| --- | --- |
| `operation` | The operation that ran |
| `success` | `true` after read, create, update, close, add_cis, or attach_reports. `false` for validate, which then fails. |
| `number` | Change number, or empty for validate |
| `sys_id` | Change sys_id, or empty for validate |
| `state` | Collection value when ServiceNow returned one (`new`, `assess`, `authorize`, `scheduled`, `implement`, `review`, `closed`, `canceled`, or the raw value when the instance uses a custom state) |
| `approval` | Record value when present, otherwise empty |
| `message` | Short status |
| `linked_ci_sys_ids` | Present after `add_cis`. CIs whose relationship was absent before this run and confirmed afterward. |
| `existing_ci_sys_ids` | Present after `add_cis`. CIs that already had a `task_ci` row. |
| `confirmed_ci_sys_ids` | Present after `add_cis`. Every requested CI that the follow-up read confirmed. |
| `attachments` | Present after `attach_reports`. Each item has `path`, `file_name`, `sys_id`, and `size_bytes`. |
| `content_updated` | Present after `attach_reports`. `true` when ServiceNow stored new or replaced bytes for at least one file name. |

A failed read, create, update, or close stops the play and does not publish a successful `snow_result`. Copy `snow_result` into your own variable before the next operation if you still need the previous value.

API task results are marked `no_log`, so the change payload and module diff stay out of the job log. Use `snow_result`. Do not debug the raw module return. `-vvv` can still expose environment data; keep job verbosity at the normal level.

## Run the test playbook

From the repository root (`ansible.cfg` sets `roles_path` to `common/roles`). If Ansible ignores that file because the checkout is world-writable, export `ANSIBLE_ROLES_PATH=common/roles` for the same result.

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_read_number=CHG0000123
```

Create, then read the new change:

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_enable_create=true
```

Add a work note to a specific change:

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_enable_work_note=true \
  -e snow_test_work_note_number=CHG0000123
```

Close one change that is already eligible for closure:

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_enable_close=true \
  -e snow_test_close_number=CHG0000999 \
  -e snow_test_close_code=successful \
  -e snow_test_close_notes='Closed from the role test playbook.'
```

Link existing configuration items. This stays off unless the flag is true:

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_enable_add_cis=true \
  -e snow_test_add_cis_number=CHG0000123 \
  -e '{"snow_test_ci_sys_ids":["0123456789abcdef0123456789abcdef"]}'
```

Attach three sample reports to an existing change. This writes the files in the current job and does not create or close a change:

```bash
ansible-playbook common/tests/snow_role_test.yml \
  -e snow_test_enable_sample_files=true \
  -e snow_test_enable_attach_reports=true \
  -e snow_test_attach_number=CHG0000123
```

To upload files you already created in this job, leave sample generation off and pass `snow_test_report_files`.

AAP job template:

1. Playbook: `common/tests/snow_role_test.yml`
2. Inventory: one that can resolve `localhost` (Ansible's implicit localhost is enough on a default controller)
3. Credential: the ServiceNow credential type above
4. Extra variables: only the test flags you intend to run
5. Execution environment: ansible-core 2.16 plus `servicenow.itsm`

Leave the enable flags at false for a read-only job.

## Calling the role

The supported pattern is a play whose host is localhost. `delegate_to: localhost`, `run_once: true`, and `ansible_connection: local` make the ServiceNow call run once on the controller. `set_fact` writes `snow_result` on the current inventory host for that single run. In a localhost play, that host is localhost, so later plays read `hostvars['localhost']['snow_result']` or a copy made in the same play.

Do not put `include_role` on `hosts: windows` without `run_once`. `run_once` still prevents one API call per server, but the fact is stored on the first host in that play. A job Limit that changes which host is first also changes where the result is. A localhost play keeps one result location.

Windows Full Patch cannot add a localhost play. AAP wave Limits such as `windows_wave_1` would skip `hosts: localhost`. Play 2 of `playbooks/windows/full_patch.yml` already targets `windows_hosts` with `connection: local` and is not serial. It includes this role with `run_once: true` after the report files exist, then copies `snow_result` before the next operation. The API call still uses this role's `delegate_to: localhost`.

```yaml
- name: Record the patch job on an existing change
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Update the change request
      ansible.builtin.include_role:
        name: servicenow_patching_change
      vars:
        snow_operation: update
        snow_change_number: "{{ change_ticket_id }}"
        snow_work_notes: "Patching execution completed."
        snow_aap_job_id: "{{ tower_job_id | default(awx_job_id) | default('') }}"

    - name: Keep the ServiceNow result
      ansible.builtin.set_fact:
        patch_change_number: "{{ snow_result.number }}"

- name: Patch Windows hosts
  hosts: windows
  tasks:
    - name: Show which change this run is working under
      ansible.builtin.debug:
        msg: "{{ hostvars['localhost']['patch_change_number'] }}"
```

`change_ticket_id` and `patch_report_files` are variables owned by the Windows patching playbook. This role does not read those names. Map them at the call:

```yaml
- name: Attach the patch reports
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Upload reports to the existing change
      ansible.builtin.include_role:
        name: servicenow_patching_change
      vars:
        snow_operation: attach_reports
        snow_change_number: "{{ change_ticket_id }}"
        snow_report_files: "{{ patch_report_files }}"
```

AAP sets `tower_job_id` in the job that is running, and some releases also set `awx_job_id`. Pass the patch job's id as `snow_aap_job_id`. If the ServiceNow update is a later workflow node, that node's own `tower_job_id` is not the patch job. Have the patch job publish its id with `ansible.builtin.set_stats`, and pass that value into the ServiceNow job. When the update runs in the patch job itself, `tower_job_id` is the correct source. The role also falls back to `tower_job_id` or `awx_job_id` when `snow_aap_job_id` is empty. An explicit value is easier to trace.

Failed hosts are incidents, not change updates. Use `servicenow_incident` only for hosts the patching workflow has already decided need an incident. Its result is `snow_incident_result` on localhost, separate from `snow_result`.

Do not call `validate` from a patch play yet. It fails on purpose. Do not create, approve, or close a change from the patch result. `snow_allow_create` and `snow_allow_close` stay false unless that operation was explicitly requested.

A successful Windows patch and a successful ServiceNow call are different outcomes. `snow_result.success` means that ServiceNow operation finished. It does not mean the servers patched. A patch that already succeeded is not rolled back when a later ServiceNow update fails. Attaching a report or writing a work note does not close the change. Closing still requires `snow_allow_close: true` and a close code the instance accepts.

Copy `snow_result` before the next role call. Publish `snow_result.number` with `ansible.builtin.set_stats` when a later job template needs it. That stays in the caller.

## Windows patching integration

Copy `common/roles/servicenow_patching_change` and `common/roles/servicenow_incident` into the patching repository's roles path, or add this repository's `common/roles` to `roles_path`. Do not rename the incident role. Keep calling `snow_operation` and the existing `snow_*` variables. This repository does not modify the Windows patching playbooks.

Collection: `servicenow.itsm` 2.6.3 or newer, pinned to the certified build installed in the execution environment. The arguments used here match 2.6.3 through 2.16.0. The collection has no extra Ansible collection dependencies. `common/tests/requirements.yml` records the same floor.

Credential: the custom credential type that injects `SN_HOST`, `SN_USERNAME`, and `SN_PASSWORD`. `SN_HOST` is `https://` with no embedded user or password. Attach that credential to the job template that runs the localhost play. The role does not accept the password as a playbook variable.

Execution environment network: the job's execution node must resolve `SN_HOST` and open outbound HTTPS, normally port 443, to that instance. Install the corporate CA in the image. The role forces `validate_certs: true` and has no switch to turn verification off. If the instance is reachable only through a proxy, configure that proxy in the execution environment. This role does not set one.

Report files must already exist on the controller in the same AAP job that calls `attach_reports`. The execution environment disk is removed when the job ends. A later job template cannot read `/tmp` paths from an earlier job. Generate `patch_report_files` in the patch job, then upload them from that same job.

AAP Limit applies to every play. A limit of `windows_wave_1` does not match `hosts: localhost`, so a separate ServiceNow play is skipped. Full Patch therefore calls this role from its existing non-serial aggregation play. A workflow that uses a later job template for ServiceNow must pass the change number and must not expect the earlier job's `/tmp` files to still exist.

Before the first non-production job: read an existing change, attach the three sample reports to that change with `snow_test_enable_sample_files` and `snow_test_enable_attach_reports`, and confirm `snow_result.attachments`. Leave create and close flags false until the ServiceNow owners agree the field list, assignment group, and close code. Leave `validate` failing until approval, the maintenance window, and CI scope are implemented. Do not treat a read or a successful patch as authorization to patch.

## Limitations

- No live ServiceNow instance was called from this workspace. YAML parsing, `ansible-playbook --syntax-check`, and `ansible-lint` production profile passed on ansible-core 2.16 with `servicenow.itsm` 2.6.3. Offline checks covered input guards, the task_ci confirmation filter, and the attachment confirmation filter. The `task_ci` confirmation read and `attachment_upload` were not executed against ServiceNow.
- `ansible-lint` production profile passes. `.ansible-lint` skips `var-naming[no-role-prefix]` because the shared interface is `snow_*`, not `servicenow_patching_change_*`. Keep that skip if the common repository enables the rule.
- Create is not idempotent.
- Validate cannot authorize patching yet.
- Close does not advance a change that is still in New, and it does not approve anything.
- Close codes are the three collection choices. Client choice lists and `change_request_mapping` are not configurable yet.
- Some instances require `assignment_group` before a transition. Pass the group name in `snow_change_fields` when yours does. The module documents that requirement more broadly than its 2.6.3–2.16.0 argument checks enforce for `closed`.
- Work notes append on every update that includes `snow_work_notes` or a resolved AAP job id.
- `add_cis` is idempotent for the same change and CI sys_id. It does not create CIs, and a second run does not insert a duplicate `task_ci` row. Success means a follow-up `api_info` read, returned in `record`, saw each relationship. The role also requires each sys_id to exist in `cmdb_ci` before it posts `task_ci`.
- `attach_reports` does not create a second attachment when the file name already exists. Different bytes replace that attachment. Same bytes leave it unchanged. Two paths that share a file name are rejected before upload.
- Returned `state` is the collection's label when it recognizes the value. `approval` is the value ServiceNow stored.
- Client columns passed in `snow_change_fields` are sent as given. ServiceNow ACLs and business rules still decide whether they stick.
- Passing `cmdb_ci` does not check that the later patch targets are in scope.
- The role does not delete changes (`state: absent` is not used).
- Files in an AAP execution environment are temporary. They are not shared with the next job. Attach reports from the job that wrote them.
- A job Limit that names only Windows hosts skips a `hosts: localhost` play. Include localhost in that limit, or run ServiceNow from a separate job template.
