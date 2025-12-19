#!/bin/bash

# NII.GZ point annotation system startup script

echo "=== NII.GZ Point Annotation System ==="
echo ""

# Stop existing services
echo "Stopping existing services..."
pkill -f "python main.py" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 1

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Start backend
echo "1. Starting backend service..."
cd "$SCRIPT_DIR/backend"
pip install -r requirements.txt -q
python main.py &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# Wait for backend to start
sleep 3

# Start frontend
echo "2. Starting frontend service..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "=== Services Started ==="
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt signal
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
