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
cd "$REPO"
exec "$BASE/venv/bin/python" web/app.py --host 0.0.0.0 --port 8088 --server waitress
