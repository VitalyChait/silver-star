#!/bin/bash
# Resolve important paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname $SCRIPT_DIR)"
LOG_DIR="$REPO_DIR/logs"

ENV_FILE="$REPO_DIR/code/.env"

# Simple colored log helpers
print_status() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_status "Loading environment variables from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a
print_success "Environment variables loaded"

# Default ports
DEFAULT_FRONTEND_PORT=$NODE_APP_PORT
DEFAULT_BACKEND_PORT=$PYTHON_APP_PORT

# Get current ports or use defaults (prefer env, fall back to files if present)
FRONTEND_PORT=${NODE_APP_PORT}
BACKEND_PORT=${PYTHON_APP_PORT}
if [ -f "$LOG_DIR/.frontend_port" ]; then FRONTEND_PORT=$(cat "$LOG_DIR/.frontend_port" 2>/dev/null || echo "$FRONTEND_PORT"); fi
if [ -f "$LOG_DIR/.backend_port" ]; then BACKEND_PORT=$(cat "$LOG_DIR/.backend_port" 2>/dev/null || echo "$BACKEND_PORT"); fi

echo "Silver Star Application Status"
echo "=============================="

# Check backend
if [ -f "$LOG_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$LOG_DIR/backend.pid")
    if ps -p $BACKEND_PID > /dev/null; then
        echo "Backend: RUNNING (PID $BACKEND_PID, Port $BACKEND_PORT)"
    else
        echo "Backend: NOT RUNNING (stale PID file)"
    fi
else
    if lsof -ti:$BACKEND_PORT >/dev/null 2>&1; then
        echo "Backend: RUNNING on port $BACKEND_PORT (unknown PID)"
    else
        echo "Backend: NOT RUNNING"
    fi
fi

# Check frontend
if [ -f "$LOG_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$LOG_DIR/frontend.pid")
    if ps -p $FRONTEND_PID > /dev/null; then
        echo "Frontend: RUNNING (PID $FRONTEND_PID, Port $FRONTEND_PORT)"
    else
        echo "Frontend: NOT RUNNING (stale PID file)"
    fi
else
    if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
        echo "Frontend: RUNNING on port $FRONTEND_PORT (unknown PID)"
    else
        echo "Frontend: NOT RUNNING"
    fi
fi

echo ""
echo "Recent log entries:"
echo "-------------------"
echo "Backend (last 5 lines):"
tail -n 5 "$LOG_DIR/backend.log" 2>/dev/null || echo "No backend log found"
echo ""
echo "Frontend (last 5 lines):"
tail -n 5 "$LOG_DIR/frontend.log" 2>/dev/null || echo "No frontend log found"
