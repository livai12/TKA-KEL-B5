#!/bin/bash
# ===========================================================================
# setup_appserver.sh - Flask Application Server Setup
# Target: VM2, VM3, VM4 (1vCPU, 2GB RAM each) - Ubuntu 22.04 LTS
# Runs Gunicorn with gevent workers behind Nginx load balancer
# ===========================================================================
set -e

# ---------------------------------------------------------------------------
# PLACEHOLDER VARIABLES - Fill these in before running!
# ---------------------------------------------------------------------------
MONGO_URI="mongodb://70.153.192.147:27017/"
JWT_SECRET="ganti-ini-di-production-dengan-string-acak-panjang"

# Application settings
APP_USER="${SUDO_USER:-$(whoami)}"
APP_DIR="/home/${APP_USER}/app"
VENV_DIR="${APP_DIR}/venv"
GUNICORN_WORKERS=3          # 3 workers for 1vCPU (2*CPU+1)
GUNICORN_WORKER_CLASS="gevent"
GUNICORN_BIND="0.0.0.0:5000"
GUNICORN_MAX_REQUESTS=1000  # Restart workers after N requests (memory leak prevention)
GUNICORN_MAX_REQUESTS_JITTER=50  # Randomize restart to avoid thundering herd

echo "=========================================="
echo " Flask App Server Setup"
echo "=========================================="

# ---------------------------------------------------------------------------
# 1. Install system dependencies
# ---------------------------------------------------------------------------
echo "[INFO] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv build-essential \
  python3-dev libffi-dev curl

echo "[OK] System packages installed."
echo "[INFO] Python version: $(python3 --version)"

# ---------------------------------------------------------------------------
# 2. Create application directory structure
# ---------------------------------------------------------------------------
echo "[INFO] Setting up application directory..."
sudo mkdir -p "$APP_DIR"
sudo chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

# ---------------------------------------------------------------------------
# 3. Copy application files
# ---------------------------------------------------------------------------
echo "[INFO] Copying application files..."

# Determine where the source files are relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_BE="${SCRIPT_DIR}/../Resources/BE"

if [ -f "${SOURCE_BE}/app.py" ]; then
  cp "${SOURCE_BE}/app.py" "${APP_DIR}/app.py"
  cp "${SOURCE_BE}/requirements.txt" "${APP_DIR}/requirements.txt"
  echo "[OK] Application files copied from ${SOURCE_BE}"
else
  echo "[WARNING] Source files not found at ${SOURCE_BE}"
  echo "          Make sure app.py and requirements.txt are in ${APP_DIR}"
fi

# ---------------------------------------------------------------------------
# 4. Create virtual environment and install dependencies
# ---------------------------------------------------------------------------
echo "[INFO] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

echo "[INFO] Installing Python dependencies..."
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel --quiet
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt" --quiet
"${VENV_DIR}/bin/pip" install gevent --quiet

echo "[OK] Python dependencies installed:"
"${VENV_DIR}/bin/pip" list --format=columns | grep -iE "flask|pymongo|gunicorn|gevent|bcrypt|jwt"

# ---------------------------------------------------------------------------
# 5. Create systemd service file
# ---------------------------------------------------------------------------
echo "[INFO] Creating systemd service..."

sudo tee /etc/systemd/system/flask-app.service > /dev/null <<EOF
[Unit]
Description=Flask Order Processing Service (Gunicorn)
After=network.target
Wants=network-online.target

[Service]
Type=notify
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/bin"
Environment="MONGO_URI=${MONGO_URI}"
Environment="JWT_SECRET=${JWT_SECRET}"
ExecStart=${VENV_DIR}/bin/gunicorn \
  --workers ${GUNICORN_WORKERS} \
  --worker-class ${GUNICORN_WORKER_CLASS} \
  --bind ${GUNICORN_BIND} \
  --max-requests ${GUNICORN_MAX_REQUESTS} \
  --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER} \
  --timeout 30 \
  --keep-alive 5 \
  --access-logfile /var/log/gunicorn/access.log \
  --error-logfile /var/log/gunicorn/error.log \
  --log-level info \
  app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=10

# Hardening
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

echo "[OK] Systemd service file created."

# ---------------------------------------------------------------------------
# 6. Create log directory
# ---------------------------------------------------------------------------
echo "[INFO] Creating log directory..."
sudo mkdir -p /var/log/gunicorn
sudo chown -R "${APP_USER}:${APP_USER}" /var/log/gunicorn

# ---------------------------------------------------------------------------
# 7. Start the service
# ---------------------------------------------------------------------------
echo "[INFO] Starting Flask application service..."
sudo systemctl daemon-reload
sudo systemctl enable flask-app
sudo systemctl restart flask-app

# Wait for service to become ready
echo "[INFO] Waiting for application to start..."
sleep 3

if sudo systemctl is-active --quiet flask-app; then
  echo "[OK] flask-app service is running."
else
  echo "[ERROR] flask-app service failed to start."
  sudo journalctl -u flask-app --no-pager -n 20
  exit 1
fi

# ---------------------------------------------------------------------------
# 8. Verification
# ---------------------------------------------------------------------------
echo ""
echo "[INFO] Running health check..."
sleep 2

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
  echo "[OK] Health check passed (HTTP 200)."
  curl -s http://localhost:5000/health | python3 -m json.tool
else
  echo "[ERROR] Health check failed (HTTP ${HTTP_CODE})."
  echo "        Check logs with: sudo journalctl -u flask-app -f"
  exit 1
fi

echo ""
echo "[INFO] Gunicorn process info:"
ps aux | grep gunicorn | grep -v grep || true

echo ""
echo "=========================================="
echo " App server setup complete!"
echo " Service: flask-app (port 5000)"
echo " Logs:    /var/log/gunicorn/"
echo " Control: sudo systemctl {start|stop|restart|status} flask-app"
echo "=========================================="
