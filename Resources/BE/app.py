"""
Order Processing Service — Backend API
Flask + MongoDB + JWT Auth

Collections:
    users       — akun user & admin
    products    — katalog produk
    orders      — transaksi pesanan
    audit_logs  — log aksi admin

Env vars:
    MONGO_URI   — default: mongodb://localhost:27017/
    JWT_SECRET  — default: ganti-ini-di-production
    JWT_EXPIRES — default: 86400 (detik = 24 jam)

Install:
    pip install flask pymongo bcrypt PyJWT
Run:
    python app.py
    gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""

import os
from datetime import datetime, timezone, timedelta
from functools import wraps

import bcrypt
import jwt
from bson import ObjectId
from flask import Flask, jsonify, request, g
from pymongo import MongoClient, DESCENDING, ASCENDING

# ═══════════════════════════════════════════
# Config
# ═══════════════════════════════════════════
app = Flask(__name__)

MONGO_URI   = os.environ.get("MONGO_URI",   "mongodb://localhost:27017/")
JWT_SECRET  = os.environ.get("JWT_SECRET",  "ganti-ini-di-production-dengan-string-acak-panjang")
JWT_EXPIRES = int(os.environ.get("JWT_EXPIRES", 86400))

client = MongoClient(MONGO_URI)
db     = client["orderdb"]

users_col  = db["users"]
prods_col  = db["products"]
orders_col = db["orders"]
logs_col   = db["audit_logs"]

# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════

def now_iso():
    return datetime.now(timezone.utc)

def serialize(doc: dict) -> dict:
    """Konversi ObjectId dan datetime ke string agar JSON-serializable."""
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [serialize(i) if isinstance(i, dict) else
                      (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, dict):
            out[k] = serialize(v)
        else:
            out[k] = v
    return out

def make_token(user_id: str, role: str) -> str:
    payload = {
        "sub":  user_id,
        "role": role,
        "exp":  datetime.now(timezone.utc) + timedelta(seconds=JWT_EXPIRES),
        "iat":  datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def write_log(action: str, collection: str, target_id: str, detail: dict = None):
    logs_col.insert_one({
        "admin_id":   ObjectId(g.user_id),
        "action":     action,
        "collection": collection,
        "target_id":  target_id,
        "detail":     detail or {},
        "created_at": now_iso(),
    })

def err(msg, code=400):
    return jsonify({"error": msg}), code

# ═══════════════════════════════════════════
# Auth decorators
# ═══════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return err("Token tidak ditemukan", 401)
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return err("Token expired", 401)
        except jwt.InvalidTokenError:
            return err("Token tidak valid", 401)
        g.user_id = payload["sub"]
        g.role    = payload["role"]
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if g.role != "admin":
            return err("Akses ditolak: hanya admin", 403)
        return f(*args, **kwargs)
    return wrapper

# ═══════════════════════════════════════════
# AUTH endpoints
# ═══════════════════════════════════════════

@app.route("/auth/register", methods=["POST"])
def register():
    d = request.get_json() or {}
    for f in ("name", "email", "password"):
        if not d.get(f):
            return err(f"Field '{f}' wajib diisi")

    if users_col.find_one({"email": d["email"]}):
        return err("Email sudah terdaftar", 409)

    pw_hash = bcrypt.hashpw(d["password"].encode(), bcrypt.gensalt()).decode()
    now = now_iso()
    doc = {
        "name":       d["name"],
        "email":      d["email"].lower().strip(),
        "password":   pw_hash,
        "role":       "user",
        "city":       d.get("city", ""),
        "phone":      d.get("phone", ""),
        "address":    d.get("address", ""),
        "is_active":  True,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }
    result = users_col.insert_one(doc)
    token  = make_token(str(result.inserted_id), "user")
    return jsonify({"message": "Registrasi berhasil", "token": token,
                    "user": {"id": str(result.inserted_id), "name": doc["name"],
                             "email": doc["email"], "role": "user"}}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    if not d.get("email") or not d.get("password"):
        return err("email dan password wajib diisi")

    user = users_col.find_one({"email": d["email"].lower().strip()})
    if not user or not bcrypt.checkpw(d["password"].encode(), user["password"].encode()):
        return err("Email atau password salah", 401)
    if not user.get("is_active", True):
        return err("Akun dinonaktifkan. Hubungi admin.", 403)

    users_col.update_one({"_id": user["_id"]}, {"$set": {"last_login": now_iso()}})
    token = make_token(str(user["_id"]), user["role"])
    return jsonify({
        "token": token,
        "user": {
            "id":    str(user["_id"]),
            "name":  user["name"],
            "email": user["email"],
            "role":  user["role"],
        }
    })


@app.route("/auth/me", methods=["GET"])
@login_required
def me():
    user = users_col.find_one({"_id": ObjectId(g.user_id)}, {"password": 0, "_id": 0})
    return jsonify(serialize(user))

# ═══════════════════════════════════════════
# PRODUCT endpoints (public read, admin write)
# ═══════════════════════════════════════════

@app.route("/products", methods=["GET"])
def list_products():
    query  = {"is_active": True}
    cat    = request.args.get("category")
    search = request.args.get("search")
    if cat:
        query["category"] = cat
    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    try:
        page  = max(1, int(request.args.get("page",  1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        page, limit = 1, 20

    sort_map = {"price_asc": ("price", ASCENDING), "price_desc": ("price", DESCENDING),
                "rating": ("rating", DESCENDING), "newest": ("created_at", DESCENDING)}
    sort_key, sort_dir = sort_map.get(request.args.get("sort", "newest"), ("created_at", DESCENDING))

    total = prods_col.count_documents(query)
    docs  = list(prods_col.find(query, {"_id": 1, "name": 1, "category": 1, "price": 1,
                                        "stock": 1, "rating": 1, "rating_count": 1, "image_url": 1})
                 .sort(sort_key, sort_dir).skip((page-1)*limit).limit(limit))
    return jsonify({"page": page, "limit": limit, "total": total,
                    "total_pages": -(-total // limit), "data": [serialize(d) for d in docs]})


@app.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
    try:
        doc = prods_col.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return err("product_id tidak valid")
    if not doc:
        return err("Produk tidak ditemukan", 404)
    return jsonify(serialize(doc))


@app.route("/products", methods=["POST"])
@admin_required
def create_product():
    d = request.get_json() or {}
    for f in ("name", "category", "price"):
        if not d.get(f):
            return err(f"Field '{f}' wajib diisi")
    now = now_iso()
    doc = {
        "name":         d["name"],
        "category":     d["category"],
        "price":        float(d["price"]),
        "stock":        int(d.get("stock", 0)),
        "rating":       0.0,
        "rating_count": 0,
        "description":  d.get("description", ""),
        "image_url":    d.get("image_url", ""),
        "is_active":    True,
        "created_at":   now,
        "updated_at":   now,
    }
    result = prods_col.insert_one(doc)
    write_log("create_product", "products", str(result.inserted_id), {"name": doc["name"]})
    doc["_id"] = result.inserted_id
    return jsonify(serialize(doc)), 201


@app.route("/products/<product_id>", methods=["PUT"])
@admin_required
def update_product(product_id):
    d = request.get_json() or {}
    allowed = {"name", "category", "price", "stock", "description", "image_url", "is_active"}
    updates = {k: v for k, v in d.items() if k in allowed}
    if not updates:
        return err("Tidak ada field yang diupdate")
    updates["updated_at"] = now_iso()
    try:
        result = prods_col.update_one({"_id": ObjectId(product_id)}, {"$set": updates})
    except Exception:
        return err("product_id tidak valid")
    if result.matched_count == 0:
        return err("Produk tidak ditemukan", 404)
    write_log("update_product", "products", product_id, updates)
    return jsonify({"message": "Produk diperbarui", "product_id": product_id})


@app.route("/products/<product_id>", methods=["DELETE"])
@admin_required
def delete_product(product_id):
    try:
        result = prods_col.update_one({"_id": ObjectId(product_id)},
                                      {"$set": {"is_active": False, "updated_at": now_iso()}})
    except Exception:
        return err("product_id tidak valid")
    if result.matched_count == 0:
        return err("Produk tidak ditemukan", 404)
    write_log("delete_product", "products", product_id)
    return jsonify({"message": "Produk dinonaktifkan"})

# ═══════════════════════════════════════════
# ORDER endpoints
# ═══════════════════════════════════════════

@app.route("/orders", methods=["POST"])
@login_required
def create_order():
    d = request.get_json() or {}
    if not d.get("items") or not isinstance(d["items"], list) or len(d["items"]) == 0:
        return err("Field 'items' wajib diisi dan tidak boleh kosong")

    user = users_col.find_one({"_id": ObjectId(g.user_id)}, {"password": 0})

    # Validasi & hitung item
    order_items = []
    subtotal    = 0
    for item in d["items"]:
        if not item.get("product_id") or not item.get("qty"):
            return err("Setiap item harus memiliki product_id dan qty")
        try:
            prod = prods_col.find_one({"_id": ObjectId(item["product_id"]), "is_active": True})
        except Exception:
            return err(f"product_id tidak valid: {item.get('product_id')}")
        if not prod:
            return err(f"Produk tidak ditemukan: {item.get('product_id')}", 404)
        qty = int(item["qty"])
        if qty < 1:
            return err("qty minimal 1")
        if prod["stock"] < qty:
            return err(f"Stok tidak cukup untuk produk: {prod['name']}")

        s = prod["price"] * qty
        order_items.append({
            "product_id":   prod["_id"],
            "product_name": prod["name"],
            "category":     prod["category"],
            "qty":          qty,
            "price":        prod["price"],
            "subtotal":     s,
        })
        subtotal += s

        # Kurangi stok
        prods_col.update_one({"_id": prod["_id"]}, {"$inc": {"stock": -qty}})

    shipping = int(d.get("shipping_cost", 0))
    total    = subtotal + shipping
    now      = now_iso()

    import uuid
    doc = {
        "order_id":        str(uuid.uuid4()),
        "user_id":         ObjectId(g.user_id),
        "customer_name":   user["name"],
        "customer_email":  user["email"],
        "customer_city":   user.get("city", ""),
        "customer_address":d.get("address", user.get("address", "")),
        "items":           order_items,
        "subtotal":        subtotal,
        "discount_pct":    0,
        "discount_amt":    0,
        "shipping_cost":   shipping,
        "total":           total,
        "status":          "pending",
        "payment_method":  d.get("payment_method", "transfer_bank"),
        "payment_status":  "unpaid",
        "notes":           d.get("notes", ""),
        "created_at":      now,
        "updated_at":      now,
    }
    result = orders_col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify(serialize(doc)), 201


@app.route("/orders", methods=["GET"])
@login_required
def list_orders():
    # User hanya lihat ordernya sendiri; admin lihat semua
    query = {} if g.role == "admin" else {"user_id": ObjectId(g.user_id)}

    status = request.args.get("status")
    city   = request.args.get("city")
    if status:
        query["status"] = status
    if city and g.role == "admin":
        query["customer_city"] = city

    try:
        page  = max(1, int(request.args.get("page",  1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        page, limit = 1, 20

    total  = orders_col.count_documents(query)
    docs   = list(orders_col.find(query, {"_id": 1, "order_id": 1, "customer_name": 1,
                                          "total": 1, "status": 1, "payment_method": 1,
                                          "created_at": 1, "items": 1})
                  .sort("created_at", DESCENDING).skip((page-1)*limit).limit(limit))
    return jsonify({"page": page, "limit": limit, "total": total,
                    "total_pages": -(-total // limit), "data": [serialize(d) for d in docs]})


@app.route("/orders/<order_id>", methods=["GET"])
@login_required
def get_order(order_id):
    query = {"order_id": order_id}
    if g.role != "admin":
        query["user_id"] = ObjectId(g.user_id)
    doc = orders_col.find_one(query)
    if not doc:
        return err("Order tidak ditemukan", 404)
    return jsonify(serialize(doc))


@app.route("/orders/<order_id>/status", methods=["PUT"])
@admin_required
def update_order_status(order_id):
    d = request.get_json() or {}
    valid = ["pending", "processing", "completed", "cancelled"]
    if d.get("status") not in valid:
        return err(f"Status tidak valid. Pilihan: {valid}")

    result = orders_col.update_one(
        {"order_id": order_id},
        {"$set": {"status": d["status"],
                  "payment_status": "paid" if d["status"] in ("processing","completed") else "unpaid",
                  "updated_at": now_iso()}}
    )
    if result.matched_count == 0:
        return err("Order tidak ditemukan", 404)

    write_log("update_order_status", "orders", order_id,
              {"new_status": d["status"], "note": d.get("note","")})
    return jsonify({"order_id": order_id, "status": d["status"]})

# ═══════════════════════════════════════════
# ADMIN — User management
# ═══════════════════════════════════════════

@app.route("/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    query  = {}
    role   = request.args.get("role")
    active = request.args.get("is_active")
    search = request.args.get("search")
    if role:
        query["role"] = role
    if active is not None:
        query["is_active"] = active.lower() == "true"
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                        {"email": {"$regex": search, "$options": "i"}}]
    try:
        page  = max(1, int(request.args.get("page",  1)))
        limit = min(100, max(1, int(request.args.get("limit", 20))))
    except ValueError:
        page, limit = 1, 20

    total = users_col.count_documents(query)
    docs  = list(users_col.find(query, {"password": 0})
                 .sort("created_at", DESCENDING).skip((page-1)*limit).limit(limit))
    return jsonify({"page": page, "limit": limit, "total": total,
                    "total_pages": -(-total // limit), "data": [serialize(d) for d in docs]})


@app.route("/admin/users/<user_id>/suspend", methods=["PUT"])
@admin_required
def suspend_user(user_id):
    d = request.get_json() or {}
    active = d.get("is_active")
    if active is None:
        return err("Field 'is_active' (true/false) wajib diisi")
    try:
        result = users_col.update_one({"_id": ObjectId(user_id)},
                                      {"$set": {"is_active": bool(active), "updated_at": now_iso()}})
    except Exception:
        return err("user_id tidak valid")
    if result.matched_count == 0:
        return err("User tidak ditemukan", 404)
    action = "activate_user" if active else "suspend_user"
    write_log(action, "users", user_id)
    msg = "User diaktifkan" if active else "User disuspend"
    return jsonify({"message": msg, "user_id": user_id, "is_active": bool(active)})


@app.route("/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    try:
        result = users_col.delete_one({"_id": ObjectId(user_id), "role": "user"})
    except Exception:
        return err("user_id tidak valid")
    if result.deleted_count == 0:
        return err("User tidak ditemukan atau tidak bisa dihapus", 404)
    write_log("delete_user", "users", user_id)
    return jsonify({"message": "User dihapus", "user_id": user_id})

# ═══════════════════════════════════════════
# ADMIN — Dashboard statistik
# ═══════════════════════════════════════════

@app.route("/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    # Revenue & order count by status
    status_pipeline = [
        {"$group": {
            "_id":           "$status",
            "count":         {"$sum": 1},
            "total_revenue": {"$sum": "$total"},
            "avg_order":     {"$avg": "$total"},
        }},
        {"$sort": {"count": -1}}
    ]

    # Top 10 produk terlaris (dari array items dalam orders)
    top_products_pipeline = [
        {"$unwind": "$items"},
        {"$group": {
            "_id":       "$items.product_name",
            "category":  {"$first": "$items.category"},
            "qty_sold":  {"$sum": "$items.qty"},
            "revenue":   {"$sum": "$items.subtotal"},
        }},
        {"$sort": {"qty_sold": -1}},
        {"$limit": 10}
    ]

    # Revenue per bulan (12 bulan terakhir)
    monthly_pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id": {
                "year":  {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
            },
            "revenue": {"$sum": "$total"},
            "count":   {"$sum": 1},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$limit": 12}
    ]

    # Revenue per kota
    city_pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {
            "_id":    "$customer_city",
            "revenue":{"$sum": "$total"},
            "count":  {"$sum": 1},
        }},
        {"$sort": {"revenue": -1}},
        {"$limit": 10}
    ]

    by_status    = list(orders_col.aggregate(status_pipeline))
    top_products = list(orders_col.aggregate(top_products_pipeline))
    monthly      = list(orders_col.aggregate(monthly_pipeline))
    by_city      = list(orders_col.aggregate(city_pipeline))

    total_users  = users_col.count_documents({"role": "user"})
    active_users = users_col.count_documents({"role": "user", "is_active": True})
    total_prods  = prods_col.count_documents({"is_active": True})
    total_orders = orders_col.count_documents({})

    total_rev  = sum(s.get("total_revenue", 0) for s in by_status if s["_id"] == "completed")

    return jsonify({
        "summary": {
            "total_orders":  total_orders,
            "total_revenue": total_rev,
            "total_users":   total_users,
            "active_users":  active_users,
            "total_products":total_prods,
        },
        "by_status":    [serialize(s) for s in by_status],
        "top_products": [serialize(p) for p in top_products],
        "monthly":      [serialize(m) for m in monthly],
        "by_city":      [serialize(c) for c in by_city],
    })


@app.route("/admin/logs", methods=["GET"])
@admin_required
def admin_logs():
    try:
        page  = max(1, int(request.args.get("page",  1)))
        limit = min(100, max(1, int(request.args.get("limit", 30))))
    except ValueError:
        page, limit = 1, 30

    total = logs_col.count_documents({})
    docs  = list(logs_col.find({}).sort("created_at", DESCENDING)
                 .skip((page-1)*limit).limit(limit))
    return jsonify({"page": page, "limit": limit, "total": total,
                    "total_pages": -(-total // limit), "data": [serialize(d) for d in docs]})


# ═══════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": now_iso().isoformat()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
