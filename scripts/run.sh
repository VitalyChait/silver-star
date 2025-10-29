#!/bin/bash

# SilverStar Run Script
# This script handles the running of the application

set -e  # Exit on any error

echo "=========================================="
echo "SilverStar Application Run"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname $SCRIPT_DIR)"
LOG_DIR="$REPO_DIR/logs"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "REPO_DIR: $REPO_DIR"
echo "LOG_DIR: $LOG_DIR"

# Function to print colored output
print_status() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

run_chatbot_sanity_check() {
    local url="http://localhost:${PYTHON_APP_PORT}/api/chatbot/chat"
    local payload='{"message":"Hello from the SilverStar sanity check!"}'
    local attempts=0
    local max_attempts=5
    local delay_seconds=3
    local last_response=""
    local exit_code=1

    while [ $attempts -lt $max_attempts ]; do
        last_response=$(curl --silent --show-error --connect-timeout 2 --max-time 5 \
            -H 'Content-Type: application/json' \
            -X POST \
            -d "$payload" \
            "$url" 2>&1)
        exit_code=$?

        if [ $exit_code -eq 0 ] && [[ "$last_response" == *'"response"'* ]]; then
            local preview
            preview=$(echo "$last_response" | sed -n 's/.*"response"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
            if [ -n "$preview" ]; then
                print_success "Chatbot sanity check passed with response: \"$preview\""
            else
                print_success "Chatbot sanity check passed."
            fi
            return 0
        fi

        print_status "Chatbot sanity check attempt $((attempts + 1)) failed. Retrying in $delay_seconds seconds..."
        attempts=$((attempts + 1))
        sleep $delay_seconds
    done

    print_error "Chatbot sanity check failed after $max_attempts attempts."
    if [ -n "$last_response" ]; then
        print_error "Last response: $last_response"
    fi
    return 1
}

# Ensure logs directory exists early
mkdir -p "$LOG_DIR"
BACKEND_LOG_FILE="$LOG_DIR/backend.log"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"
LLM_LOG_DIR="$LOG_DIR/llm"

mkdir -p "$LLM_LOG_DIR"

# Always start with fresh logs for this run
rm -rf "$BACKEND_LOG_FILE" "$FRONTEND_LOG_FILE" "$LLM_LOG_DIR/*"

bash "$SCRIPT_DIR/stop.sh"

ENV_FILE="$REPO_DIR/code/.env"
print_status "Loading environment variables from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a
print_success "Environment variables loaded"

# Generate a frontend env.js with frozen values so the static server can serve it
print_status "Writing frontend env.js with startup env values..."
FRONTEND_DIR_ENV="$REPO_DIR/code/frontend/env.js"
rm -f "$FRONTEND_DIR_ENV"
cat > "$FRONTEND_DIR_ENV" <<EOF
// Generated at runtime by scripts/run.sh
window.__ENV__ = Object.freeze({
  NODE_APP_PORT: ${NODE_APP_PORT:-3000},
  PYTHON_APP_PORT: ${PYTHON_APP_PORT:-8000}
});
EOF
print_success "Wrote $FRONTEND_DIR_ENV"

# Start the backend server
print_status "Starting backend server..."
cd "$REPO_DIR/code/backend"
uv run python start_server.py &
BACKEND_PID=$!

# Wait a moment for the backend to start
sleep 3

# Start a simple HTTP server for the frontend
print_status "Starting frontend server..."
cd "$REPO_DIR/code/frontend"
( uv run python -m http.server $NODE_APP_PORT 2>&1 | tee -a "$FRONTEND_LOG_FILE" ) &
FRONTEND_PID=$!
cd "$REPO_DIR"

print_status "Waiting for services before running chatbot sanity check..."
sleep 5
print_status "Running chatbot sanity check..."
if run_chatbot_sanity_check; then
    :
else
    print_error "Chatbot sanity check did not complete successfully. Please review the backend logs."
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    print_status "Stopping servers..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    print_success "All servers stopped"
    exit 0
}

# Set up trap to cleanup on Ctrl+C
trap cleanup INT

echo ""
echo "=========================================="
print_success "SilverStar application is ready!"
echo "=========================================="
echo "Backend: http://localhost:$PYTHON_APP_PORT"
echo "Frontend: http://localhost:$NODE_APP_PORT/silverstar.html"
echo "Chatbot: http://localhost:$NODE_APP_PORT/chatbot.html"
echo "API Docs: http://localhost:$PYTHON_APP_PORT/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for processes
wait
