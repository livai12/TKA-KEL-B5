#!/bin/bash
# ===========================================================================
# setup_nginx.sh - Nginx Load Balancer + Frontend Setup
# Target: VM1 (1vCPU, 512MB RAM) - Ubuntu 22.04 LTS
# Serves static frontend and proxies API to Flask backends
# ===========================================================================
set -e

# ---------------------------------------------------------------------------
# PLACEHOLDER VARIABLES - Replace with actual IPs before running!
# ---------------------------------------------------------------------------
APP_SERVER_1_IP="REPLACE_WITH_VM2_IP"
APP_SERVER_2_IP="REPLACE_WITH_VM3_IP"
APP_SERVER_3_IP="REPLACE_WITH_VM4_IP"

echo "=========================================="
echo " Nginx Load Balancer + Frontend Setup - VM1"
echo "=========================================="

# ---------------------------------------------------------------------------
# Validate placeholder IPs are filled in
# ---------------------------------------------------------------------------
if echo "$APP_SERVER_1_IP $APP_SERVER_2_IP $APP_SERVER_3_IP" | grep -q "REPLACE"; then
  echo "[ERROR] You must replace placeholder IPs before running this script!"
  echo "        Edit this script and set APP_SERVER_1_IP, APP_SERVER_2_IP, APP_SERVER_3_IP"
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Install Nginx
# ---------------------------------------------------------------------------
echo "[INFO] Installing Nginx..."
sudo apt-get update -qq
sudo apt-get install -y nginx curl

echo "[OK] Nginx installed: $(nginx -v 2>&1)"

# ---------------------------------------------------------------------------
# 2. Configure main nginx.conf (worker tuning)
# ---------------------------------------------------------------------------
echo "[INFO] Configuring main nginx.conf..."

sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak

sudo tee /etc/nginx/nginx.conf > /dev/null <<'NGINX_MAIN'
# Main nginx.conf - Tuned for VM1 (1vCPU, 512MB RAM)
user www-data;
worker_processes auto;              # Auto-detect CPU cores (will be 1 on this VM)
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 2048;         # Max connections per worker
    multi_accept on;                 # Accept multiple connections at once
    use epoll;                       # Efficient event model for Linux
}

http {
    # ---- Basic settings ----
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;               # Hide Nginx version in headers

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # ---- Logging ----
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # ---- Gzip compression ----
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 4;
    gzip_min_length 256;
    gzip_types
        text/plain
        text/css
        text/xml
        application/json
        application/javascript
        application/xml
        application/xml+rss
        text/javascript;

    # ---- Connection limits (DDoS mitigation) ----
    # Uncomment if needed:
    # limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

    # ---- Include site configurations ----
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
NGINX_MAIN

echo "[OK] Main nginx.conf configured."

# ---------------------------------------------------------------------------
# 3. Deploy site configuration (from nginx.conf in deploy/)
# ---------------------------------------------------------------------------
echo "[INFO] Deploying site configuration..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_CONF="${SCRIPT_DIR}/nginx.conf"

if [ ! -f "$SITE_CONF" ]; then
  echo "[ERROR] Site configuration file not found at: ${SITE_CONF}"
  exit 1
fi

# Copy and replace placeholder IPs with actual IPs
sudo cp "$SITE_CONF" /etc/nginx/sites-available/orderservice
sudo sed -i "s/APP_SERVER_1_IP/${APP_SERVER_1_IP}/g" /etc/nginx/sites-available/orderservice
sudo sed -i "s/APP_SERVER_2_IP/${APP_SERVER_2_IP}/g" /etc/nginx/sites-available/orderservice
sudo sed -i "s/APP_SERVER_3_IP/${APP_SERVER_3_IP}/g" /etc/nginx/sites-available/orderservice

echo "[OK] Placeholder IPs replaced in site configuration."

# ---------------------------------------------------------------------------
# 4. Enable site, remove default
# ---------------------------------------------------------------------------
echo "[INFO] Enabling site configuration..."

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Enable our site
sudo ln -sf /etc/nginx/sites-available/orderservice /etc/nginx/sites-enabled/orderservice

echo "[OK] Site enabled, default site removed."

# ---------------------------------------------------------------------------
# 5. Deploy frontend static files
# ---------------------------------------------------------------------------
echo "[INFO] Deploying frontend files..."

sudo mkdir -p /var/www/frontend
SOURCE_FE="${SCRIPT_DIR}/../Resources/FE"

if [ -d "$SOURCE_FE" ]; then
  sudo cp "${SOURCE_FE}/index.html" /var/www/frontend/
  sudo cp "${SOURCE_FE}/styles.css" /var/www/frontend/
  sudo chown -R www-data:www-data /var/www/frontend
  echo "[OK] Frontend files deployed to /var/www/frontend/"
else
  echo "[WARNING] Frontend source not found at ${SOURCE_FE}"
  echo "          Manually copy index.html and styles.css to /var/www/frontend/"
fi

# ---------------------------------------------------------------------------
# 6. Test and restart Nginx
# ---------------------------------------------------------------------------
echo "[INFO] Testing Nginx configuration..."

if sudo nginx -t 2>&1; then
  echo "[OK] Nginx configuration test passed."
else
  echo "[ERROR] Nginx configuration test failed!"
  exit 1
fi

echo "[INFO] Restarting Nginx..."
sudo systemctl restart nginx
sudo systemctl enable nginx

if sudo systemctl is-active --quiet nginx; then
  echo "[OK] Nginx is running."
else
  echo "[ERROR] Nginx failed to start."
  sudo journalctl -u nginx --no-pager -n 20
  exit 1
fi

# ---------------------------------------------------------------------------
# 7. Verification
# ---------------------------------------------------------------------------
echo ""
echo "[INFO] Running verification checks..."

# Check frontend
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  echo "[OK] Frontend is accessible (HTTP 200)."
else
  echo "[WARNING] Frontend returned HTTP ${HTTP_CODE}. Check /var/www/frontend/ files."
fi

# Check backend proxy (may fail if backends aren't set up yet)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost/health || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  echo "[OK] Backend health check passed via proxy (HTTP 200)."
  curl -s http://localhost/health | python3 -m json.tool 2>/dev/null || true
else
  echo "[INFO] Backend health check returned HTTP ${HTTP_CODE}."
  echo "       This is expected if app servers are not yet set up."
fi

echo ""
echo "[INFO] Upstream servers configured:"
grep "server " /etc/nginx/sites-available/orderservice | grep -v "#" | sed 's/^/  /'

echo ""
echo "=========================================="
echo " Nginx setup complete!"
echo " Frontend: http://<THIS_VM_IP>/"
echo " API Proxy: http://<THIS_VM_IP>/health"
echo " Control: sudo systemctl {start|stop|restart|status} nginx"
echo "=========================================="
