#!/usr/bin/env bash
# GS ERP — Production deployment script
# Run this on your server after cloning the repo.
# Usage:  bash deploy.sh [--init-ssl]
set -euo pipefail

COMPOSE="docker compose -f docker/docker-compose.prod.yml"

# ── helpers ──────────────────────────────────────────────────────────────────
red()   { echo -e "\e[31m$*\e[0m"; }
green() { echo -e "\e[32m$*\e[0m"; }
info()  { echo -e "\e[34m>> $*\e[0m"; }

# ── preflight ────────────────────────────────────────────────────────────────
if [ ! -f ".env.production" ]; then
    red "ERROR: .env.production not found."
    echo "  cp .env.production.example .env.production"
    echo "  Then fill in DJANGO_SECRET_KEY, passwords, domain, etc."
    exit 1
fi

if ! command -v docker &>/dev/null; then
    red "ERROR: docker not installed."
    exit 1
fi

# ── optional: first-time SSL init ────────────────────────────────────────────
if [ "${1:-}" = "--init-ssl" ]; then
    DOMAIN=$(grep DJANGO_ALLOWED_HOSTS .env.production | cut -d= -f2 | cut -d, -f1)
    EMAIL=$(grep EMAIL_HOST_USER .env.production | cut -d= -f2)
    info "Obtaining SSL certificate for ${DOMAIN} ..."

    # Start nginx with HTTP-only config first
    $COMPOSE up -d nginx
    sleep 3

    $COMPOSE run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email \
        -d "${DOMAIN}" \
        -d "www.${DOMAIN}"

    green "SSL certificate obtained. Restart nginx."
    $COMPOSE restart nginx
fi

# ── build & deploy ───────────────────────────────────────────────────────────
info "Building production images ..."
$COMPOSE build --pull

info "Starting services ..."
$COMPOSE up -d

info "Waiting for API to be healthy ..."
sleep 8
$COMPOSE ps

green "Deployment complete!"
echo ""
echo "  Logs:    docker compose -f docker/docker-compose.prod.yml logs -f"
echo "  Shell:   docker compose -f docker/docker-compose.prod.yml exec api python manage.py shell"
echo "  Restart: docker compose -f docker/docker-compose.prod.yml restart"
