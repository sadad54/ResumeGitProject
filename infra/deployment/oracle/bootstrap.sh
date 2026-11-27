#!/bin/sh
# Runs on the VM (Ubuntu 24.04, arm64 or amd64), as the default `ubuntu` user
# with sudo. Idempotent: the first run installs Docker and opens the firewall,
# and every run rebuilds the image from the requested git ref and restarts.
#
#   sh bootstrap.sh <api-hostname> <git-ref>
#
# Expects /opt/proofhire/app.env (written by deploy_vm.py, mode 600).
set -eu
HOST="$1"
REF="${2:-master}"
REPO="https://github.com/sadad54/ResumeGitProject.git"
DIR=/opt/proofhire

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi
DOCKER="sudo docker"

# Oracle's Ubuntu images ship iptables rules that reject everything but SSH.
# The VCN security list must also allow 80/443 (done in the console).
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save >/dev/null
fi

sudo mkdir -p "$DIR"
sudo chown "$USER" "$DIR"
if [ -d "$DIR/src/.git" ]; then
  git -C "$DIR/src" fetch --depth 1 origin "$REF"
  git -C "$DIR/src" checkout -q --force FETCH_HEAD
else
  git clone --depth 1 --branch "$REF" "$REPO" "$DIR/src"
fi
echo "source: $(git -C "$DIR/src" rev-parse --short HEAD) ($REF)"

$DOCKER build -f "$DIR/src/infra/docker/Dockerfile.space" -t proofhire-api "$DIR/src"

$DOCKER network inspect proofhire >/dev/null 2>&1 || $DOCKER network create proofhire >/dev/null

$DOCKER rm -f proofhire-api >/dev/null 2>&1 || true
$DOCKER run -d --name proofhire-api --network proofhire --restart unless-stopped \
  --env-file "$DIR/app.env" -e PORT=7860 \
  -v proofhire-data:/data \
  proofhire-api >/dev/null

# Caddy terminates TLS with an automatic Let's Encrypt certificate for
# $HOST (an sslip.io name needs no DNS setup) and proxies to the API,
# streaming SSE without buffering.
cat > "$DIR/Caddyfile" <<EOF
$HOST {
	encode gzip
	reverse_proxy proofhire-api:7860 {
		flush_interval -1
	}
}
EOF
$DOCKER rm -f proofhire-caddy >/dev/null 2>&1 || true
$DOCKER run -d --name proofhire-caddy --network proofhire --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v "$DIR/Caddyfile:/etc/caddy/Caddyfile:ro" -v caddy-data:/data \
  caddy:2 >/dev/null

$DOCKER image prune -f >/dev/null
echo "waiting for the API to come up..."
for i in $(seq 1 90); do
  if $DOCKER exec proofhire-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/ready')" 2>/dev/null; then
    echo "api: ready"
    exit 0
  fi
  sleep 2
done
$DOCKER logs --tail 80 proofhire-api
echo "api: not ready after 3 minutes (logs above)" >&2
exit 1
