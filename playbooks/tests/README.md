# Standalone ServiceNow tests

These playbooks exercise `servicenow_patching_change` and `servicenow_incident` on localhost. They are not part of `playbooks/windows/full_patch.yml` and they do not target Windows patch waves.

`roles/servicenow_change/` is the existing Windows adapter and is not used here.

## Job template

Create one job template per playbook. Use the same settings for each:

| Field | Value |
| --- | --- |
| Inventory | An inventory that can resolve `localhost`. The controller's implicit localhost is enough. |
| Limit | Leave empty. A Windows wave limit skips `hosts: localhost`. |
| Credential | The custom credential that injects `SN_HOST`, `SN_USERNAME`, and `SN_PASSWORD`. |
| Execution environment | An image that already contains `servicenow.itsm` 2.6.3 or newer. |
| Verbosity | Normal. Do not use `-vvv`. |

`execution-environments/windows-patch-ee/requirements.yml` now lists `servicenow.itsm`. The image already published from that definition does not include the collection until the EE is rebuilt. Do not point these templates at `playbooks/windows/full_patch.yml`.

## Playbooks

Read an existing change. This is the smallest check.

```text
Playbook: playbooks/tests/test_snow_change.yml
Extra variables:
  snow_test_change_number: CHG0000123
```

The playbook displays `snow_result`. It does not create, update, or close the change.

Broader change-role checks, copied from the ServiceNow repository. Create, work notes, close, CI association, report attachment, and sample-file creation stay off unless the matching extra variable is `true`.

```text
Playbook: playbooks/tests/snow_role_test.yml
```

Read-only example:

```text
snow_test_read_number: CHG0000123
```

Attach three sample files to an existing change, without creating or closing one:

```text
snow_test_enable_sample_files: true
snow_test_enable_attach_reports: true
snow_test_attach_number: CHG0000123
```

Incident checks. Create, update, and close stay off unless the matching extra variable is `true`.

```text
Playbook: playbooks/tests/snow_incident_test.yml
```

Read-only example:

```text
snow_incident_test_read_number: INC0000123
```

Leave every `*_enable_*` flag false unless that write was requested for this test. A successful read is not authorization to patch.
