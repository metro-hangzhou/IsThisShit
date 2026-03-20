param(
    [string]$RepoPath = ".",
    [string]$LauncherPath = "",
    [string]$QuickLoginUin = ""
)

$ErrorActionPreference = "Stop"

function Get-RepoScopedNapCatProcesses {
    param(
        [string]$RepoLower
    )

    try {
        $processes = @(Get-CimInstance Win32_Process)
    } catch {
        return @()
    }

    $processes | Where-Object {
        $name = [string]$_.Name
        $cmd = [string]$_.CommandLine
        if (-not $name) {
            return $false
        }
        if ($cmd -and $cmd.ToLowerInvariant().Contains($RepoLower)) {
            return (
                $name -match '^(cmd|powershell|pwsh|NapCatWinBootMain)\.exe$' -or
                $cmd -match 'start_napcat_logged|launcher-win10|NapCatWinBootMain|loadNapCat'
            )
        }
        if ($name -ieq "QQ.exe" -and $cmd -and $cmd -match '--enable-logging') {
            return $true
        }
        return $false
    }
}

$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$repoLower = $repo.ToLowerInvariant()
$launcher = if ($LauncherPath) { (Resolve-Path -LiteralPath $LauncherPath).Path } else { $null }

$targets = @(Get-RepoScopedNapCatProcesses -RepoLower $repoLower)
$stopped = @()
foreach ($target in $targets) {
    try {
        Stop-Process -Id $target.ProcessId -Force -ErrorAction Stop
        $stopped += [string]$target.ProcessId
    } catch {
    }
}

Start-Sleep -Milliseconds 800

if (-not $launcher) {
    Write-Output "launcher_started=0"
    Write-Output ("stopped_count=" + $stopped.Count)
    Write-Output ("stopped_pids=" + ($stopped -join ","))
    exit 0
}

if ($QuickLoginUin) {
    $env:NAPCAT_QUICK_ACCOUNT = $QuickLoginUin
    $env:NAPCAT_QUICK_LOGIN_UIN = $QuickLoginUin
}

$launcherDir = Split-Path -Parent $launcher
Start-Process -FilePath $launcher -WorkingDirectory $launcherDir | Out-Null

Write-Output "launcher_started=1"
Write-Output ("launcher_path=" + $launcher)
Write-Output ("quick_login_uin=" + $QuickLoginUin)
Write-Output ("stopped_count=" + $stopped.Count)
Write-Output ("stopped_pids=" + ($stopped -join ","))
