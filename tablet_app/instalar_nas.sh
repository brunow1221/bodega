#!/bin/sh
set -eu

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no esta instalado o no esta disponible para este usuario." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d --build
else
  echo "No se encontro Docker Compose en el NAS." >&2
  exit 1
fi

echo ""
echo "Contenedor iniciado correctamente."
echo "Estado:"
docker ps --filter "name=bodega-tablet" \
  --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

APP_PORT="$(sed -n 's/^BODEGA_TABLET_PORT=//p' .env | tail -n 1)"
case "$APP_PORT" in
  ''|*[!0-9]*) APP_PORT="8080" ;;
esac

echo ""
echo "Vista local: http://IP-DEL-NAS:$APP_PORT"

TAILSCALE_BIN="$(command -v tailscale 2>/dev/null || true)"
if [ -z "$TAILSCALE_BIN" ] && [ -x /var/packages/Tailscale/target/bin/tailscale ]; then
  TAILSCALE_BIN="/var/packages/Tailscale/target/bin/tailscale"
fi

if [ -n "$TAILSCALE_BIN" ]; then
  echo ""
  echo "Configurando HTTPS privado mediante Tailscale Serve..."
  if "$TAILSCALE_BIN" serve --bg "http://127.0.0.1:$APP_PORT"; then
    echo ""
    echo "Abra en la tablet la direccion HTTPS mostrada a continuacion:"
    "$TAILSCALE_BIN" serve status
  else
    echo "No fue posible activar Tailscale Serve automaticamente." >&2
    echo "Ejecutelo manualmente con:" >&2
    echo "sudo tailscale serve --bg http://127.0.0.1:$APP_PORT" >&2
  fi
else
  echo ""
  echo "No se encontro el comando tailscale en el NAS." >&2
  echo "Cuando este disponible, ejecute:" >&2
  echo "sudo tailscale serve --bg http://127.0.0.1:$APP_PORT" >&2
fi
