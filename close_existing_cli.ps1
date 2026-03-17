param(
    [string]$RepoPath = "."
)

$ErrorActionPreference = "Stop"

try {
    $repo = (Resolve-Path -LiteralPath $RepoPath).Path.ToLowerInvariant()
} catch {
    Write-Output 0
    exit 0
}

$targets = @(
    Get-CimInstance Win32_Process | Where-Object {
        $cmd = [string]$_.CommandLine
        $name = [string]$_.Name
        $cmd -and
        $cmd.ToLowerInvariant().Contains($repo) -and
        $cmd -match "(^|[ '""=])app\.py([ '""$]|$)" -and
        $name -match "^(python|py)(w)?\.exe$"
    }
)

foreach ($target in $targets) {
    try {
        Stop-Process -Id $target.ProcessId -Force -ErrorAction Stop
    } catch {
    }
}

Write-Output (($targets | Measure-Object).Count)
