#!/usr/bin/env bash
# One-time bootstrap for Nginx + Let's Encrypt.
#
# Run this ONCE, on the VPS, from the repo root, after DOMAIN and
# LETSENCRYPT_EMAIL are set in .env and the domain's DNS A record already
# points at this server (see docs/INFRASTRUCTURE.md — "Настройка домена" /
# "Настройка DNS"). Everything after this is fully automatic (the `certbot`
# container renews on its own; Nginx reloads itself periodically to pick up
# the renewed cert — see docs/INFRASTRUCTURE.md — "Автоматическое продление").
#
# Safe to re-run: it skips steps that already completed.
set -euo pipefail
cd "$(dirname "$0")/../.."   # repo root

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

if [ ! -f .env ]; then
    echo "Missing .env — copy .env.example to .env and fill in DOMAIN / LETSENCRYPT_EMAIL first." >&2
    exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

if [ -z "${DOMAIN:-}" ] || [ "$DOMAIN" = "example.com" ]; then
    echo "DOMAIN is not set in .env — nothing to do until a real domain points at this server." >&2
    exit 1
fi
if [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
    echo "LETSENCRYPT_EMAIL is not set in .env — Let's Encrypt needs an email for expiry notices." >&2
    exit 1
fi

STAGING="${CERTBOT_STAGING:-1}"
STAGING_ARG=""
if [ "$STAGING" = "1" ]; then
    STAGING_ARG="--staging"
    echo "== CERTBOT_STAGING=1: requesting a STAGING certificate (not trusted by browsers, no rate limits)."
    echo "   Set CERTBOT_STAGING=0 in .env and re-run once you've verified the flow end-to-end."
fi

echo "== 1/5 Ensuring the certbot/nginx named volumes exist and a DH param file is present..."
docker volume create ker_nginx_dhparam >/dev/null
if ! docker run --rm -v ker_nginx_dhparam:/out alpine test -f /out/dhparam.pem; then
    echo "   Generating a 2048-bit DH param (one-time, ~1-2 min)..."
    docker run --rm -v ker_nginx_dhparam:/out alpine sh -c \
        "apk add --no-cache openssl >/dev/null && openssl dhparam -out /out/dhparam.pem 2048"
else
    echo "   Already present, skipping."
fi

echo "== 2/5 Creating a temporary self-signed certificate so Nginx can start..."
docker run --rm \
    -v ker_certbot_etc:/etc/letsencrypt \
    alpine sh -c "
        apk add --no-cache openssl >/dev/null
        mkdir -p /etc/letsencrypt/live/$DOMAIN
        [ -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ] && exit 0
        openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
            -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
            -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
            -subj '/CN=localhost'
    "

echo "== 3/5 Starting Nginx with the temporary certificate..."
$COMPOSE up -d nginx

echo "== 4/5 Deleting the temporary certificate and requesting the real one from Let's Encrypt..."
docker run --rm -v ker_certbot_etc:/etc/letsencrypt alpine \
    rm -rf "/etc/letsencrypt/live/$DOMAIN" "/etc/letsencrypt/archive/$DOMAIN" "/etc/letsencrypt/renewal/$DOMAIN.conf"

$COMPOSE run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
        --email "$LETSENCRYPT_EMAIL" -d "$DOMAIN" \
        --rsa-key-size 4096 --agree-tos --no-eff-email $STAGING_ARG

echo "== 5/5 Reloading Nginx with the real certificate..."
$COMPOSE exec nginx nginx -s reload

echo
echo "Done. Certificate for $DOMAIN is live."
if [ "$STAGING" = "1" ]; then
    echo "Reminder: this was a STAGING certificate. Set CERTBOT_STAGING=0 in .env and re-run this"
    echo "script to get a browser-trusted certificate (this deletes the staging cert first)."
fi
echo "The 'certbot' container now renews automatically every ~12h (only actually renews inside"
echo "the last 30 days of validity); Nginx reloads itself every 6h to pick up the new cert."
echo "Verify anytime with: deploy/nginx/check-cert-renewal.sh"
