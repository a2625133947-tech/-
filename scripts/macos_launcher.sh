#!/bin/bash
# ==============================================================================
# AI Hedge Fund - macOS Application Launcher
# ==============================================================================
# This launcher is designed to run silently without popping up any Terminal window,
# discovering required tool paths (Poetry, Node, npm, curl, lsof), verifying
# backend and frontend states, launching services if needed, polling for readiness,
# and opening the application in the default web browser.
# ==============================================================================

set -uo pipefail

# 1. Project directories & file locations
PROJECT_ROOT="/Users/niuyufei/ai-hedge-fund-2025"
RUN_DIR="$PROJECT_ROOT/.run"
mkdir -p "$RUN_DIR"

LAUNCHER_LOG="$RUN_DIR/launcher.log"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
LOCK_FILE="$RUN_DIR/launcher.lock"

# 2. Logging functions
log() {
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [LAUNCHER] $*" >> "$LAUNCHER_LOG"
}

# 3. macOS Native UI Functions (No Terminal required)
show_native_alert() {
    local title="$1"
    local message="$2"
    log "ALERT: $title - $message"
    /usr/bin/osascript -e "tell application \"System Events\" to activate" \
                       -e "tell application \"System Events\" to display alert \"$title\" message \"$message\" as critical buttons {\"确定\"} default button \"确定\"" >/dev/null 2>&1 || true
}

show_native_notification() {
    local title="$1"
    local message="$2"
    log "NOTIFICATION: $title - $message"
    /usr/bin/osascript -e "display notification \"$message\" with title \"$title\"" >/dev/null 2>&1 &
}

log "=== AI Hedge Fund launch sequence initiated ==="

# 4. Concurrency Lock: Prevent multiple concurrent launcher instances on fast clicks
if [ -f "$LOCK_FILE" ]; then
    PREV_LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || true)
    if [ -n "$PREV_LOCK_PID" ] && kill -0 "$PREV_LOCK_PID" 2>/dev/null; then
        log "Another launcher instance (PID $PREV_LOCK_PID) is currently active. Waiting up to 10s..."
        for _ in {1..20}; do
            sleep 0.5
            if ! kill -0 "$PREV_LOCK_PID" 2>/dev/null; then
                break
            fi
            # If services become healthy during wait, open browser and exit
            if /usr/bin/curl -s -m 1 "http://127.0.0.1:5173/" 2>/dev/null | grep -q "AI Hedge Fund"; then
                log "Services are already healthy. Opening browser directly."
                /usr/bin/open "http://localhost:5173"
                exit 0
            fi
        done
    fi
fi
echo "$$" > "$LOCK_FILE"
cleanup_lock() {
    rm -f "$LOCK_FILE" 2>/dev/null || true
}
trap cleanup_lock EXIT

