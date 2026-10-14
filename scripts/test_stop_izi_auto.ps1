$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

# Synthetic process inventory: this test never queries or stops real processes.
function Get-CimInstance {
    param($ClassName)
    @(
        [pscustomobject]@{ProcessId=101; Name='python.exe'; ExecutablePath="$projectRoot\venv\Scripts\python.exe"; CommandLine='python.exe -u pianos\automation\monitor.py'; CreationDate='test'},
        [pscustomobject]@{ProcessId=105; ParentProcessId=101; Name='python.exe'; ExecutablePath='C:\Python\python.exe'; CommandLine='python.exe -u pianos\automation\monitor.py'; CreationDate='test'},
        [pscustomobject]@{ProcessId=102; Name='python.exe'; ExecutablePath="$projectRoot\venv\Scripts\python.exe"; CommandLine='python.exe manage.py runserver 127.0.0.1:8000 --noreload'; CreationDate='test'},
        [pscustomobject]@{ProcessId=103; Name='electron.exe'; ExecutablePath="$projectRoot\electron\node_modules\electron\dist\electron.exe"; CommandLine='electron .'; CreationDate='test'},
        [pscustomobject]@{ProcessId=104; Name='node.exe'; ExecutablePath='C:\node\node.exe'; CommandLine="node `"$projectRoot\frontend\node_modules\vite\bin\vite.js`""; CreationDate='test'},
        [pscustomobject]@{ProcessId=901; Name='python.exe'; ExecutablePath='C:\Other\python.exe'; CommandLine='python monitor.py'; CreationDate='test'},
        [pscustomobject]@{ProcessId=902; Name='electron.exe'; ExecutablePath='C:\Other\electron.exe'; CommandLine='electron .'; CreationDate='test'},
        [pscustomobject]@{ProcessId=903; Name='python.exe'; ExecutablePath="$projectRoot\venv\Scripts\python.exe"; CommandLine='python unrelated.py'; CreationDate='test'},
        [pscustomobject]@{ProcessId=904; Name='chrome.exe'; ExecutablePath='C:\Chrome\chrome.exe'; CommandLine='chrome --remote-debugging-port=9222'; CreationDate='test'},
        [pscustomobject]@{ProcessId=905; Name='node.exe'; ExecutablePath='C:\node\node.exe'; CommandLine='node C:\Other\frontend\node_modules\vite\bin\vite.js'; CreationDate='test'}
    )
}
function Stop-Process { throw 'Test must never stop processes' }

$result = (& "$PSScriptRoot\stop_izi_auto.ps1" -Preview | Out-String)
foreach ($expected in 101,102,103,104,105) {
    if ($result -notmatch "\b$expected\b") { throw "Missing IZI process $expected" }
}
foreach ($excluded in 901,902,903,904,905) {
    if ($result -match "\b$excluded\b") { throw "Unrelated process selected: $excluded" }
}
Write-Host 'PASS: app processes selected; unrelated Python, Electron, Vite and Chrome excluded.'
