FROM nginx:stable-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js logic.js manifest.webmanifest service-worker.js /usr/share/nginx/html/
COPY icon.svg icon-192.png icon-512.png /usr/share/nginx/html/
COPY config.template.js /opt/bodega/config.template.js
COPY docker-entrypoint.d/40-bodega-config.sh /docker-entrypoint.d/40-bodega-config.sh

RUN sed -i 's/\r$//' /docker-entrypoint.d/40-bodega-config.sh \
    && chmod +x /docker-entrypoint.d/40-bodega-config.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health || exit 1
