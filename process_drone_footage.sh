#!/bin/bash

echo "DJI Drone Metadata Embedder"
echo "=========================="
echo

# Check if directory argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [directory_path]"
    echo "Example: $0 /path/to/drone/footage"
    echo
    exit 1
fi

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python is not installed"
    echo "Please install Python 3.6 or higher"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Run the Python script
echo "Processing drone footage in: $1"
echo
dji-embed "$@"

echo
echo "Processing complete!"
