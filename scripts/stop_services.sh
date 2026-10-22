#!/bin/bash
# ==============================================================================
# AI Hedge Fund - Stop Services Script
# ==============================================================================
# Safely stops backend (8000) and frontend (5173) services.
# ==============================================================================

set -uo pipefail

PROJECT_ROOT="/Users/niuyufei/ai-hedge-fund-2025"
RUN_DIR="$PROJECT_ROOT/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

LSOF_BIN=$(which lsof 2>/dev/null || echo "/usr/sbin/lsof")

echo "Stopping AI Hedge Fund services..."

# Helper to stop PID
stop_pid() {
    local pid="$1"
    local name="$2"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "Terminating $name (PID: $pid)..."
        kill -15 "$pid" 2>/dev/null || true
        for _ in {1..10}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo "$name stopped."
                return 0
            fi
            sleep 0.5
        done
        echo "Force killing $name (PID: $pid)..."
        kill -9 "$pid" 2>/dev/null || true
    fi
}

# 1. Stop backend via PID file if present
if [ -f "$BACKEND_PID_FILE" ]; then
    BPID=$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)
    stop_pid "$BPID" "Backend (from PID file)"
    rm -f "$BACKEND_PID_FILE"
fi

# 2. Stop frontend via PID file if present
if [ -f "$FRONTEND_PID_FILE" ]; then
    FPID=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)
    stop_pid "$FPID" "Frontend (from PID file)"
    rm -f "$FRONTEND_PID_FILE"
fi

# 3. Check port 8000 to catch any remaining uvicorn process
if [ -x "$LSOF_BIN" ]; then
    PORT_8000_PIDS=$("$LSOF_BIN" -ti :8000 2>/dev/null || true)
    for p in $PORT_8000_PIDS; do
        CMD=$(ps -p "$p" -o command= 2>/dev/null || true)
        if echo "$CMD" | grep -qE "app\.backend\.main|uvicorn"; then
            echo "Stopping remaining backend process on port 8000 (PID: $p)..."
            kill -15 "$p" 2>/dev/null || true
            sleep 1
            kill -9 "$p" 2>/dev/null || true
        fi
    done

    # 4. Check port 5173 to catch any remaining vite process
    PORT_5173_PIDS=$("$LSOF_BIN" -ti :5173 2>/dev/null || true)
    for p in $PORT_5173_PIDS; do
        CMD=$(ps -p "$p" -o command= 2>/dev/null || true)
        if echo "$CMD" | grep -qE "vite|node"; then
            echo "Stopping remaining frontend process on port 5173 (PID: $p)..."
            kill -15 "$p" 2>/dev/null || true
            sleep 1
            kill -9 "$p" 2>/dev/null || true
        fi
    done
fi

echo "AI Hedge Fund services stopped successfully."
