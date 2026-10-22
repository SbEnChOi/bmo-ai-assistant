#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory=$true)][string]$LanIP,
    [ValidateRange(1,65535)][int]$Port = 8766,
    [ValidateRange(1,65535)][int]$SetupPort = 8767,
    [string]$PythonPath = ''
)
$ErrorActionPreference = 'Stop'
$address = [System.Net.IPAddress]::Parse($LanIP)
if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
    -not (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $LanIP -ErrorAction SilentlyContinue)) {
    throw 'LanIP must be an IPv4 address assigned to this PC.'
}
if ($Port -eq $SetupPort) { throw 'The HTTPS and setup ports must differ.' }
if (-not $PythonPath) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { throw 'Start the BMO HTTPS server before configuring its firewall rule.' }
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if ($serverProcess.CommandLine -notmatch '\-m\s+bmo\.lan(?:\s|$)') {
        throw 'The selected port is not owned by the BMO LAN server. Supply its PythonPath explicitly.'
    }
    $PythonPath = $serverProcess.ExecutablePath
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
$ruleName = 'BMO-LAN-Access'
$ruleGroup = 'BMO local development'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing -and $existing.Group -ne $ruleGroup) { throw 'An unrelated firewall rule uses the BMO rule name.' }
if ($existing) { $existing | Remove-NetFirewallRule }
New-NetFirewallRule -Name $ruleName -DisplayName 'BMO LAN HTTPS and certificate setup' -Group $ruleGroup `
    -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $LanIP -LocalPort @($Port,$SetupPort) `
    -RemoteAddress LocalSubnet -Profile Any -Program $PythonPath | Out-Null
Write-Host "BMO access enabled only from the local subnet to $LanIP ports $Port and $SetupPort."
