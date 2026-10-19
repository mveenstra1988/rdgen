#!/usr/bin/env bash
# Figma-alternatief: Penpot lokaal via Docker (poort 9001).
set -euo pipefail

DIR="${HOME}/.config/vit/penpot"
COMPOSE="$DIR/docker-compose.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop ontbreekt. Installeer: https://www.docker.com/products/docker-desktop/" >&2
  echo "Of gebruik cloud Penpot: open https://design.penpot.app" >&2
  exit 1
fi

mkdir -p "$DIR"
if [[ ! -f "$COMPOSE" ]]; then
  cat >"$COMPOSE" <<'YAML'
# Minimal Penpot stack — zie https://help.penpot.app/technical-guide/getting-started/docker/
services:
  penpot-frontend:
    image: penpotapp/frontend:latest
    ports: ["9001:80"]
    volumes: ["penpot_assets:/opt/data"]
    depends_on: [penpot-backend, penpot-exporter]
    environment:
      PENPOT_FLAGS: enable-registration enable-login-with-password
  penpot-backend:
    image: penpotapp/backend:latest
    volumes: ["penpot_assets:/opt/data"]
    depends_on: [penpot-postgres, penpot-redis]
    environment:
      PENPOT_FLAGS: enable-registration enable-login-with-password
      PENPOT_PUBLIC_URI: http://127.0.0.1:9001
  penpot-exporter:
    image: penpotapp/exporter:latest
  penpot-postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: penpot
      POSTGRES_USER: penpot
      POSTGRES_PASSWORD: penpot
    volumes: ["penpot_pg:/var/lib/postgresql/data"]
  penpot-redis:
    image: redis:7
volumes:
  penpot_assets:
  penpot_pg:
YAML
fi

cd "$DIR"
docker compose -f "$COMPOSE" up -d
echo "Penpot: http://127.0.0.1:9001"
echo "In VIT AI Hub: studio Design + knop Penpot."
if [[ "$(uname -s)" == "Darwin" ]]; then
  open "http://127.0.0.1:9001" || true
fi
