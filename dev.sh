#!/usr/bin/env bash
# =========================================================================
# dev.sh — local dev launcher
#   · Postgres in Docker (via docker-compose.dev.yml)
#   · Alembic `upgrade head` before backend starts
#   · Backend (uvicorn)   on :17004   — local venv
#   · Frontend (next dev) on :17005   — local node_modules
#
# Default: backend + frontend logs stream to this terminal with
#   [backend] / [frontend] prefixes. Pass --log-files (or -f) to redirect
#   them to .dev-logs/{backend,frontend}.log instead.
#
# Ctrl+C stops backend + frontend; Postgres is left running (down with:
#   docker compose -f docker-compose.dev.yml down
# ).
# =========================================================================
set -euo pipefail

LOG_TO_FILES=false
for arg in "$@"; do
    case "$arg" in
        --log-files|-f) LOG_TO_FILES=true ;;
        -h|--help)
            printf "Usage: %s [--log-files|-f]\n" "$0"
            printf "  default       stream logs to this terminal\n"
            printf "  --log-files   redirect to .dev-logs/{backend,frontend}.log\n"
            exit 0
            ;;
        *) err "unknown arg: $arg" 2>/dev/null || printf "unknown arg: %s\n" "$arg" >&2; exit 2 ;;
    esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
COMPOSE_FILE="$ROOT_DIR/docker-compose.dev.yml"
ENV_FILE="$ROOT_DIR/.env"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$ROOT_DIR/.dev-logs"

BACKEND_PORT=17004
FRONTEND_PORT=17005
POSTGRES_PORT=17000

# --- helpers --------------------------------------------------------------
c_reset="\033[0m"; c_bold="\033[1m"; c_blue="\033[34m"; c_green="\033[32m"; c_red="\033[31m"; c_yellow="\033[33m"
log()  { printf "${c_blue}[dev]${c_reset} %s\n" "$*"; }
ok()   { printf "${c_green}[ok]${c_reset}  %s\n" "$*"; }
warn() { printf "${c_yellow}[warn]${c_reset} %s\n" "$*"; }
err()  { printf "${c_red}[err]${c_reset} %s\n" "$*" >&2; }

require() {
    command -v "$1" >/dev/null 2>&1 || { err "missing dependency: $1"; exit 1; }
}

port_in_use() {
    if command -v ss >/dev/null 2>&1; then
        ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN
    else
        (echo >/dev/tcp/127.0.0.1/"$1") >/dev/null 2>&1
    fi
}

# --- cleanup on exit ------------------------------------------------------
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
    log "stopping local processes..."
    [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    log "Postgres stays up (stop with: docker compose -f docker-compose.dev.yml down)"
}
trap cleanup EXIT INT TERM

# --- pre-flight -----------------------------------------------------------
require docker
require python3
require node
require npm

if [[ ! -f "$ENV_FILE" ]]; then
    warn ".env missing — copying from .env.example"
    cp "$ROOT_DIR/.env.example" "$ENV_FILE"
fi

mkdir -p "$LOG_DIR"

# --- Postgres -------------------------------------------------------------
log "ensuring Postgres is up..."
if port_in_use "$POSTGRES_PORT"; then
    ok "port $POSTGRES_PORT already in use — assuming Postgres is running"
else
    docker compose -f "$COMPOSE_FILE" up -d postgres
    log "waiting for Postgres to become healthy..."
    for i in {1..30}; do
        status=$(docker inspect -f '{{.State.Health.Status}}' wmp-postgres 2>/dev/null || echo "starting")
        [[ "$status" == "healthy" ]] && break
        sleep 1
    done
    [[ "$status" == "healthy" ]] || { err "Postgres did not become healthy"; exit 1; }
    ok "Postgres healthy on :$POSTGRES_PORT"
fi

# --- Backend venv + deps --------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    log "creating backend venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

