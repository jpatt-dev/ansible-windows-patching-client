# Controller configuration as code

This directory is the declarative AAP 2.7 configuration for Windows patching
**application** objects: one Project and eight Job Templates (Full Patch and
Precheck for LAB, IST, UAT, and PROD).

It does **not** create organizations, inventories, credentials, Execution
Environments, instance groups, or workflow templates. Those are referenced by
name from central platform CaC and the inventory repository.

## Collection / dispatcher status

This repository, `requirements.yml`, and `windows-patch-ee` do **not** declare
`infra.controller_configuration`, `ansible.controller`, or `awx.awx`. Those
FQCN values were not verified against the client's AAP 2.7 Controller.

`playbooks/configure_controller.yml` **fails closed** until:

1. The client names the approved Controller collection FQCN in
   `vars/settings.yml` (`controller_cac_collection`)
2. That collection is installed in the Controller-configuration Execution
   Environment
3. `controller_cac_dispatch_enabled` is set `true`

Do not invent a REST/module wrapper in this repository.

## Objects defined

| Object | Name |
| --- | --- |
| Project | `Windows Patching` (SCM URL is a placeholder) |
| Job Template | `Windows Full Patch LAB` |
| Job Template | `Windows Full Patch IST` |
| Job Template | `Windows Full Patch UAT` |
| Job Template | `Windows Full Patch PROD` |
| Job Template | `Windows Precheck LAB` |
| Job Template | `Windows Precheck IST` |
| Job Template | `Windows Precheck UAT` |
| Job Template | `Windows Precheck PROD` |

Waves are **not** Job Templates. Operators set Limit to `windows_wave_1` …
`windows_wave_20`.

Each Job Template binds one inventory (`ask_inventory_on_launch: false`).
DEV is reserved with no templates.

## Surveys

Job Templates set `survey_file` to:

- `surveys/windows_patch_workflow_survey.yml` (all Full Patch templates)
- `surveys/windows_precheck_survey.yml` (all Precheck templates)

Do not copy question lists into `vars/`. Load those files at dispatch.

## Extra-vars by environment

| Variable | LAB / IST Full Patch | UAT / PROD Full Patch | All Precheck |
| --- | --- | --- | --- |
| `snow_require_change_validation` | `false` | `true` | `false` |
| `snow_enabled` | `false` | `false`. Not used for Full Patch reporting | `false` |
| `snow_shared_role` | empty | empty until the validation role is in the EE | empty |
| `snow_patching_update_cr_enabled` | `false` | `false` until credential and EE are ready | not set |
| `snow_patching_attach_reports_enabled` | `false` | `false` until credential and EE are ready | not set |
| `snow_patching_create_incidents_enabled` | `false` | `false` until caller, group, priority, credential, and EE are ready | not set |
| `snow_patching_create_ctasks_enabled` | `false` | `false` until the Change Task API, assignment group, credential, and EE are ready | not set |
| `snow_change_window_gate_enabled` | `false` | `false` until the validated change supplies its window end | not set |
| `snow_change_close_enabled` | `false` | `false` until Standard Change closure with open Change Tasks is confirmed | not set |
| `patch_require_maintenance_window` | `false` | `true` | `false` |

UAT/PROD remediating hosts **fail closed** while `snow_shared_role` is empty.
Exempt and read-only hosts still skip CR validation in the playbook.

All templates: `ask_limit_on_launch: true`, `ask_variables_on_launch: false`,
`ask_inventory_on_launch: false`, `job_slice_count: 1`.

Protected variables must not be surveyed. See
`controller_cac_protected_variables` in `vars/settings.yml`.

## Bootstrap and SCM promotion

1. Replace every `REPLACE_ME_*` value in `vars/settings.yml`.
2. Confirm the AAP Inventory objects, Machine credential, SCM credential, and
   `windows-patch-ee` already exist (central CaC / inventory repo).
3. Point the Project SCM URL at this GitLab project. Enable **Update Revision
   on Launch**. Promote by merging to the branch named in
   `controller_project_scm_branch`, not by prompting SCM branch on the Job
   Template (`ask_scm_branch_on_launch: false`).
4. Operators receive **Execute** only. Job Template **Admin/Edit** can change
   extra-vars and must stay with a small administrator group.
5. After the client verifies a Controller collection, set the collection FQCN
   and `controller_cac_dispatch_enabled: true`, then run
   `playbooks/configure_controller.yml` twice (second run must be unchanged).

Do not run dispatch from a Windows patch Execution Environment. Use a
Controller-configuration EE that already contains the approved collection.

## Empty approved waves

A Full Patch play with `hosts: windows_hosts` and Limit `windows_wave_N` that
intersects **zero** hosts never runs play tasks, including fail-closed
asserts. Empty waves cannot be detected from inside that play.

The inventory repository must:

- Create `windows_hosts` and `windows_wave_1` … `windows_wave_20`
- Keep wave membership exclusive (a host in at most one approved wave)
- Put every wave member in `windows_hosts`
- Separate LAB / DEV / UAT / PROD (separate inventories, or equivalent
  isolation). `patch_environment` is reporting-only in this repository.
- Fail Controller or inventory acceptance when an approved Limit group is empty

See `tests/controller_cac/test_empty_wave_detection.yml`.

## RBAC

- Operators: Execute on the eight Job Templates. Cannot prompt extra-vars or
  edit templates.
- Administrators: may change PROD extra-vars (`snow_shared_role`, SMTP,
  `snow_enabled`, `snow_patching_update_cr_enabled`,
  `snow_patching_attach_reports_enabled`,
  `snow_patching_create_incidents_enabled`,
  `snow_patching_create_ctasks_enabled`,
  `snow_change_window_gate_enabled`,
  `snow_change_close_enabled`) after change control. Leave
  those switches false until the Windows Full Patch Job Template has the
  existing ServiceNow credential and an Execution Environment that contains
  `servicenow.itsm`. Incident creation also needs `snow_incident_caller`
  when a host requires follow-up. Assignment group and priority are optional.
  Do not change `snow_require_change_validation` as part of
  enabling those switches.
- Emergency override variables must not be stored on the templates.
