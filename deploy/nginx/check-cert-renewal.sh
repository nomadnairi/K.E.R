#!/bin/sh
# Verifies the live certificate is not close to expiring — i.e. that
# automatic renewal is actually working, not just configured. Certbot tries
# to renew inside the last 30 days of validity, so anything under 20 days
# remaining means renewal has silently failed at least once.
#
# Runs INSIDE the `certbot` container (mounted read-only at /scripts, see
# docker-compose.prod.yml), where /etc/letsencrypt and $DOMAIN already exist —
# wired as that container's Docker healthcheck, so `docker compose ps` visibly
# flips to "unhealthy" the moment this happens. That is the "automatic
# verification" requirement. Also runnable by hand at any time:
#
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#       exec certbot /scripts/check-cert-renewal.sh
#
set -eu

MIN_DAYS="${CERT_MIN_DAYS:-20}"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

if [ -z "${DOMAIN:-}" ]; then
    echo "DOMAIN is not set — nothing to check yet." >&2
    exit 1
fi

if [ ! -f "$CERT_PATH" ]; then
    echo "No certificate found at $CERT_PATH yet — run deploy/nginx/init-letsencrypt.sh first." >&2
    exit 1
fi

END_DATE=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
MIN_SECONDS=$(( MIN_DAYS * 86400 ))

# -checkend <seconds> avoids any date-parsing portability issues (Alpine's
# busybox `date` doesn't reliably parse OpenSSL's enddate format) — it exits
# non-zero exactly when the cert has fewer than <seconds> left, which is
# precisely what we want to check.
if ! openssl x509 -checkend "$MIN_SECONDS" -noout -in "$CERT_PATH"; then
    echo "FAIL: certificate for $DOMAIN (expires $END_DATE) has fewer than $MIN_DAYS days remaining — automatic renewal appears to have failed." >&2
    exit 1
fi

echo "OK: certificate for $DOMAIN expires $END_DATE — renewal is healthy."
