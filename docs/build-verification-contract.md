# Build verification reporting contract

Windows build verification is a read-only inventory snapshot. It is not a
patch result and it does not calculate compliance. The job does not call
ServiceNow. The client inventory sync must already have placed the variables
below on each host.

This repository does not know the ServiceNow table or column names. Mapping
those columns onto the variables in this document is still client work. The
sync must not rebuild `windows_wave_*`, exemption groups, or `patch_temp_*` /
`reboot_temp_*`.

## Inventory variables

| Variable | Required for a complete row | When missing |
| --- | --- | --- |
| `inventory_hostname` | Yes. This is the report hostname. | AAP always supplies it. |
| `cmdb_fqdn` | Yes | `not_available`, plus a diagnostic |
| `cmdb_os_release` | Yes | `not_available`, plus a diagnostic |
| `patch_location` | Yes | Empty string. No site is invented. |
| `patch_environment` | Yes. `LAB`, `IST`, `UAT`, or `PROD`. | Empty. The job label becomes `unspecified` when no host has a value, or `inconsistent` when hosts disagree. |
| `sys_id` | Yes. CMDB CI sys_id. | JSON `snow_ci_sys_id` is `not_available`, plus a diagnostic. |

A value that is only whitespace is treated as missing. A missing CMDB field
does not fail the live Windows build query. The live OS caption, DNS name,
and FQDN are never copied into `cmdb_fqdn`, `cmdb_os_release`, location, or
`sys_id`.

## Reporting fields

| Report field | Source |
| --- | --- |
| Hostname | `inventory_hostname` |
| FQDN | `cmdb_fqdn` |
| Platform | `windows` for this playbook |
| OS Release | `cmdb_os_release` |
| OS Version | Live Windows `Version`, for example `10.0.20348` |
| Current Build / Kernel | Live `BuildNumber.UBR`, for example `20348.2849` |
| Location | `patch_location` |
| Environment | `patch_environment` |
| Collection Status | `success`, `failed`, or `unreachable` |
| Collection Time | UTC timestamp |
| Diagnostic | Blank when the live build and the CMDB fields above are present |

`collection_status: success` means the OS version and base build were read.
It does not mean the server is patched or compliant.

## Per-host JSON

Each host object in `windows_build_verification_report.hosts` has this shape.
`schema_version` on the report is `"2"`.

```yaml
inventory_hostname: win-2022
hostname: win-2022
fqdn: win-2022.cmdb.example
platform: windows
os_release: Windows Server 2022
os_version: "10.0.20348"
current_build: "20348.2849"
current_build_kind: windows_build
location: Datacenter-East
patch_environment: LAB
snow_ci_sys_id: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
collection_status: success
collection_time_utc: "2026-10-29T18:00:00Z"
diagnostic: ""
```

`snow_ci_sys_id` is JSON only. It is not a CSV column.

The report object also has `report_source: windows_build_verification`,
`platform`, `generated_at_utc`, `patch_environment`, `total_systems`,
`systems_succeeded`, `systems_failed`, `systems_unreachable`,
`email_delivery`, `aap_limit`, `aap_job_id`, and `csv_path`.

## CSV columns

The header, in order, is:

`Hostname`, `FQDN`, `Platform`, `OS Release`, `OS Version`,
`Current Build / Kernel`, `Location`, `Environment`, `Collection Status`,
`Collection Time`, `Diagnostic`

The file is UTF-8 with a byte order mark and CRLF. Fields are quoted. A value
that starts with `=`, `+`, `-`, `@`, tab, or carriage return is prefixed with
an apostrophe before quoting. One row is written for every targeted host,
including failed and unreachable hosts. One job writes one CSV.

## Missing CMDB values

On a successful live collection, `Diagnostic` lists only the fields that were
empty:

- `Inventory FQDN was not available.`
- `Inventory OS release was not available.`
- `Inventory CI sys_id was not available.`

If the UBR registry value is missing, the current build stays the base number
plus ` (revision unavailable)`, and the diagnostic starts with
`revision unavailable.` A full dotted build is not invented.

A failed or unreachable query keeps the failure diagnostic. Inventory fields
that are present are still copied onto that row. A host that produced no
record is still listed as `failed` with `Build record was not produced for
this host.`

## Windows collection

`playbooks/windows/build_verification.yml` targets `windows_hosts`. Both plays
use that group, so a Limit only narrows it. Blank Limit, `all`, and `*` are
allowed. Full Patch and Precheck still reject those Limits.

Play 1 does not gather facts. It runs the existing PowerShell query with a
120-second timeout. The script reads `Win32_OperatingSystem` for `Version` and
`BuildNumber`, and the UBR registry value under
`HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`. Native Windows facts do
not include UBR, so this query stays.

`success` requires a non-empty OS version and a numeric base build. A rescued
failure still produces a row, and the AAP job stays failed. Unreachable hosts
remain in the play. One bad host does not drop the others from the CSV.

## What Linux needs to match this report

Linux collection is owned by another consultant. This repository already has
a Linux playbook that includes the shared report tasks. Its record task does
not yet read `cmdb_fqdn` or `cmdb_os_release`. To produce the same CSV, a
Linux run needs one `build_verification_record` per host and then the same
include:

`playbooks/build_verification/tasks/report.yml`

Set these play variables for the Linux job:

- `build_verify_platform: linux`
- `build_verify_build_kind: running_kernel`
- `build_verify_report_name: linux_build_verification_report`
- `build_verify_csv_name: linux_build_verification_csv`
- `build_verify_filename_prefix: linux-build-verification`
- `build_verify_subject_name: Linux`
- `build_verify_report_source: linux_build_verification`

Use the same inventory variables and the same missing-value rules. Put the
distribution version in `os_version` and the running kernel in
`current_build`. Set `current_build_kind` to `running_kernel` and `platform`
to `linux`. Include the report once, `run_once`, from a `connection: local`
play on the same `linux_hosts` selection. Do not create a second reporting
role. Do not reuse `roles/patch_report` or `roles/report_email`.

## AAP and SMTP delivery

Job template: `Windows - Build Verification`.

| Setting | Value |
| --- | --- |
| Playbook | `playbooks/windows/build_verification.yml` |
| Inventory | One of LAB, IST, UAT, or PROD |
| Credential | Existing WinRM credential |
| Execution environment | Windows patching EE |
| Limit | Optional |
| Job slicing | `1` |

AAP artifacts, from `set_stats`:

- `windows_build_verification_report`
- `windows_build_verification_csv`

The CSV file is written on the execution environment under
`/tmp/aap-build-verification`. It is not written on the Windows host.

Email is off unless `report_email_enabled` is true. The mail tasks load only
then. One message is sent per job. Empty SMTP settings fail that job after
the CSV artifact exists. The variables are `report_email_smtp_host`,
`report_email_smtp_port` (`25`), `report_email_smtp_secure` (`never` for the
internal relay), `report_email_from`, `report_email_to`,
`report_email_attach_csv`, and `report_email_fail_on_error`.

Still required from the client before a production run: the CMDB-to-inventory
mapping, the job template if it has not been created, and SMTP values when
email is wanted. Controller CaC in this repository does not declare the
build-verification job template.
