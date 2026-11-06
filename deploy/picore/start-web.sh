#!/bin/sh
# Run as tc; filesystem must be mounted before startup.
set -eu
BASE=/mnt/mmcblk0p3/smoke-mesh
REPO="$BASE/app/smoke-listener-mesh"
ENV_FILE="$BASE/data/web.env"

if [ ! -r "$ENV_FILE" ]; then
  echo "Configuration missing: $ENV_FILE" >&2
  exit 1
fi
set -a
. "$ENV_FILE"
set +a
# piCore has no RTC; settime.sh may still be synchronizing after bootlocal.
# Avoid starting logging/SQLite with a 1970 timestamp.
attempt=0
while [ "$(date -u +%Y)" -lt 2026 ]; do
  if [ "$attempt" -ge 120 ]; then
    echo "ERROR: system clock not synchronized after 120s; Smoke Mesh not started" >&2
    exit 1
  fi
  if [ "$attempt" -eq 0 ]; then
    echo "Waiting for valid system time before starting Smoke Mesh" >&2
  fi
  attempt=$((attempt + 1))
  sleep 1
done
echo "Clock ready: $(date)" >&2

cd "$REPO"
exec "$BASE/venv/bin/python" web/app.py --host 0.0.0.0 --port 8088 --server waitress
