#!/bin/sh
# Wraps the official nginx image's entrypoint so the renewed certificate is
# picked up automatically, with no Docker-socket mount and no extra
# container: this process reloads Nginx in place every 6 hours. A reload with
# an unchanged certificate is a harmless no-op (Nginx just re-reads the same
# files and starts new worker processes) — simpler and just as reliable as
# watching the cert files for changes.
set -e

reload_loop() {
    while true; do
        sleep 6h
        nginx -s reload 2>/dev/null || true
    done
}

reload_loop &

# Hand off to the image's real entrypoint (renders templates/*.template via
# envsubst, then execs `nginx -g "daemon off;"`).
exec /docker-entrypoint.sh "$@"
