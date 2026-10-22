param(
    [ValidateSet('openai','claude')][string]$Provider = 'openai',
    [string]$Model = '',
    [string]$RealtimeModel = 'gpt-realtime-2.1',
    [ValidateSet('realtime','live')][string]$DialogueMode = 'realtime',
    [string]$PythonPath = '',
    [switch]$RequirePairing,
    [ValidateRange(1,65525)][int]$Port = 8765,
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
Set-Location -LiteralPath $PSScriptRoot
$bindAddress = [System.Net.IPAddress]::Loopback
if ($LanIP) {
    $parsedAddress = [System.Net.IPAddress]::Parse($LanIP)
    $localAddresses = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
        ForEach-Object { $_.GetIPProperties().UnicastAddresses.Address.IPAddressToString }
    if ($parsedAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or $LanIP -notin $localAddresses) {
        throw 'LanIP must be the Wi-Fi IPv4 address assigned to this PC.'
    }
    $bindAddress = [System.Net.IPAddress]::Any
}
    $cameraArgs = @()
    $connectionArgs = @()
    if (-not $RequirePairing) { $connectionArgs = @('--auto-connect') }
    if ($PiCamera -and $ImagePath) { throw 'Choose PiCamera or ImagePath, not both.' }
    if ($PiCamera) {
        if (-not $PiKey) { $PiKey = Join-Path $env:USERPROFILE '.ssh/bmo_pi_ed25519' }
        $cameraArgs = @('--source','ssh-pi','--scene-mode','camera','--pi-host',$PiHost,'--pi-user',$PiUser,'--pi-key',$PiKey,'--pi-project',$PiProject)
    }
    if ($ImagePath) {
        if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
            throw 'ImagePath file not found. Choose an existing JPG or PNG photo.'
        }
        $cameraArgs = @('--source', 'image', '--image', (Resolve-Path -LiteralPath $ImagePath).Path)
    }
    if ($Provider -eq 'claude') {
        if (-not $Model) { $Model = $env:ANTHROPIC_MODEL }
        if (-not $Model) { $Model = Read-Host 'Claude model ID available in your account' }
    } elseif (-not $Model) {
        $Model = $env:OPENAI_MODEL
        if (-not $Model) { $Model = 'gpt-4.1-mini' }
    }
    $selectedPort = $null
    foreach ($candidate in $Port..($Port + 10)) {
        if ($LanIP -and $candidate -eq $SetupPort) { continue }
        $probe = $null
        try {
            $probe = [System.Net.Sockets.TcpListener]::new($bindAddress, $candidate)
            $probe.Server.ExclusiveAddressUse = $true
            $probe.Start()
            $selectedPort = $candidate
            break
        } catch [System.Net.Sockets.SocketException] {
            # The port is already in use. Try the next local port.
        } finally {
            if ($probe) { $probe.Stop() }
        }
    }
    if (-not $selectedPort) { throw "No available local port between $Port and $($Port + 10)." }
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $pythonPrefix = @()
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'PythonPath file not found.' }
        $pythonCommand = (Resolve-Path -LiteralPath $PythonPath).Path
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonCommand = 'py'
        $pythonPrefix = @('-3')
    } elseif (Test-Path -LiteralPath $bundledPython) {
        $pythonCommand = $bundledPython
    } else { throw 'Python 3.10 or later is required.' }
    if ($DialogueMode -eq 'live') {
        if ($Provider -ne 'openai') { throw 'GPT-Live-1 requires the OpenAI provider.' }
        & $pythonCommand @pythonPrefix -c 'import websocket'
        if ($LASTEXITCODE -ne 0) { throw 'Install the Live dependency in this Python environment: python -m pip install -r requirements-live.txt' }
    }
    if ($LanIP) {
        & $pythonCommand @pythonPrefix -m bmo.lan --address $LanIP --prepare-only
        if ($LASTEXITCODE -ne 0) { throw 'Could not prepare BMO HTTPS certificates.' }
        $certDirectory = Join-Path $PSScriptRoot 'certs'
        $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls $certDirectory '/inheritance:r' '/grant:r' "$($account):(OI)(CI)F" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not restrict access to BMO certificate private keys.' }
        $caPath = Join-Path $certDirectory 'rootCA.cer'
        $ca = [Security.Cryptography.X509Certificates.X509Certificate2]::new($caPath)
        $store = [Security.Cryptography.X509Certificates.X509Store]::new('Root', [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
        try {
            $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
            if (-not $store.Certificates.Find([Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $ca.Thumbprint, $false).Count) {
                Write-Host 'Trusting the BMO development certificate for this Windows user.'
                $store.Add($ca)
            }
        } finally { $store.Close() }
        Write-Host "PC manager: https://127.0.0.1:$selectedPort/admin"
        Write-Host "iPad setup (Safari): http://${LanIP}:$SetupPort/"
        Write-Host "BMO device (Chrome): https://${LanIP}:$selectedPort/phone"
        Write-Host "Firewall setup (administrator PowerShell): ./tools/allow-bmo-lan.ps1 -LanIP $LanIP -Port $selectedPort -SetupPort $SetupPort"
        & $pythonCommand @pythonPrefix -m bmo.lan --address $LanIP --setup-port $SetupPort --provider $Provider --model $Model --realtime-model $RealtimeModel --dialogue-mode $DialogueMode --port $selectedPort @cameraArgs @connectionArgs
    } else {
        Write-Host "PC manager: http://127.0.0.1:$selectedPort/admin"
        Write-Host "Phone preview: http://127.0.0.1:$selectedPort/phone (Ctrl+C stops the server)"
        & $pythonCommand @pythonPrefix -m bmo.app --provider $Provider --model $Model --realtime-model $RealtimeModel --dialogue-mode $DialogueMode --port $selectedPort @cameraArgs @connectionArgs
    }