BACKEND_STAMP="$VENV_DIR/.deps-stamp"
if [[ ! -f "$BACKEND_STAMP" || "$BACKEND_DIR/pyproject.toml" -nt "$BACKEND_STAMP" ]]; then
    log "installing backend deps (editable + dev extras)..."
    pip install --quiet --upgrade pip
    pip install --quiet -e "$BACKEND_DIR[dev]"
    touch "$BACKEND_STAMP"
    ok "backend deps installed"
else
    ok "backend deps up to date"
fi

# --- Frontend deps --------------------------------------------------------
if [[ ! -d "$FRONTEND_DIR/node_modules" \
   || "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_DIR/node_modules/.package-lock.json" ]]; then
    log "installing frontend deps (npm ci)..."
    (cd "$FRONTEND_DIR" && npm ci --silent)
    ok "frontend deps installed"
else
    ok "frontend deps up to date"
fi

# --- migrations -----------------------------------------------------------
log "running alembic upgrade head..."
(
    cd "$BACKEND_DIR"
    set -a; source "$ENV_FILE"; set +a
    alembic upgrade head
)
ok "migrations applied"

# --- port guards ----------------------------------------------------------
if port_in_use "$BACKEND_PORT"; then
    err "port $BACKEND_PORT already in use (backend); stop the other process first"
    exit 1
fi
if port_in_use "$FRONTEND_PORT"; then
    err "port $FRONTEND_PORT already in use (frontend); stop the other process first"
    exit 1
fi

# --- launch backend -------------------------------------------------------
c_backend="\033[36m"   # cyan
c_frontend="\033[35m"  # magenta

if $LOG_TO_FILES; then
    log "starting backend on :$BACKEND_PORT  (logs: $LOG_DIR/backend.log)"
    (
        cd "$BACKEND_DIR"
        set -a; source "$ENV_FILE"; set +a
        exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload
    ) >"$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!

    log "starting frontend on :$FRONTEND_PORT (logs: $LOG_DIR/frontend.log)"
    (
        cd "$FRONTEND_DIR"
        set -a; source "$ENV_FILE"; set +a
        exec npm run dev
    ) >"$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
else
    log "starting backend on :$BACKEND_PORT  (streaming to this terminal)"
    (
        cd "$BACKEND_DIR"
        set -a; source "$ENV_FILE"; set +a
        exec uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload 2>&1 \
            | sed -u "s/^/$(printf "${c_backend}")[backend]$(printf "${c_reset}") /"
    ) &
    BACKEND_PID=$!

    log "starting frontend on :$FRONTEND_PORT (streaming to this terminal)"
    (
        cd "$FRONTEND_DIR"
        set -a; source "$ENV_FILE"; set +a
        exec npm run dev 2>&1 \
            | sed -u "s/^/$(printf "${c_frontend}")[frontend]$(printf "${c_reset}") /"
    ) &
    FRONTEND_PID=$!
fi

# --- summary --------------------------------------------------------------
printf "\n${c_bold}▸ dev stack ready${c_reset}\n"
printf "   backend:  http://localhost:%s/api/v1/health\n" "$BACKEND_PORT"
printf "   frontend: http://localhost:%s\n" "$FRONTEND_PORT"
printf "   postgres: localhost:%s (container wmp-postgres)\n" "$POSTGRES_PORT"
if $LOG_TO_FILES; then
    printf "   logs:     tail -f %s/{backend,frontend}.log\n\n" "$LOG_DIR"
else
    printf "   logs:     streaming below (run with --log-files to write to disk instead)\n\n"
fi
printf "${c_yellow}Ctrl+C to stop backend + frontend. Postgres stays up.${c_reset}\n\n"

# --- wait for either to exit ---------------------------------------------
# If either process dies, fail loudly so the user sees it.
wait -n "$BACKEND_PID" "$FRONTEND_PID" || true
if $LOG_TO_FILES; then
    err "one process exited — check $LOG_DIR for details"
else
    err "one process exited — scroll up for the stack trace"
fi
exit 1
