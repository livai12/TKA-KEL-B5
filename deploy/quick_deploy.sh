#!/bin/bash
# ===========================================================================
# quick_deploy.sh - One-Script Deployment for FP TKA 26
# ===========================================================================
# Jalankan script ini di dalam VM yang sesuai.
# Script ini mendeteksi hostname VM dan menjalankan setup yang tepat.
#
# Cara pakai (setelah vagrant ssh):
#   cd /vagrant/deploy && bash quick_deploy.sh
# ===========================================================================
set -e

# ---------------------------------------------------------------------------
# KONFIGURASI - Sesuaikan IP ini dengan VM Anda
# ---------------------------------------------------------------------------
IP_VM1_LB="192.168.56.10"
IP_VM2_APP1="192.168.56.11"
IP_VM3_APP2="192.168.56.12"
IP_VM4_APP3="192.168.56.13"
IP_VM5_MONGODB="192.168.56.14"

JWT_SECRET="fp-tka-26-super-secret-key-2026"

# ---------------------------------------------------------------------------
# Deteksi VM berdasarkan hostname
# ---------------------------------------------------------------------------
HOSTNAME=$(hostname)
echo "=========================================="
echo " Quick Deploy - Detected hostname: ${HOSTNAME}"
echo "=========================================="

case "$HOSTNAME" in
  db-server)
    echo "[INFO] Setting up MongoDB on VM5..."
    # Override dump path for Vagrant synced folder
    export DUMP_PATH="/vagrant/Resources/DB/dump"
    bash /vagrant/deploy/setup_mongodb.sh
    ;;

  app-server-1|app-server-2|app-server-3)
    echo "[INFO] Setting up App Server on ${HOSTNAME}..."

    # Patch MONGO_URI dan JWT_SECRET sebelum jalankan
    cd /vagrant/deploy
    sed -i "s|MONGO_URI=.*|MONGO_URI=\"mongodb://${IP_VM5_MONGODB}:27017/\"|" setup_appserver.sh
    sed -i "s|JWT_SECRET=.*|JWT_SECRET=\"${JWT_SECRET}\"|" setup_appserver.sh

    bash setup_appserver.sh
    ;;

  load-balancer)
    echo "[INFO] Setting up Nginx Load Balancer on VM1..."

    # Patch IP addresses sebelum jalankan
    cd /vagrant/deploy
    sed -i "s|APP_SERVER_1_IP=.*|APP_SERVER_1_IP=\"${IP_VM2_APP1}\"|" setup_nginx.sh
    sed -i "s|APP_SERVER_2_IP=.*|APP_SERVER_2_IP=\"${IP_VM3_APP2}\"|" setup_nginx.sh
    sed -i "s|APP_SERVER_3_IP=.*|APP_SERVER_3_IP=\"${IP_VM4_APP3}\"|" setup_nginx.sh

    bash setup_nginx.sh
    ;;

  *)
    echo "[ERROR] Hostname tidak dikenali: ${HOSTNAME}"
    echo "        Hostname yang diharapkan:"
    echo "          db-server      -> MongoDB"
    echo "          app-server-1   -> App Server 1"
    echo "          app-server-2   -> App Server 2"
    echo "          app-server-3   -> App Server 3"
    echo "          load-balancer  -> Nginx LB"
    echo ""
    echo "        Set hostname manual: sudo hostnamectl set-hostname <nama>"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo " Deployment selesai untuk: ${HOSTNAME}"
echo "=========================================="
