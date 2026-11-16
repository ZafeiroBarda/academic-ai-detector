#!/usr/bin/env bash
# AI Content Detector — εκκίνηση (Linux / Mac / WSL)
# Η κύρια λογική είναι στο launcher.py· εδώ μόνο βρίσκουμε Python και venv.
set -euo pipefail
cd "$(dirname "$0")"

echo
echo " AI Content Detector"
echo " ================================"
echo

if [ ! -x "venv/bin/python" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo " ❌ Δεν βρέθηκε Python 3 (Python 3 not found): https://www.python.org/downloads/"
        exit 1
    fi
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
        echo " ❌ Χρειάζεται Python 3.10+ (Python 3.10+ is required)"
        exit 1
    fi
    echo " 📦 Προετοιμασία — μόνο την πρώτη φορά…"
    python3 -m venv venv
fi

exec venv/bin/python launcher.py "$@"
