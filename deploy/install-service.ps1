<#
.SYNOPSIS
    Installs the Faculty Evaluation app (serve.py / Waitress) as a Windows service using NSSM.

.EXAMPLE
    # From an elevated PowerShell, in the project folder:
    .\deploy\install-service.ps1 -Nssm C:\tools\nssm\win64\nssm.exe -DependsOn postgresql-x64-17
#>
param(
    [Parameter(Mandatory)] [string] $Nssm,           # path to nssm.exe (https://nssm.cc/download)
    [string] $ServiceName = "FacultyEvaluation",
    [string] $DependsOn = ""                         # e.g. postgresql-x64-17, so the DB starts first
)
$ErrorActionPreference = "Stop"

$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project ".venv\Scripts\python.exe"
$logs = Join-Path $project "logs"

if (-not (Test-Path $python)) { throw "Missing $python - create the venv first (see README.md)." }
if (-not (Test-Path (Join-Path $project ".env"))) { throw "Missing .env - copy .env.example to .env and fill it in." }
New-Item -ItemType Directory -Force $logs | Out-Null

& $Nssm install $ServiceName $python "serve.py"
& $Nssm set $ServiceName AppDirectory $project
& $Nssm set $ServiceName DisplayName "Faculty Evaluation (Waitress)"
& $Nssm set $ServiceName Start SERVICE_AUTO_START
& $Nssm set $ServiceName AppStdout (Join-Path $logs "waitress.log")
& $Nssm set $ServiceName AppStderr (Join-Path $logs "waitress.log")
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppRotateOnline 1
& $Nssm set $ServiceName AppRotateBytes 10485760
& $Nssm set $ServiceName AppExit Default Restart
if ($DependsOn) { & $Nssm set $ServiceName DependOnService $DependsOn }

& $Nssm start $ServiceName
Get-Service $ServiceName
