param([switch]$Preview)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot 'venv\Scripts\python.exe'
$electronPath = Join-Path $projectRoot 'electron\node_modules\electron\dist\electron.exe'
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\'
$runtimePath = Join-Path $projectRoot '.runtime'

function Get-IziProcesses {
    # Never select by executable name or port alone.
    $inventory = @(Get-CimInstance Win32_Process)
    $pythonLaunchers = @($inventory | Where-Object { $_.ExecutablePath -ieq $pythonPath } |
        ForEach-Object { $_.ProcessId })
    foreach ($item in $inventory) {
        $command = [string]$item.CommandLine
        $kind = $null
        # Windows venv may launch the base interpreter as a direct child.
        if ($item.ExecutablePath -ieq $pythonPath -or
            ($item.Name -ieq 'python.exe' -and $pythonLaunchers -contains $item.ParentProcessId)) {
            if ($command -match 'pianos[\\/]automation[\\/]monitor\.py(?:"|\s|$)') {
                $kind = 'Monitor'
            } elseif ($command -match 'manage\.py\s+runserver\s+127\.0\.0\.1:8000(?:\s|$)') {
                $kind = 'Backend'
            }
        } elseif ($item.ExecutablePath -ieq $electronPath) {
            $kind = 'Electron'
        } elseif ($item.Name -ieq 'node.exe' -and
                  $command.Replace('/', '\').IndexOf($vitePath, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $kind = 'Frontend'
        }
        if ($kind) {
            [pscustomobject]@{ Kind=$kind; ProcessId=$item.ProcessId; Created=$item.CreationDate }
        }
    }
}

$targets = @(Get-IziProcesses)
if ($Preview) {
    $targets | Format-Table Kind, ProcessId, Created
    Write-Host 'Preview only. No processes stopped.'
    exit 0
}

# Ask the monitor to finish its current cycle before stopping other services.
$monitors = @($targets | Where-Object Kind -eq 'Monitor')
if ($monitors.Count) {
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    foreach ($item in $monitors) {
        Set-Content -LiteralPath (Join-Path $runtimePath "stop-monitor-$($item.ProcessId)") -Value 'stop'
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        $remaining = @(Get-IziProcesses | Where-Object Kind -eq 'Monitor')
        if (-not $remaining.Count) { break }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($remaining.Count) {
        Write-Warning 'Monitor is still busy or uses older code. Services left running. Wait for completion; do not force-stop during a booking operation.'
        exit 1
    }
}

foreach ($kind in @('Electron', 'Frontend', 'Backend')) {
    foreach ($item in @($targets | Where-Object Kind -eq $kind)) {
        # Recheck identity to avoid stopping a reused PID.
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.ProcessId)"
        if (-not $current -or $current.CreationDate -ne $item.Created) { continue }
        if ($kind -eq 'Electron') {
            $process = Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
            if ($process -and $process.MainWindowHandle -ne 0) {
                [void]$process.CloseMainWindow()
                [void]$process.WaitForExit(5000)
            }
        }
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.ProcessId)"
        if ($current -and $current.CreationDate -eq $item.Created) {
            Stop-Process -Id $item.ProcessId -ErrorAction Stop
        }
        Write-Host "Stopped $kind PID $($item.ProcessId)"
    }
}
Write-Host 'IZI AUTO stopped. Chrome and unrelated applications were left running.'
