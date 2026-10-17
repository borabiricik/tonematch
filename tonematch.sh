#!/usr/bin/env sh
# Launcher (macOS / Linux): keeps the (multi-GB) venv out of iCloud/OneDrive, then runs the CLI.
case "$(uname)" in
  Darwin) export UV_PROJECT_ENVIRONMENT="$HOME/Library/Application Support/tonematch/venv" ;;
  *)      export UV_PROJECT_ENVIRONMENT="$HOME/.local/share/tonematch/venv" ;;
esac
exec uv run --project "$(dirname "$0")" tonematch "$@"
