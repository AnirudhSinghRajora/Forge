#!/usr/bin/env bash
# Runs FasalSaakshi on one Ubuntu/Debian VM with HTTPS. Safe to re-run: it rebuilds and replaces the app.
# Sealed evidence stays on the fasalsaakshi-data volume, so QR verify links survive a redeploy.
#
#   sudo DOMAIN=your.domain GEMINI_API_KEY=... ./deploy/run-on-vm.sh
#
# With no DOMAIN it uses <public-ip>.sslip.io, which needs no DNS setup. Ports 80 and 443 must be open.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null || { apt-get update -y; apt-get install -y docker.io; systemctl enable --now docker; }

if [ -z "${DOMAIN:-}" ]; then
  ip=$(curl -fsS https://api.ipify.org)
  DOMAIN="${ip}.sslip.io"
fi
TOKEN_FILE=/var/lib/fasalsaakshi-scheduler-token
[ -s "$TOKEN_FILE" ] || { openssl rand -hex 32 > "$TOKEN_FILE"; chmod 600 "$TOKEN_FILE"; }

docker build -t fasalsaakshi:latest .
docker network inspect fasalsaakshi >/dev/null 2>&1 || docker network create fasalsaakshi >/dev/null

docker rm -f fasalsaakshi >/dev/null 2>&1 || true
docker run -d --name fasalsaakshi --restart unless-stopped --network fasalsaakshi \
  -v fasalsaakshi-data:/data \
  -e PUBLIC_WEB_URL="https://${DOMAIN}" \
  -e TRUST_PROXY=true \
  -e GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
  -e SCHEDULER_TOKEN="$(cat "$TOKEN_FILE")" \
  fasalsaakshi:latest

mkdir -p /etc/fasalsaakshi
cat > /etc/fasalsaakshi/Caddyfile <<CADDY
${DOMAIN} {
  encode gzip
  reverse_proxy fasalsaakshi:8080 {
    flush_interval -1
  }
}
CADDY
docker rm -f fasalsaakshi-https >/dev/null 2>&1 || true
docker run -d --name fasalsaakshi-https --restart unless-stopped --network fasalsaakshi \
  -p 80:80 -p 443:443 \
  -v /etc/fasalsaakshi/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v fasalsaakshi-caddy:/data \
  docker.io/library/caddy:2

for _ in $(seq 1 60); do
  curl -fsS -m 5 "https://${DOMAIN}/api/health" && { echo; echo "Live at https://${DOMAIN}"; exit 0; }
  sleep 5
done
echo "App did not answer at https://${DOMAIN}. Check: docker logs fasalsaakshi; docker logs fasalsaakshi-https" >&2
exit 1
