# One-command local automation (Windows PowerShell).
#   .\run_pipeline.ps1                 # full: build + evaluate published agents + report
#   .\run_pipeline.ps1 -Predictions my_agent.jsonl   # also score your own agent's patches
param([string]$Predictions = "", [switch]$ReusePool)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
python -m pip install -q -r requirements.txt
python -m pytest -q tests
if ($ReusePool) { python -m agentbench build --reuse-pool } else { python -m agentbench build }
if ($Predictions) {
    python -m agentbench evaluate --published --predictions $Predictions
} else {
    python -m agentbench evaluate --published
}
python -m agentbench report
Write-Host "Done. See dataset/DATASHEET.md and reports/RESULTS.md"
