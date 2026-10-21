#!/usr/bin/env sh
# Start the desktop app in dev mode (macOS / Linux). Rust build output stays out of iCloud/OneDrive.
set -e
cd "$(dirname "$0")"
case "$(uname)" in
  Darwin) export CARGO_TARGET_DIR="$HOME/Library/Caches/tonematch/desktop-target" ;;
  *)      export CARGO_TARGET_DIR="$HOME/.cache/tonematch/desktop-target" ;;
esac
[ -d node_modules ] || npm install
[ $# -gt 0 ] || set -- dev
npm run tauri -- "$@"
