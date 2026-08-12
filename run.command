#!/bin/zsh
cd "${0:A:h}"
set -u

port=8000
health_url="http://127.0.0.1:${port}/api/health"
expected='"app":"inkdrop-local"'

if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 1 "$health_url" 2>/dev/null | grep -Fq "$expected"; then
  echo "Inkdrop Local is already running at http://127.0.0.1:${port}"
  exit 0
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:${port} -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port ${port} is already in use by another process." >&2
  exit 1
fi

uv run uvicorn app.main:app --host 127.0.0.1 --port "$port" --workers 1 &
server_pid=$!
cleanup() { kill -TERM "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; }
trap cleanup HUP INT TERM EXIT

for _ in {1..30}; do
  if curl -fsS --max-time 1 "$health_url" 2>/dev/null | grep -Fq "$expected"; then
    echo "Inkdrop Local running at http://127.0.0.1:${port}"
    wait "$server_pid"
    exit $?
  fi
  kill -0 "$server_pid" 2>/dev/null || break
  sleep 0.5
done

echo "Inkdrop Local failed to become healthy on port ${port}." >&2
exit 1
