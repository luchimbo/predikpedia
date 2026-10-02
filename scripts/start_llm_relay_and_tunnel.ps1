[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "No se encontró el Python del venv: $python" }
if (-not (Test-Path -LiteralPath (Join-Path $root '.env.relay.local'))) {
    throw 'Falta .env.relay.local. Copiá .env.relay.example y cargá tus secretos locales.'
}
& $python (Join-Path $root 'tools\supervise_quick_tunnel.py')
