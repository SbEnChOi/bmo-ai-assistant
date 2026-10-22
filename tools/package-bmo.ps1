param([string]$OutputPath = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $projectRoot 'BMO-PushToTalk-RPi5.zip' }
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
$temporaryPath = $OutputPath + '.building'
if (Test-Path -LiteralPath $temporaryPath) { throw "Temporary package already exists: $temporaryPath" }
Add-Type -AssemblyName System.IO.Compression
$files = @('README.md', 'BMO-HANDOFF.md', 'BMO-VERSIONS.md', 'BMO-OBSERVATION.md', 'BMO-EMOTIONS.md', 'BMO-REALTIME.md', 'BMO-HARDWARE.md', 'BMO-LIVE.md', 'BMO-LIVE-DESIGN.md', 'BMO-LIVE-PLAN.md', 'BMO-NETWORK.md', 'BMO-FINAL.md', 'BMO-FOCUS-PLAN.md', 'VALIDATION.md', 'PI-SETUP.md', 'requirements.txt', 'requirements-lan.txt', 'requirements-live.txt', 'start-assistant.ps1', 'start-live-noeul.ps1', 'start-demo.cmd', 'start-pi.sh', 'start-pi-live-noeul.sh', 'start-pi-kiosk.sh', 'connect-pi.ps1', 'tools/package-bmo.ps1', 'tools/pi_install.py', 'tools/update_pi.py', 'tools/configure_pi_camera.py', 'tools/configure_pi_display.py', 'tools/allow-bmo-lan.ps1', '.gitignore') |
    ForEach-Object { Get-Item -LiteralPath (Join-Path $projectRoot $_) }
$files += Get-ChildItem -LiteralPath (Join-Path $projectRoot 'bmo') -Recurse -File |
    Where-Object { $_.Extension -in '.py', '.html', '.css', '.js', '.jpg' -and $_.Name -ne 'private_config.py' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]' }
$files += Get-ChildItem -LiteralPath (Join-Path $projectRoot 'tests') -File |
    Where-Object { $_.Extension -in '.py', '.cjs' }
$stream = [IO.File]::Open($temporaryPath, [IO.FileMode]::CreateNew)
$archive = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($projectRoot.Length + 1).Replace('\', '/')
        $entry = $archive.CreateEntry('bmo-project/' + $relative)
        $entryStream = $entry.Open()
        try {
            if ($file.Extension -eq '.sh') {
                $bytes = [Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($file.FullName).Replace("`r`n", "`n"))
            } else { $bytes = [IO.File]::ReadAllBytes($file.FullName) }
            $entryStream.Write($bytes, 0, $bytes.Length)
        } finally { $entryStream.Dispose() }
    }
    $entry = $archive.CreateEntry('bmo-project/bmo/private_config.py')
    $entryStream = $entry.Open()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes("OPENAI_API_KEY = `"`"`nANTHROPIC_API_KEY = `"`"`n")
        $entryStream.Write($bytes, 0, $bytes.Length)
    } finally { $entryStream.Dispose() }
} finally { $archive.Dispose(); $stream.Dispose() }
Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force
Write-Output "Package: $OutputPath ($($files.Count + 1) files; blank API key template)"
