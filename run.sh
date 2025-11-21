#!/bin/bash

# WireWAN - WireGuard WAN Overlay Manager
# Run script for development (using UV)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}WireWAN - WireGuard WAN Overlay Manager${NC}"
echo "========================================"

# Check for UV
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}UV not found. Installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check for Node.js
command -v node >/dev/null 2>&1 || { echo -e "${RED}Node.js is required but not installed.${NC}" >&2; exit 1; }

# Function to setup backend
setup_backend() {
    echo -e "\n${YELLOW}Setting up backend...${NC}"
    cd backend

    # Use UV to sync dependencies (creates venv automatically)
    echo "Installing Python dependencies with UV..."
    uv sync

    cd ..
}

# Function to setup frontend
setup_frontend() {
    echo -e "\n${YELLOW}Setting up frontend...${NC}"
    cd frontend

    # Install dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install
    fi

    cd ..
}

# Function to run backend
run_backend() {
    echo -e "\n${GREEN}Starting backend server on http://localhost:8000${NC}"
    cd backend
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Function to run frontend
run_frontend() {
    echo -e "\n${GREEN}Starting frontend server on http://localhost:3000${NC}"
    cd frontend
    npm run dev
}

# Main script
case "$1" in
    setup)
        setup_backend
        setup_frontend
        echo -e "\n${GREEN}Setup complete!${NC}"
        echo "Run './run.sh backend' in one terminal"
        echo "Run './run.sh frontend' in another terminal"
        ;;
    backend)
        setup_backend
        run_backend
        ;;
    frontend)
        setup_frontend
        run_frontend
        ;;
    *)
        echo "Usage: ./run.sh {setup|backend|frontend}"
        echo ""
        echo "Commands:"
        echo "  setup    - Install all dependencies"
        echo "  backend  - Start the backend API server"
        echo "  frontend - Start the frontend development server"
        echo ""
        echo "For development, run in two separate terminals:"
        echo "  Terminal 1: ./run.sh backend"
        echo "  Terminal 2: ./run.sh frontend"
        ;;
esac
