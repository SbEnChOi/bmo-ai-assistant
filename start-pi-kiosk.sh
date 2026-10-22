#!/usr/bin/env bash
# Run the existing cloud-backed BMO web app on the Pi's own LCD.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo 'Start this script inside the Raspberry Pi desktop session.' >&2
  exit 1
fi
profile_dir="${XDG_DATA_HOME:-$HOME/.local/share}/bmo/chromium"
lock_dir="${XDG_CACHE_HOME:-$HOME/.cache}/bmo"
mkdir -p -- "$profile_dir" "$lock_dir"
exec 9>"$lock_dir/kiosk.lock"
flock -n 9 || exit 0

systemctl --user start bmo.service
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if curl --silent --fail --max-time 2 http://127.0.0.1:8765/phone >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if ((!ready)); then
  echo 'BMO server is unavailable. Check systemctl --user status bmo.service.' >&2
  exit 1
fi
if [[ -n "${DISPLAY:-}" ]] && command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi
chromium --kiosk --no-first-run --noerrdialogs --password-store=basic \
  --disable-session-crashed-bubble --user-data-dir="$profile_dir" \
  http://127.0.0.1:8765/phone
