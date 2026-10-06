$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& ".\.venv\Scripts\streamlit.exe" run "predikpedia.py" --server.address 127.0.0.1
