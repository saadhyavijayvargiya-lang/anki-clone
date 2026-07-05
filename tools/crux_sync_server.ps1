# Crux self-hosted Anki sync server.
# Lets the desktop app and AnkiDroid sync the same collection through Anki's own
# (shared Rust) sync, with no AnkiWeb account. Run this, then point both apps at
# it (see SYNC_SETUP.md).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$env:PYTHONPATH = "$root\out\pylib;$root\pylib"
$env:SYNC_USER1 = "crux:crux"          # username:password used by both apps
$env:SYNC_HOST = "0.0.0.0"             # bind on all interfaces so the phone can reach it
$env:SYNC_PORT = "8080"
$env:SYNC_BASE = "$root\sync_server_data"
$env:RUST_LOG = "anki=info"
New-Item -ItemType Directory -Force -Path $env:SYNC_BASE | Out-Null

# Prefer a real LAN address (192.168.x / 10.x), not virtual adapters (172.x WSL/Hyper-V).
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { ($_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*") -and $_.IPAddress -notlike "10.0.2.*" } |
    Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $ip) { $ip = "<run ipconfig for your LAN IP>" }

Write-Host "Crux sync server starting on http://0.0.0.0:$($env:SYNC_PORT)/"
Write-Host "  user: crux   pass: crux"
Write-Host "  Desktop  -> Preferences > Syncing > Self-hosted sync server: http://$ip`:8080/"
Write-Host "  Emulator -> AnkiDroid Settings > Advanced > Custom sync server: http://10.0.2.2:8080/"
Write-Host "  Real phone (same wifi) -> http://$ip`:8080/"
Write-Host ""

& "$root\out\pyenv\Scripts\python.exe" -m anki.syncserver
