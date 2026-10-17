@echo off
rem Launcher: keeps the (multi-GB) venv outside OneDrive, then runs the CLI.
set "UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\tonematch\venv"
uv run --project "%~dp0." tonematch %*
