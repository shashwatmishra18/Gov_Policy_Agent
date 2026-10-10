param([ValidateSet('preflight','start','status','stop')][string]$Action='status',
    [ValidateSet('api','frontend','worker','index','rag')][string[]]$Services)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $operationArgs=@('backend\operate.py',$Action)
    if ($Services) { $operationArgs+=@('--services')+$Services }
    & .\.venv\Scripts\python.exe @operationArgs
    if ($LASTEXITCODE -ne 0) { throw 'Native operation failed; see docs/SETUP.md.' }
} finally { Pop-Location }
