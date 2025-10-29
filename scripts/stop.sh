#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd "$SCRIPT_DIR" && pwd)"
REPO_DIR="$(dirname $SCRIPT_DIR)"
LOG_DIR="$REPO_DIR/logs"

# Default ports
DEFAULT_FRONTEND_PORT=3000
DEFAULT_BACKEND_PORT=8000

# Get current ports or use defaults
FRONTEND_PORT=$(cat "$LOG_DIR/.frontend_port" 2>/dev/null || echo "$DEFAULT_FRONTEND_PORT")
BACKEND_PORT=$(cat "$LOG_DIR/.backend_port" 2>/dev/null || echo "$DEFAULT_BACKEND_PORT")

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
