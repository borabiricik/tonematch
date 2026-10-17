# Start the desktop app (Windows): `dev.ps1` = dev mode, `dev.ps1 build` = installer. Rust output stays out of OneDrive.
$env:CARGO_TARGET_DIR = "$env:LOCALAPPDATA\tonematch\desktop-target"
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:ProgramFiles\nodejs;$env:Path"
Set-Location $PSScriptRoot
if (-not (Test-Path node_modules)) { npm install }
$tauriArgs = @(if ($args.Count -gt 0) { $args } else { "dev" })
npm run tauri -- @tauriArgs
