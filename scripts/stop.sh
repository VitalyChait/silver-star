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

echo "Stopping Silver Star application..."

# Kill backend if PID file exists
if [ -f "$LOG_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$LOG_DIR/backend.pid")
    if ps -p $BACKEND_PID > /dev/null; then
        kill $BACKEND_PID
        echo "Backend server stopped"
    fi
    rm "$LOG_DIR/backend.pid"
fi

# Kill frontend if PID file exists
if [ -f "$LOG_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$LOG_DIR/frontend.pid")
    if ps -p $FRONTEND_PID > /dev/null; then
        kill $FRONTEND_PID
        echo "Frontend server stopped"
    fi
    rm "$LOG_DIR/frontend.pid"
fi

# Also kill any remaining processes
pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
pkill -f "next.*dev" 2>/dev/null || true
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true

echo "Silver Star application stopped"
