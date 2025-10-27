#!/bin/bash

# SilverStar Setup and Run Script
# This script handles all steps from installation to running of application

set -e  # Exit on any error

echo "=========================================="
echo "SilverStar Application Setup and Run"
echo "=========================================="

SCRIPT_DIR=$(pwd)

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

# Check if we're in the right directory
if [ ! -f "$SCRIPT_DIR/code/backend/start_server.py" ]; then
    print_error "Please run this script from the silver-star root directory"
    exit 1
fi

# Clean up any existing processes
print_status "Cleaning up any existing processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "python -m http.server" 2>/dev/null || true

# Step 1: Install dependencies
print_status "Step 1: Installing Python dependencies..."
cd "$SCRIPT_DIR/code/backend"
if [ -d "venv" ]; then
    print_status "Virtual environment already exists"
else
    print_status "Creating virtual environment..."
    python3 -m venv venv
fi

print_status "Activating virtual environment..."
source ./venv/bin/activate

print_status "Installing dependencies..."
pip install -r requirements.txt
print_success "Dependencies installed successfully"

# Step 2: Configure LLM API keys
print_status "Step 2: Setting up LLM configuration..."
LLM_CONFIG_FILE="app/llm/.llm_config"
LLM_CONFIG_EXAMPLE="app/llm/.llm_config.example"

if [ -f "$LLM_CONFIG_FILE" ]; then
    print_status "LLM config file already exists"
else
    print_status "Creating LLM config file from example..."
    cp "$LLM_CONFIG_EXAMPLE" "$LLM_CONFIG_FILE"
    print_success "LLM config file created"
    print_status "Please edit $LLM_CONFIG_FILE with your actual API keys before running the chatbot"
fi

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

python populate_jobs.py
print_success "Database initialized with sample jobs"

# Step 4: Remove unnecessary script files
print_status "Step 4: Cleaning up unnecessary script files..."
cd "$SCRIPT_DIR"

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
cd "$SCRIPT_DIR/code/backend"
source ./venv/bin/activate
python3 start_server.py &
BACKEND_PID=$!

# Wait a moment for the backend to start
sleep 3

# Start a simple HTTP server for the frontend
print_status "Starting frontend server..."
cd "$SCRIPT_DIR/code/frontend"
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

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
