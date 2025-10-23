#!/usr/bin/env python3
"""
Startup script for the Silver Star FastAPI server.
This script sets up the Python path correctly before starting the server.
"""

import sys
import os
from pathlib import Path

# Get the directory where this script is located
script_dir = Path(__file__).parent.absolute()

# Add the llm module to the Python path using absolute path
llm_path = script_dir.parent / "llm"
llm_path_str = str(llm_path.absolute())
sys.path.insert(0, llm_path_str)

print(f"Adding {llm_path_str} to Python path")
print(f"LLM directory exists: {llm_path.exists()}")

# Set up global error handling to terminate fast on errors
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to terminate fast on errors."""
    import traceback
    print(f"Fatal error: {exc_type.__name__}: {exc_value}", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.exit(1)

# Install the global exception handler
sys.excepthook = handle_exception

# Check if the llm module can be imported
try:
    import llm
    print("Successfully imported LLM module")
except ImportError as e:
    print(f"Error importing LLM module: {e}", file=sys.stderr)
    print("Please ensure all dependencies are installed:", file=sys.stderr)
    print("- google-generativeai", file=sys.stderr)
    print("- google-cloud-speech", file=sys.stderr)
    print("- google-cloud-texttospeech", file=sys.stderr)
    sys.exit(1)

# Start the uvicorn server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
