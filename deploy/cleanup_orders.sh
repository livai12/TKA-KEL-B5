#!/bin/bash
# ===========================================================================
# cleanup_orders.sh - Clean Locust Test Data Without Deleting Dump Data
# Target: Run on VM5 (MongoDB server) or any machine with mongosh access
#
# Strategy:
#   Method A (Recommended): Snapshot-based
#     1. BEFORE Locust run: record the current max created_at timestamp
#     2. AFTER Locust run: delete all orders/users with created_at > snapshot
#
#   Method B (Simple): Time-based
#     Delete orders created in the last N hours
#
# Usage:
#   ./cleanup_orders.sh snapshot-save    # Run BEFORE each Locust test
#   ./cleanup_orders.sh snapshot-clean   # Run AFTER each Locust test
#   ./cleanup_orders.sh time-clean [hours]  # Delete orders from last N hours (default: 2)
#   ./cleanup_orders.sh restore-stock    # Restore product stock from dump baseline
# ===========================================================================
set -e

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MONGODB_HOST="${MONGODB_HOST:-localhost}"
MONGODB_PORT="${MONGODB_PORT:-27017}"
MONGO_CONN="mongodb://${MONGODB_HOST}:${MONGODB_PORT}/orderdb"
SNAPSHOT_FILE="/tmp/locust_snapshot_timestamp.txt"

ACTION="${1:-help}"
HOURS="${2:-2}"

# ---------------------------------------------------------------------------
# Helper function
# ---------------------------------------------------------------------------
run_mongosh() {
  mongosh --quiet "$MONGO_CONN" --eval "$1"
}

# ===========================================================================
# Method A: Snapshot-Based Cleanup (Recommended)
# ===========================================================================

snapshot_save() {
  echo "[INFO] Recording current database state before Locust run..."

  # Get the latest created_at from orders collection
  TIMESTAMP=$(run_mongosh '
    var latest = db.orders.find().sort({created_at: -1}).limit(1).toArray();
    if (latest.length > 0) {
      print(latest[0].created_at.toISOString());
    } else {
      print(new Date().toISOString());
    }
  ')

  echo "$TIMESTAMP" > "$SNAPSHOT_FILE"
  echo "[OK] Snapshot timestamp saved: $TIMESTAMP"
  echo "     Saved to: $SNAPSHOT_FILE"

  # Also record counts for verification
  echo ""
  echo "[INFO] Current collection counts:"
  run_mongosh '
    print("  orders:     " + db.orders.countDocuments({}));
    print("  users:      " + db.users.countDocuments({}));
    print("  products:   " + db.products.countDocuments({}));
    print("  audit_logs: " + db.audit_logs.countDocuments({}));
  '

  echo ""
  echo "[INFO] Now run your Locust test. When done, run:"
  echo "       ./cleanup_orders.sh snapshot-clean"
}

snapshot_clean() {
  if [ ! -f "$SNAPSHOT_FILE" ]; then
    echo "[ERROR] No snapshot file found at $SNAPSHOT_FILE"
    echo "        Run './cleanup_orders.sh snapshot-save' before your Locust test."
    exit 1
  fi

  TIMESTAMP=$(cat "$SNAPSHOT_FILE")
  echo "[INFO] Cleaning data created after: $TIMESTAMP"
  echo ""

  # Show what will be deleted
  echo "[INFO] Documents to be deleted:"
  run_mongosh "
    var cutoff = new Date('${TIMESTAMP}');
    print('  orders:     ' + db.orders.countDocuments({created_at: {\$gt: cutoff}}));
    print('  users:      ' + db.users.countDocuments({created_at: {\$gt: cutoff}}));
    print('  audit_logs: ' + db.audit_logs.countDocuments({created_at: {\$gt: cutoff}}));
  "

  echo ""
  read -p "Proceed with deletion? [y/N] " -n 1 -r
  echo ""

  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "[INFO] Aborted."
    exit 0
  fi

  # Delete Locust-generated data
  echo "[INFO] Deleting Locust-generated orders..."
  run_mongosh "
    var cutoff = new Date('${TIMESTAMP}');

    var orderResult = db.orders.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + orderResult.deletedCount + ' orders');

    var userResult = db.users.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + userResult.deletedCount + ' users');

    var logResult = db.audit_logs.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + logResult.deletedCount + ' audit_logs');
  "

  # Show remaining counts
  echo ""
  echo "[INFO] Remaining collection counts:"
  run_mongosh '
    print("  orders:     " + db.orders.countDocuments({}));
    print("  users:      " + db.users.countDocuments({}));
    print("  products:   " + db.products.countDocuments({}));
    print("  audit_logs: " + db.audit_logs.countDocuments({}));
  '

  rm -f "$SNAPSHOT_FILE"
  echo ""
  echo "[OK] Cleanup complete. Snapshot file removed."
}

