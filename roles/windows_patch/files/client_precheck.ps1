# Client PowerShell precheck stub.
# Returns a structured object for Ansible consumption. No secrets printed.
# Replace this file with the approved client PowerShell precheck before enabling
# windows_powershell_precheck_enabled=true in production.

[PSCustomObject]@{
    overall_health  = 'failed'
    critical_failed = $true
    failed_checks   = @('Approved client PowerShell precheck has not yet been installed')
    warnings        = @('client_precheck.ps1 is a fail-closed stub until replaced with the approved client script')
}
