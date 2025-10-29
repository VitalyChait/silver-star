#!/bin/bash

# SilverStar Setup and Run Script
# This script handles all steps from installation to running of application

set -e  # Exit on any error

echo "=========================================="
echo "SilverStar Application Setup and Run"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd "$SCRIPT_DIR" && pwd)"
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

# Ensure logs directory exists early
mkdir -p "$LOG_DIR"
BACKEND_LOG_FILE="$LOG_DIR/backend.log"
FRONTEND_LOG_FILE="$LOG_DIR/frontend.log"

# Always start with fresh logs for this run
rm -f "$BACKEND_LOG_FILE" "$FRONTEND_LOG_FILE"

sanitize_string() {
    local value="$1"
    value="$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    echo "$value"
}

sanity_check_env_keys() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        print_error "Environment file not found at $env_file"
        exit 1
    fi

    print_status "Performing environment sanity check..."

    local -a missing_keys
    local -a placeholder_keys
    local key value

    missing_keys=()
    placeholder_keys=()

    while IFS='=' read -r raw_key raw_value; do
        key=$(sanitize_string "$raw_key")

        # Skip comments and blank lines
        if [[ -z "$key" || "${key:0:1}" == "#" ]]; then
            continue
        fi

        value=$(sanitize_string "$raw_value")

        if [[ -z "$value" ]]; then
            missing_keys+=("$key")
            continue
        fi

        if [[ "$value" == *"YOUR_"* || "$value" == *"REPLACE"* || "$value" == *"INSERT"* || "$value" == *"CHANGE_ME"* || "$value" == *"PUT_YOUR"* || "$value" == *"ADD_YOUR"* ]]; then
            placeholder_keys+=("$key")
        fi
    done < "$env_file"

    if [ "${#missing_keys[@]}" -gt 0 ]; then
        print_error "Missing values detected for: ${missing_keys[*]}"
        exit 1
    fi

    if [ "${#placeholder_keys[@]}" -gt 0 ]; then
        print_error "Placeholder values detected for: ${placeholder_keys[*]}"
        exit 1
    fi

    print_success "Environment sanity check passed"
}

run_chatbot_sanity_check() {
    local url="http://localhost:8000/api/chatbot/chat"
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

# Check if we're in the right directory
if [ ! -f "$REPO_DIR/code/backend/start_server.py" ]; then
    print_error "Please run this script from the silver-star root directory"
    exit 1
fi

# Step 0: Install required system packages (Ubuntu/Debian)
print_status "Step 0: Installing system packages (apt)..."
bash "$SCRIPT_DIR/install_ubuntu_dependencies.sh"

# Clean up any existing processes
print_status "Cleaning up any existing processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "python -m http.server" 2>/dev/null || true

# Step 1: Install dependencies
print_status "Step 1: Installing Python dependencies with uv..."
cd "$REPO_DIR/code/backend"

# Ensure uv is installed
if ! command -v uv >/dev/null 2>&1; then
    print_error "uv not found. Please install uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then re-run: ./setup_and_run.sh"
    exit 1
fi

# Sync environment from pyproject
print_status "Syncing environment (uv sync)..."
uv sync
print_success "Dependencies installed successfully via uv"

# Step 2: Configure environment variables
print_status "Step 2: Setting up environment configuration..."
ENV_FILE="../.env"
ENV_EXAMPLE="../env_example"

if [ -f "$ENV_FILE" ]; then
    print_status ".env file already exists"
else
    print_status "Creating .env file from example..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_success ".env file created"
    print_status "Please edit $ENV_FILE with your actual API keys before running the chatbot"
fi

sanity_check_env_keys "$ENV_FILE"

print_status "Loading environment variables from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a
print_success "Environment variables loaded"

# Step 3: Initialize database
print_status "Step 3: Initializing database with sample jobs..."
if [ -f "data.db" ]; then
    print_status "Database already exists"

    set +e
    # Use -t 10 for a 10-second timeout
    read -p "Do you want to reset the database? (y/n): " -n 1 -r -t 1

    if [ $? -gt 128 ]; then
        # Timeout occurred, keep the default value "n"
        # or explicitly set it for clarity
        REPLY="n"
        echo -e "\nTimeout reached. Defaulting to 'n'."
    else
        # The user provided input or hit enter, so we need to handle the case
        # where the user didn't type 'y' or 'n' but hit another key.
        # Since you used -n 1, REPLY contains the single character typed.
        # If a character was typed, we can proceed with the value in REPLY.
        echo
    fi
    set -e
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f data.db
        print_status "Database removed"
    else
        print_status "Keeping existing database"
    fi
fi

uv run python populate_jobs.py
print_success "Database initialized with sample jobs"

# Step 4: Remove unnecessary script files
print_status "Step 4: Cleaning up unnecessary script files..."
cd "$REPO_DIR"

# Remove individual run scripts since we now have a comprehensive one
if [ -f "run_me.sh" ]; then
    print_status "Removing run_me.sh (replaced by setup_and_run.sh)..."
    rm run_me.sh
fi

if [ -f "run_dev.sh" ]; then
    print_status "Removing run_dev.sh (replaced by setup_and_run.sh)..."
    rm run_dev.sh
fi

print_success "Cleanup completed"

# Step 5: Start the application
print_status "Step 5: Starting SilverStar application..."

# Clean up any existing processes on the ports we need
print_status "Checking for existing processes on required ports..."
# Kill any process using port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
# Kill any process using port 3000
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

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
( uv run python -m http.server 3000 2>&1 | tee -a "$FRONTEND_LOG_FILE" ) &
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
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000/silverstar.html"
echo "Chatbot: http://localhost:3000/chatbot.html"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for processes
wait
