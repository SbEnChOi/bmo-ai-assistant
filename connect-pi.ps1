param(
    [string]$PiHost = '192.168.1.50',
    [string]$PiUser = 'pi-user',
    [string]$HostKeyAlias = '192.168.1.50',
    [ValidateRange(1,65535)][int]$Port = 8775
)
$ErrorActionPreference = 'Stop'
$bmoKey = Join-Path $env:USERPROFILE '.ssh/bmo_pi_ed25519'
if (-not (Test-Path -LiteralPath $bmoKey)) { throw "SSH key not found: $bmoKey" }
Write-Host "Pi PC manager: http://127.0.0.1:$Port/admin"
Write-Host "Pi face preview: http://127.0.0.1:$Port/phone"
Write-Host 'Keep this terminal open. Ctrl+C disconnects the tunnel.'
& ssh -i $bmoKey -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o "HostKeyAlias=$HostKeyAlias" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -N -L "127.0.0.1:${Port}:127.0.0.1:8765" "${PiUser}@${PiHost}"
if ($LASTEXITCODE -ne 0) { throw 'SSH tunnel failed. Check the wired/Wi-Fi address and whether the port is already in use.' }
