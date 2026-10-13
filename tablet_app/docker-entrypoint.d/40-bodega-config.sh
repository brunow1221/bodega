#!/bin/sh
set -eu

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_PUBLISHABLE_KEY:-}" ]; then
  echo "Faltan SUPABASE_URL o SUPABASE_PUBLISHABLE_KEY." >&2
  exit 1
fi

envsubst '${SUPABASE_URL} ${SUPABASE_PUBLISHABLE_KEY}' \
  < /opt/bodega/config.template.js \
  > /usr/share/nginx/html/config.js

