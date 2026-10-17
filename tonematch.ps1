# Launcher: keeps the (multi-GB) venv outside OneDrive, then runs the CLI.
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\tonematch\venv"
# PowerShell turns unquoted a,b into an array; join it back so `--only clean,rhythm` works
$cliArgs = $args | ForEach-Object { if ($_ -is [array]) { $_ -join ',' } else { $_ } }
uv run --project $PSScriptRoot tonematch @cliArgs