# ===========================================================================
# Method B: Time-Based Cleanup (Simple)
# ===========================================================================

time_clean() {
  echo "[INFO] Deleting orders created in the last ${HOURS} hour(s)..."
  echo ""

  # Show what will be deleted
  echo "[INFO] Documents to be deleted:"
  run_mongosh "
    var cutoff = new Date(Date.now() - ${HOURS} * 60 * 60 * 1000);
    print('  Cutoff time: ' + cutoff.toISOString());
    print('  orders:      ' + db.orders.countDocuments({created_at: {\$gt: cutoff}}));
    print('  users:       ' + db.users.countDocuments({created_at: {\$gt: cutoff}}));
    print('  audit_logs:  ' + db.audit_logs.countDocuments({created_at: {\$gt: cutoff}}));
  "

  echo ""
  read -p "Proceed with deletion? [y/N] " -n 1 -r
  echo ""

  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "[INFO] Aborted."
    exit 0
  fi

  run_mongosh "
    var cutoff = new Date(Date.now() - ${HOURS} * 60 * 60 * 1000);

    var orderResult = db.orders.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + orderResult.deletedCount + ' orders');

    var userResult = db.users.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + userResult.deletedCount + ' users');

    var logResult = db.audit_logs.deleteMany({created_at: {\$gt: cutoff}});
    print('[OK] Deleted ' + logResult.deletedCount + ' audit_logs');
  "

  echo ""
  echo "[OK] Time-based cleanup complete."
}

# ===========================================================================
# Stock Restoration
# ===========================================================================

restore_stock() {
  echo "[INFO] Restoring product stock from dump baseline..."
  echo "       This re-restores only the products collection."
  echo ""

  DUMP_PATH="/home/ubuntu/dump"
  if [ -d "$DUMP_PATH" ]; then
    mongorestore --drop \
      --nsInclude="orderdb.products" \
      "$DUMP_PATH"
    echo "[OK] Products collection restored from dump."
  else
    echo "[ERROR] Dump not found at $DUMP_PATH. Provide the path manually:"
    echo "        mongorestore --drop --nsInclude='orderdb.products' /path/to/dump"
  fi
}

# ===========================================================================
# Quick mongosh one-liners for manual use
# ===========================================================================

show_commands() {
  cat <<'CMDS'

=== Manual mongosh Commands ===

# Connect to MongoDB:
mongosh "mongodb://MONGODB_IP:27017/orderdb"

# Check current counts:
db.orders.countDocuments({})
db.users.countDocuments({})

# Get the latest order timestamp (for manual snapshot):
db.orders.find().sort({created_at:-1}).limit(1).forEach(o => print(o.created_at))

# Delete orders after a specific timestamp:
db.orders.deleteMany({created_at: {$gt: ISODate("2026-06-16T12:00:00Z")}})

# Delete users created during Locust (Locust creates users via /auth/register):
db.users.deleteMany({created_at: {$gt: ISODate("2026-06-16T12:00:00Z")}})

# Full reset (re-import everything from dump):
# mongorestore --drop /home/ubuntu/dump

CMDS
}

# ===========================================================================
# Main
# ===========================================================================

case "$ACTION" in
  snapshot-save)
    snapshot_save
    ;;
  snapshot-clean)
    snapshot_clean
    ;;
  time-clean)
    time_clean
    ;;
  restore-stock)
    restore_stock
    ;;
  commands)
    show_commands
    ;;
  help|*)
    echo "Usage: $0 <action> [args]"
    echo ""
    echo "Actions:"
    echo "  snapshot-save       Save current DB state (run BEFORE Locust test)"
    echo "  snapshot-clean      Delete data newer than snapshot (run AFTER Locust test)"
    echo "  time-clean [hours]  Delete data from the last N hours (default: 2)"
    echo "  restore-stock       Restore product stock from dump file"
    echo "  commands            Show useful mongosh one-liners for manual cleanup"
    echo ""
    echo "Recommended workflow:"
    echo "  1. ./cleanup_orders.sh snapshot-save"
    echo "  2. Run Locust test"
    echo "  3. ./cleanup_orders.sh snapshot-clean"
    echo "  4. ./cleanup_orders.sh restore-stock"
    echo "  5. Repeat for next scenario"
    ;;
esac
