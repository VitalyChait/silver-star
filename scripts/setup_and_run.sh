#!/bin/bash

# SilverStar Setup and Run Script
# This script handles all steps from installation to running of application

set -e  # Exit on any error

echo "=========================================="
echo "SilverStar Application Setup and Run"
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

# Step 1: Install required system packages (Ubuntu/Debian)
print_status "Step 0: Installing system packages (apt)..."
bash "$SCRIPT_DIR/install_ubuntu_dependencies.sh"

# Ensure uv is installed
if ! command -v uv >/dev/null 2>&1; then
    print_error "uv not found. Please install uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then re-run: $SCRIPT_DIR/setup_and_run.sh"
    exit 1
fi

# Step 2: Install Python dependencies
print_status "Step 2: Installing Python dependencies with uv..."
cd "$REPO_DIR/code/backend"
uv sync
print_success "Python dependencies installed successfully via uv"

# Step 3: Configure environment variables
print_status "Step 3: Setting up environment configuration..."
ENV_FILE="$REPO_DIR/code/.env"
ENV_EXAMPLE="$REPO_DIR/code/env_example"

if [ -f "$ENV_FILE" ]; then
    print_status ".env file already exists"
else
    print_status "Creating .env file from example..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_success ".env file created"
    print_status "Please edit $ENV_FILE with your actual API keys before running the chatbot"
fi

sanity_check_env_keys "$ENV_FILE"

# Step 4: Initialize database
print_status "Step 4: Initializing database with sample jobs..."
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

print_status "Loading environment variables from $ENV_FILE"
set -a
source "$ENV_FILE"
set +a
print_success "Environment variables loaded"

uv run python populate_jobs.py
print_success "Database initialized with sample jobs"

# Step 5: Start the application
print_status "Step 5: Starting SilverStar application..."

bash "$SCRIPT_DIR/run.sh"
