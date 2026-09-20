#!/usr/bin/env bash
# One-command launcher for EVGuard (macOS / Linux; also works in Git Bash on Windows).
#
#   ./run.sh                 start backend + dashboard
#   ./run.sh --no-dashboard  start the backend, check /health, then stop (smoke test)
#   EVGUARD_NO_BROWSER=1     do not open a browser;  EVGUARD_PORT=n  backend port (default 8000)
#
# Creates .venv if missing, installs requirements.txt, starts the backend on
# http://127.0.0.1:8000, waits for /health, starts the dashboard on
# http://127.0.0.1:8501 and stops the backend when the dashboard exits.

set -u
cd "$(dirname "$0")"

HOST=127.0.0.1
BACKEND_PORT="${EVGUARD_PORT:-8000}"
DASHBOARD_PORT=8501
HEALTH_URL="http://${HOST}:${BACKEND_PORT}/health"
LOG_FILE="evguard-backend.log"
NO_DASHBOARD=0
[ "${1:-}" = "--no-dashboard" ] && NO_DASHBOARD=1

fail() {
    echo ""
    echo "ERROR: $1" >&2
    exit 1
}

# ---- 1. Find Python 3.11 / 3.12 ---------------------------------------------
find_python() {
    for candidate in python3.12 python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            version=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
            if [ "$version" = "3.12" ] || [ "$version" = "3.11" ]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if [ -x .venv/bin/python ]; then
    VENV_PY=.venv/bin/python
elif [ -x .venv/Scripts/python.exe ]; then
    VENV_PY=.venv/Scripts/python.exe
else
    PY=$(find_python) || fail "Python 3.11 or 3.12 was not found. Install Python 3.12 (https://www.python.org/downloads/, or 'brew install python@3.12' / 'sudo apt install python3.12 python3.12-venv'), then run ./run.sh again."
    echo "Creating virtual environment (.venv)..."
    "$PY" -m venv .venv || fail "Could not create .venv (on Debian/Ubuntu install python3-venv)."
    if [ -x .venv/bin/python ]; then VENV_PY=.venv/bin/python; else VENV_PY=.venv/Scripts/python.exe; fi
fi

# ---- 2. Install dependencies -------------------------------------------------
echo "Installing requirements (first run can take a minute)..."
"$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements.txt \
    || fail "pip install failed. Check your internet connection and try again."

# ---- 3. Start the backend ------------------------------------------------------
export EVGUARD_MOCK=0
export EVGUARD_API_URL="http://${HOST}:${BACKEND_PORT}"

health_ok() {
    "$VENV_PY" - "$HEALTH_URL" <<'PY' >/dev/null 2>&1
import json, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=2) as r:
    sys.exit(0 if json.load(r).get("status") == "ok" else 1)
PY
}

BACKEND_PID=""
DASHBOARD_PID=""
cleanup() {
    if [ -n "$DASHBOARD_PID" ] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        kill "$DASHBOARD_PID" 2>/dev/null
        wait "$DASHBOARD_PID" 2>/dev/null
    fi
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "Stopping EVGuard backend..."
        kill "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if health_ok; then
    echo "An EVGuard backend is already running on port ${BACKEND_PORT}; reusing it."
else
    echo "Starting EVGuard backend..."
    "$VENV_PY" -m uvicorn backend.main:app --host "$HOST" --port "$BACKEND_PORT" >"$LOG_FILE" 2>&1 &
    BACKEND_PID=$!

    ready=0
    for _ in $(seq 1 60); do
        kill -0 "$BACKEND_PID" 2>/dev/null || break
        if health_ok; then ready=1; break; fi
        sleep 0.5
    done
    if [ "$ready" -ne 1 ]; then
        echo "--- last lines of $LOG_FILE ---" >&2
        tail -n 15 "$LOG_FILE" >&2
        fail "The backend did not answer ${HEALTH_URL} within 30 seconds (full log: $LOG_FILE)."
    fi
fi
echo "Backend is healthy: ${HEALTH_URL}"

if [ "$NO_DASHBOARD" -eq 1 ]; then
    echo "--no-dashboard given: backend check passed."
    exit 0
fi

# ---- 4. Start the dashboard -------------------------------------------------
# Headless: no first-run email prompt. We open the browser ourselves below.
DASHBOARD_URL="http://${HOST}:${DASHBOARD_PORT}"
echo "Starting EVGuard dashboard..."
"$VENV_PY" -m streamlit run dashboard/app.py \
    --server.address "$HOST" --server.port "$DASHBOARD_PORT" --server.headless true &
DASHBOARD_PID=$!

dashboard_up() {
    "$VENV_PY" - "$DASHBOARD_URL/_stcore/health" <<'PY' >/dev/null 2>&1
import sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=2) as r:
    sys.exit(0 if r.read().strip() == b"ok" else 1)
PY
}

up=0
for _ in $(seq 1 60); do
    kill -0 "$DASHBOARD_PID" 2>/dev/null || break
    if dashboard_up; then up=1; break; fi
    sleep 0.5
done
[ "$up" -eq 1 ] || fail "The dashboard did not start on port ${DASHBOARD_PORT} (is another program using it?)."

echo "Open ${DASHBOARD_URL}"
if [ "${EVGUARD_NO_BROWSER:-0}" != "1" ]; then
    if command -v open >/dev/null 2>&1; then
        open "$DASHBOARD_URL" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$DASHBOARD_URL" >/dev/null 2>&1 || echo "(Could not open a browser automatically; open the URL above.)"
    elif command -v cmd.exe >/dev/null 2>&1; then
        cmd.exe /c start "" "$DASHBOARD_URL" >/dev/null 2>&1 || true
    else
        echo "(No browser opener found; open the URL above.)"
    fi
fi
echo "Press Ctrl+C here to stop EVGuard."
wait "$DASHBOARD_PID"
