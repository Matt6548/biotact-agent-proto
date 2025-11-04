param([string]$cmd="run")
$ErrorActionPreference="Stop"
$python = ".\.venv\Scripts\python.exe"

switch ($cmd) {
 "run"     { & $python -X utf8 -m uvicorn server_unified:app --host 127.0.0.1 --port 18080 --reload }
 "lint"    { ruff check . ; black --check . }
 "fmt"     { ruff check . --fix ; black . }
 "test"    { pytest }
 "health"  { Invoke-RestMethod http://127.0.0.1:18080/health | ConvertTo-Json -Depth 3 | Write-Host }
 default   { Write-Host "use: .\scripts\dev.ps1 [run|lint|fmt|test|health]" }
}
