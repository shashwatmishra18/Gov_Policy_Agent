param([ValidateSet('prepare','check','local-check','start','status','stop')][string]$Action='check')
$ErrorActionPreference='Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & .\.venv\Scripts\python.exe backend\demo.py $Action
    if ($LASTEXITCODE -ne 0) { throw 'Demo operation failed; see docs/SETUP.md.' }
} finally { Pop-Location }
