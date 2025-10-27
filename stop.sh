#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd "$SCRIPT_DIR" && pwd)"

# Default ports
DEFAULT_FRONTEND_PORT=3000
DEFAULT_BACKEND_PORT=8000

# Get current ports or use defaults
FRONTEND_PORT=$(cat "$SCRIPT_DIR/logs/.frontend_port" 2>/dev/null || echo "$DEFAULT_FRONTEND_PORT")
BACKEND_PORT=$(cat "$SCRIPT_DIR/logs/.backend_port" 2>/dev/null || echo "$DEFAULT_BACKEND_PORT")

echo "Stopping Silver Star application..."

# Kill backend if PID file exists
if [ -f "$SCRIPT_DIR/logs/backend.pid" ]; then
    BACKEND_PID=$(cat "$SCRIPT_DIR/logs/backend.pid")
    if ps -p $BACKEND_PID > /dev/null; then
        kill $BACKEND_PID
        echo "Backend server stopped"
    fi
    rm "$SCRIPT_DIR/logs/backend.pid"
fi

# Kill frontend if PID file exists
if [ -f "$SCRIPT_DIR/logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$SCRIPT_DIR/logs/frontend.pid")
    if ps -p $FRONTEND_PID > /dev/null; then
        kill $FRONTEND_PID
        echo "Frontend server stopped"
    fi
    rm "$SCRIPT_DIR/logs/frontend.pid"
fi

# Also kill any remaining processes
pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
pkill -f "next.*dev" 2>/dev/null || true
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true

echo "Silver Star application stopped"
