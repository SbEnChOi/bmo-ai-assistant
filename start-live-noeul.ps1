param(
    [string]$Model = '',
    [string]$PythonPath = '',
    [switch]$RequirePairing,
    [ValidateRange(1,65525)][int]$Port = 8780,
    [string]$ImagePath = '',
    [string]$LanIP = '',
    [ValidateRange(1,65535)][int]$SetupPort = 8767,
    [switch]$PiCamera,
    [string]$PiHost = '192.168.1.50',
    [string]$PiUser = 'pi-user',
    [string]$PiKey = '',
    [string]$PiProject = '/home/pi-user/bmo-project'
)
$ErrorActionPreference = 'Stop'
if (-not $PythonPath) {
    $localPython = Join-Path $PSScriptRoot '.venv-live/Scripts/python.exe'
    if (Test-Path -LiteralPath $localPython) { $PSBoundParameters['PythonPath'] = $localPython }
}
$PSBoundParameters['Port'] = $Port
& (Join-Path $PSScriptRoot 'start-assistant.ps1') @PSBoundParameters -Provider openai -DialogueMode live
