#!/bin/bash
# ===========================================================================
# setup_mongodb.sh - MongoDB 7.0 Installation & Configuration
# Target: VM5 (2vCPU, 4GB RAM) - Ubuntu 22.04 LTS
# Database: orderdb
# ===========================================================================
set -e

# ---------------------------------------------------------------------------
# Placeholder - fill in your actual MongoDB server IP
# ---------------------------------------------------------------------------
MONGODB_BIND_IP="0.0.0.0"
DUMP_PATH="/home/ubuntu/dump"   # Path to the mongorestore dump directory

echo "=========================================="
echo " MongoDB 7.0 Setup - VM5 (Database Server)"
echo "=========================================="

# ---------------------------------------------------------------------------
# 1. Install MongoDB 7.0
# ---------------------------------------------------------------------------
echo "[INFO] Installing prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y gnupg curl

echo "[INFO] Adding MongoDB 7.0 GPG key and repository..."
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg

echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list > /dev/null

sudo apt-get update -qq
sudo apt-get install -y mongodb-org

echo "[OK] MongoDB 7.0 installed: $(mongod --version | head -1)"

# ---------------------------------------------------------------------------
# 2. Configure MongoDB
# ---------------------------------------------------------------------------
echo "[INFO] Configuring MongoDB..."

sudo cp /etc/mongod.conf /etc/mongod.conf.bak

sudo tee /etc/mongod.conf > /dev/null <<'MONGOD_CONF'
# mongod.conf - Tuned for VM5 (2vCPU, 4GB RAM)

storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      # WiredTiger Cache Size Tuning for 4GB RAM
      # -----------------------------------------------
      # Default formula: 50% of (RAM - 1GB) = 50% of 3GB = 1.5GB
      # We set it to 1.5GB explicitly. This leaves ~2.5GB for:
      #   - OS page cache (~1GB, caches frequently accessed data files)
      #   - mongod process overhead (~200-300MB)
      #   - OS and other processes (~1.2GB)
      # For a 4GB VM, do NOT exceed 2GB here or the OS will start swapping.
      cacheSizeGB: 1.5

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 0.0.0.0
  # WARNING: In production, restrict bindIp to specific app server IPs.
  # Example: bindIp: 127.0.0.1,APP_SERVER_1_IP,APP_SERVER_2_IP,APP_SERVER_3_IP

processManagement:
  timeZoneInfo: /usr/share/zoneinfo

# NOTE: Authentication is disabled for simplicity in this lab setup.
# For production, uncomment and configure:
# security:
#   authorization: enabled
MONGOD_CONF

echo "[OK] MongoDB configuration written."

# ---------------------------------------------------------------------------
# 3. Start MongoDB
# ---------------------------------------------------------------------------
echo "[INFO] Starting MongoDB service..."
sudo systemctl daemon-reload
sudo systemctl enable mongod
sudo systemctl restart mongod

# Wait for MongoDB to become ready
echo "[INFO] Waiting for MongoDB to start..."
for i in $(seq 1 15); do
  if mongosh --quiet --eval "db.runCommand({ping:1})" > /dev/null 2>&1; then
    echo "[OK] MongoDB is running and accepting connections."
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "[ERROR] MongoDB failed to start within 15 seconds."
    sudo journalctl -u mongod --no-pager -n 20
    exit 1
  fi
  sleep 1
done

# ---------------------------------------------------------------------------
# 4. Restore dump data
# ---------------------------------------------------------------------------
if [ -d "$DUMP_PATH" ]; then
  echo "[INFO] Restoring database dump from $DUMP_PATH ..."
  mongorestore --drop "$DUMP_PATH"
  echo "[OK] Database dump restored successfully."
else
  echo "[WARNING] Dump directory not found at $DUMP_PATH"
  echo "          Upload the dump folder and run:"
  echo "          mongorestore --drop $DUMP_PATH"
fi

# ---------------------------------------------------------------------------
# 5. Create indexes for orderdb
# ---------------------------------------------------------------------------
echo "[INFO] Creating indexes on orderdb collections..."

mongosh --quiet orderdb <<'INDEXES'
// ---- orders collection ----
// Lookup by order_id (used in GET /orders/<order_id>)
db.orders.createIndex({ "order_id": 1 }, { name: "idx_order_id" });

// Compound: user orders sorted by date (used in GET /orders for user)
db.orders.createIndex({ "user_id": 1, "created_at": -1 }, { name: "idx_user_created" });

// Filter by status (used in order list filtering and admin stats)
db.orders.createIndex({ "status": 1 }, { name: "idx_status" });

// Sort by created_at descending (used in order list default sort)
db.orders.createIndex({ "created_at": -1 }, { name: "idx_created_at" });

// ---- products collection ----
// Compound: category + is_active (used in GET /products with category filter)
db.products.createIndex({ "category": 1, "is_active": 1 }, { name: "idx_category_active" });

// Text search on product name (used in GET /products?search=...)
db.products.createIndex({ "name": "text" }, { name: "idx_name_text" });

// ---- users collection ----
// Unique email (used in login and registration)
db.users.createIndex({ "email": 1 }, { unique: true, name: "idx_email_unique" });

// ---- audit_logs collection ----
// Sort by created_at (used in GET /admin/logs)
db.audit_logs.createIndex({ "created_at": -1 }, { name: "idx_auditlog_created" });

print("[OK] All indexes created successfully.");
printjson(db.orders.getIndexes());
printjson(db.products.getIndexes());
printjson(db.users.getIndexes());
printjson(db.audit_logs.getIndexes());
INDEXES

# ---------------------------------------------------------------------------
# 6. Verification
# ---------------------------------------------------------------------------
echo ""
echo "[INFO] Running verification checks..."

COLLECTIONS=$(mongosh --quiet orderdb --eval "db.getCollectionNames().join(', ')")
echo "[OK] Collections in orderdb: $COLLECTIONS"

ORDER_COUNT=$(mongosh --quiet orderdb --eval "db.orders.countDocuments({})")
echo "[OK] Orders count: $ORDER_COUNT"

PRODUCT_COUNT=$(mongosh --quiet orderdb --eval "db.products.countDocuments({})")
echo "[OK] Products count: $PRODUCT_COUNT"

USER_COUNT=$(mongosh --quiet orderdb --eval "db.users.countDocuments({})")
echo "[OK] Users count: $USER_COUNT"

# Show WiredTiger cache info
echo ""
echo "[INFO] WiredTiger cache status:"
mongosh --quiet orderdb --eval "
  var status = db.serverStatus().wiredTiger.cache;
  print('  Maximum cache size: ' + Math.round(status['maximum bytes configured'] / 1024 / 1024) + ' MB');
  print('  Current cache used: ' + Math.round(status['bytes currently in the cache'] / 1024 / 1024) + ' MB');
"

echo ""
echo "=========================================="
echo " MongoDB setup complete!"
echo " Connection string: mongodb://<THIS_VM_IP>:27017/orderdb"
echo "=========================================="