# 5. Environment & Binary Path Discovery
# Finder launches with a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin).
# We proactively search standard and user paths for node, npm, poetry, python3, curl, lsof.
find_binary() {
    local name="$1"
    shift
    for candidate in "$@"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

POETRY_BIN=$(find_binary "poetry" \
    "$HOME/.local/bin/poetry" \
    "$HOME/Library/Application Support/pypoetry/venv/bin/poetry" \
    "/opt/homebrew/bin/poetry" \
    "/usr/local/bin/poetry" \
    "$(command -v poetry 2>/dev/null || true)")

NODE_BIN=$(find_binary "node" \
    "/opt/homebrew/bin/node" \
    "/usr/local/bin/node" \
    "$(command -v node 2>/dev/null || true)")

NPM_BIN=$(find_binary "npm" \
    "/opt/homebrew/bin/npm" \
    "/usr/local/bin/npm" \
    "$(command -v npm 2>/dev/null || true)")

PYTHON_BIN=$(find_binary "python3" \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" \
    "/opt/homebrew/bin/python3.11" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3" \
    "$(command -v python3 2>/dev/null || true)" \
    "/usr/bin/python3")

CURL_BIN=$(find_binary "curl" \
    "/usr/bin/curl" \
    "/opt/homebrew/bin/curl" \
    "$(command -v curl 2>/dev/null || true)")

LSOF_BIN=$(find_binary "lsof" \
    "/usr/sbin/lsof" \
    "/usr/bin/lsof" \
    "$(command -v lsof 2>/dev/null || true)")

# Validate required tools
MISSING_TOOLS=""
[ -z "$POETRY_BIN" ] && MISSING_TOOLS="$MISSING_TOOLS Poetry"
[ -z "$NODE_BIN" ]   && MISSING_TOOLS="$MISSING_TOOLS Node.js"
[ -z "$NPM_BIN" ]    && MISSING_TOOLS="$MISSING_TOOLS npm"
[ -z "$CURL_BIN" ]   && MISSING_TOOLS="$MISSING_TOOLS curl"
[ -z "$LSOF_BIN" ]   && MISSING_TOOLS="$MISSING_TOOLS lsof"

if [ -n "$MISSING_TOOLS" ]; then
    log "ERROR: Missing required dependencies:$MISSING_TOOLS"
    show_native_alert "AI Hedge Fund 启动失败" "未找到必需的运行环境：$MISSING_TOOLS。\n请检查环境配置。\n详细日志：$LAUNCHER_LOG"
    exit 1
fi

log "Environment verified:"
log "  Poetry : $POETRY_BIN"
log "  Node   : $NODE_BIN"
log "  npm    : $NPM_BIN"
log "  Python : $PYTHON_BIN"
log "  curl   : $CURL_BIN"
log "  lsof   : $LSOF_BIN"

# Export enhanced PATH so child processes (npm -> vite, poetry -> python) succeed
NODE_DIR=$(dirname "$NODE_BIN")
POETRY_DIR=$(dirname "$POETRY_BIN")
export PATH="$NODE_DIR:$POETRY_DIR:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:$HOME/.local/bin:$PATH"

# 6. Ensure .env exists in project root
if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
    log "Creating .env from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

# 7. Helper functions for port checking and health validation
is_port_listening() {
    local port="$1"
    "$LSOF_BIN" -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

get_port_pid() {
    local port="$1"
    "$LSOF_BIN" -ti :"$port" 2>/dev/null | head -n 1
}

is_backend_healthy() {
    local resp
    resp=$("$CURL_BIN" -s -m 2 "http://127.0.0.1:8000/" 2>/dev/null || true)
    if echo "$resp" | grep -q "Welcome to AI Hedge Fund API"; then
        return 0
    fi
    return 1
}

is_frontend_healthy() {
    local resp
    resp=$("$CURL_BIN" -s -m 2 "http://127.0.0.1:5173/" 2>/dev/null || true)
    if echo "$resp" | grep -q "AI Hedge Fund"; then
        return 0
    fi
    return 1
}

# 8. Check Backend Service (Port 8000)
START_BACKEND=0
if is_backend_healthy; then
    log "Backend is already running and healthy on port 8000."
elif is_port_listening 8000; then
    PORT_8000_PID=$(get_port_pid 8000)
    PROC_CMD=$(ps -p "$PORT_8000_PID" -o command= 2>/dev/null || true)
    # Check if this process belongs to our app
    if echo "$PROC_CMD" | grep -qE "app\.backend\.main|uvicorn"; then
        log "Port 8000 occupied by existing backend process (PID: $PORT_8000_PID). Waiting for it to become ready..."
        for _ in {1..10}; do
            sleep 0.5
            if is_backend_healthy; then
                log "Backend became healthy on port 8000."
                break
            fi
        done
        if ! is_backend_healthy; then
            show_native_alert "AI Hedge Fund 启动失败" "后端进程正在运行但未通过健康检查。\n请检查日志：$BACKEND_LOG"
            exit 1
        fi
    else
        log "ERROR: Port 8000 occupied by foreign process: PID $PORT_8000_PID ($PROC_CMD)"
        show_native_alert "AI Hedge Fund 端口冲突" "端口 8000 已被其他非 AI Hedge Fund 程序占用 (PID: $PORT_8000_PID)。\n为避免冲突，服务未启动。"
        exit 1
    fi
else
    START_BACKEND=1
fi

if [ "$START_BACKEND" -eq 1 ]; then
    log "Starting FastAPI backend on 127.0.0.1:8000..."
    echo "==================================================" >> "$BACKEND_LOG"
    echo "=== Starting AI Hedge Fund Backend: $(date) ===" >> "$BACKEND_LOG"
    echo "==================================================" >> "$BACKEND_LOG"
    cd "$PROJECT_ROOT"
    nohup "$POETRY_BIN" run uvicorn app.backend.main:app --host 127.0.0.1 --port 8000 >> "$BACKEND_LOG" 2>&1 &
    NEW_BACKEND_PID=$!
    echo "$NEW_BACKEND_PID" > "$BACKEND_PID_FILE"
    log "FastAPI backend spawned with PID $NEW_BACKEND_PID"
fi

# 9. Check Frontend Service (Port 5173)
START_FRONTEND=0
if is_frontend_healthy; then
    log "Frontend is already running and healthy on port 5173."
elif is_port_listening 5173; then
    PORT_5173_PID=$(get_port_pid 5173)
    PROC_CMD=$(ps -p "$PORT_5173_PID" -o command= 2>/dev/null || true)
    if echo "$PROC_CMD" | grep -qE "vite|node"; then
        log "Port 5173 occupied by frontend process (PID: $PORT_5173_PID). Waiting for it to respond..."
        for _ in {1..10}; do
            sleep 0.5
            if is_frontend_healthy; then
                log "Frontend became healthy on port 5173."
                break
            fi
        done
        if ! is_frontend_healthy; then
            show_native_alert "AI Hedge Fund 启动失败" "前端进程正在运行但未响应请求。\n请检查日志：$FRONTEND_LOG"
            exit 1
        fi
    else
        log "ERROR: Port 5173 occupied by foreign process: PID $PORT_5173_PID ($PROC_CMD)"
        show_native_alert "AI Hedge Fund 端口冲突" "端口 5173 已被其他程序占用 (PID: $PORT_5173_PID)。\n为避免冲突，前端未启动。"
        exit 1
    fi
else
    START_FRONTEND=1
fi

if [ "$START_FRONTEND" -eq 1 ]; then
    log "Starting Vite frontend on 127.0.0.1:5173..."
    echo "===================================================" >> "$FRONTEND_LOG"
    echo "=== Starting AI Hedge Fund Frontend: $(date) ===" >> "$FRONTEND_LOG"
    echo "===================================================" >> "$FRONTEND_LOG"
    cd "$PROJECT_ROOT/app/frontend"
    nohup "$NPM_BIN" run dev -- --host 127.0.0.1 --port 5173 >> "$FRONTEND_LOG" 2>&1 &
    NEW_FRONTEND_PID=$!
    echo "$NEW_FRONTEND_PID" > "$FRONTEND_PID_FILE"
    log "Vite frontend spawned with PID $NEW_FRONTEND_PID"
fi

# 10. Polling & Service Readiness Verification (Timeout: 30s)
# Backend Readiness Poll
if [ "$START_BACKEND" -eq 1 ]; then
    log "Polling backend on http://127.0.0.1:8000/ ..."
    BACKEND_READY=0
    for i in {1..60}; do
        if ! kill -0 "$NEW_BACKEND_PID" 2>/dev/null; then
            log "ERROR: Backend process $NEW_BACKEND_PID exited prematurely."
            show_native_alert "AI Hedge Fund 启动失败" "后端 FastAPI 服务异常退出。\n请查看日志：\n$BACKEND_LOG"
            exit 1
        fi
        if is_backend_healthy; then
            BACKEND_READY=1
            log "Backend is ready! (Polled for $(( i * 500 ))ms)"
            break
        fi
        sleep 0.5
    done

    if [ "$BACKEND_READY" -ne 1 ]; then
        log "ERROR: Backend failed to become ready within 30s."
        show_native_alert "AI Hedge Fund 启动超时" "FastAPI 后端服务启动超时（30秒）。\n请查看日志：\n$BACKEND_LOG"
        exit 1
    fi
fi

# Frontend Readiness Poll
log "Polling frontend on http://127.0.0.1:5173/ ..."
FRONTEND_READY=0
for i in {1..60}; do
    if [ "$START_FRONTEND" -eq 1 ]; then
        if ! kill -0 "$NEW_FRONTEND_PID" 2>/dev/null; then
            log "ERROR: Frontend process $NEW_FRONTEND_PID exited prematurely."
            show_native_alert "AI Hedge Fund 启动失败" "前端 Vite 服务异常退出。\n请查看日志：\n$FRONTEND_LOG"
            exit 1
        fi
    fi
    if is_frontend_healthy; then
        FRONTEND_READY=1
        log "Frontend is ready! (Polled for $(( i * 500 ))ms)"
        break
    fi
    sleep 0.5
done

if [ "$FRONTEND_READY" -ne 1 ]; then
    log "ERROR: Frontend failed to become ready within 30s."
    show_native_alert "AI Hedge Fund 启动超时" "Vite 前端服务启动超时（30秒）。\n请查看日志：\n$FRONTEND_LOG"
    exit 1
fi

# 11. Open Browser
log "Opening http://localhost:5173 in default browser..."
/usr/bin/open "http://localhost:5173"

# Activate default browser so it immediately comes to foreground when clicked from Dock
/usr/bin/osascript -e '
tell application "System Events"
    if exists (application process "Google Chrome") then
        tell application "Google Chrome" to activate
    else if exists (application process "Safari") then
        tell application "Safari" to activate
    end if
end tell
' >/dev/null 2>&1 || true

log "=== Launch completed successfully ==="

exit 0
