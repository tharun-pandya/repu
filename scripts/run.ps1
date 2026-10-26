# Windows: .\scripts\run.ps1   (creates venv, installs deps, checks Ollama, starts Repu on 127.0.0.1:8000)
$ErrorActionPreference = "Stop"
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install -q -r requirements.txt
$model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "gemma3:4b" }
try { $null = Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 }
catch { Write-Warning "Ollama is not running. Install from https://ollama.com, then: ollama pull $model" }
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
