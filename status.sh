#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd "$SCRIPT_DIR" && pwd)"

# Default ports
DEFAULT_FRONTEND_PORT=3000
DEFAULT_BACKEND_PORT=8000

# Get current ports or use defaults
FRONTEND_PORT=$(cat "$SCRIPT_DIR/logs/.frontend_port" 2>/dev/null || echo "$DEFAULT_FRONTEND_PORT")
BACKEND_PORT=$(cat "$SCRIPT_DIR/logs/.backend_port" 2>/dev/null || echo "$DEFAULT_BACKEND_PORT")

echo "Silver Star Application Status"
echo "=============================="

# Check backend
if [ -f "$SCRIPT_DIR/logs/backend.pid" ]; then
    BACKEND_PID=$(cat "$SCRIPT_DIR/logs/backend.pid")
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
if [ -f "$SCRIPT_DIR/logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$SCRIPT_DIR/logs/frontend.pid")
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
tail -n 5 "$SCRIPT_DIR/logs/backend.log" 2>/dev/null || echo "No backend log found"
echo ""
echo "Frontend (last 5 lines):"
tail -n 5 "$SCRIPT_DIR/logs/frontend.log" 2>/dev/null || echo "No frontend log found"
