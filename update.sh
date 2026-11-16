#!/usr/bin/env bash
# AI Content Detector — μεταφορά ρυθμίσεων/δεδομένων από παλιό φάκελο (ή git pull)
set -euo pipefail
cd "$(dirname "$0")"
PY=python3
[ -x venv/bin/python ] && PY=venv/bin/python
exec "$PY" tools/update.py "$@"
