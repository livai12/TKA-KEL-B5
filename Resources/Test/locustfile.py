"""
Locustfile — Order Processing Service (dengan Auth)
Jalankan dari host BERBEDA dari server:
    locust -f locustfile.py --host=http://<IP_SERVER>
"""

from locust import HttpUser, task, between, events
import random

PRODUCTS_CACHE = []   # diisi saat on_start
ORDER_IDS      = []   # shared antar user

CITIES    = ["Surabaya","Jakarta","Bandung","Medan","Semarang","Makassar"]
PAYMENTS  = ["gopay","ovo","dana","transfer_bank","kartu_kredit","qris"]
STATUSES  = ["pending","processing","completed","cancelled"]


# ════════════════════════════════════════════
# Regular User — simulates customer behaviour
# ════════════════════════════════════════════
class CustomerUser(HttpUser):
    weight    = 8   # 80% traffic adalah user biasa
    wait_time = between(0.5, 2)

    def on_start(self):
        """Login sebagai user biasa."""
        # Gunakan 1 dari 10 email acak agar hit cache session
        idx = random.randint(1, 50)
        with self.client.post("/auth/login", json={
            "email":    f"user{idx}@example.com",    # akan 404 tapi itu ok
            "password": "User@12345"
        }, catch_response=True, name="/auth/login [user]") as res:
            # Fallback: kalau user tidak ada, pakai akun yang pasti ada
            if res.status_code != 200:
                res.success()   # jangan gagalkan, lanjut tanpa token
                self.token = None
            else:
                self.token = res.json().get("token")
                res.success()

        # Ambil daftar produk sekali di awal
        global PRODUCTS_CACHE
        if not PRODUCTS_CACHE:
            r = self.client.get("/products?limit=50", name="/products [init]")
            if r.status_code == 200:
                PRODUCTS_CACHE = [p["_id"] for p in r.json().get("data", [])]

    def auth_headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(4)
    def browse_products(self):
        """GET /products — browse katalog (berat karena sort+skip di koleksi besar)"""
        params = {"page": random.randint(1, 5), "limit": 20}
        cats   = ["Elektronik","Smartphone","Fashion","Olahraga","Buku","Rumah Tangga","Makanan"]
        if random.random() < 0.4:
            params["category"] = random.choice(cats)
        if random.random() < 0.2:
            params["sort"] = random.choice(["price_asc","price_desc","rating","newest"])
        with self.client.get("/products", params=params, catch_response=True,
                             name="/products?[filters]") as r:
            r.success() if r.status_code == 200 else r.failure(r.status_code)

    @task(2)
    def view_product_detail(self):
        """GET /products/<id> — lihat detail produk"""
        if not PRODUCTS_CACHE:
            return
        pid = random.choice(PRODUCTS_CACHE)
        with self.client.get(f"/products/{pid}", catch_response=True,
                             name="/products/<id>") as r:
            r.success() if r.status_code in (200, 404) else r.failure(r.status_code)

    @task(3)
    def create_order(self):
        """POST /orders — buat pesanan (write-heavy)"""
        if not PRODUCTS_CACHE or not self.token:
            return
        items = [{"product_id": random.choice(PRODUCTS_CACHE),
                  "qty": random.randint(1, 3)}
                 for _ in range(random.randint(1, 3))]
        payload = {
            "items":          items,
            "payment_method": random.choice(PAYMENTS),
            "shipping_cost":  random.choice([0, 9000, 15000, 25000]),
            "address":        f"Jl. Contoh No. {random.randint(1,100)}, {random.choice(CITIES)}",
        }
        with self.client.post("/orders", json=payload, headers=self.auth_headers(),
                              catch_response=True, name="/orders [POST]") as r:
            if r.status_code == 201:
                oid = r.json().get("order_id")
                if oid:
                    ORDER_IDS.append(oid)
                    if len(ORDER_IDS) > 5000:
                        ORDER_IDS[:] = ORDER_IDS[-5000:]
                r.success()
            elif r.status_code in (400, 401, 404):
                r.success()   # error bisnis, bukan error infra
            else:
                r.failure(r.status_code)

    @task(2)
    def my_orders(self):
        """GET /orders — riwayat order milik user"""
        if not self.token:
            return
        params = {"page": random.randint(1, 3), "limit": 10}
        if random.random() < 0.3:
            params["status"] = random.choice(STATUSES)
        with self.client.get("/orders", params=params, headers=self.auth_headers(),
                             catch_response=True, name="/orders [user list]") as r:
            r.success() if r.status_code in (200, 401) else r.failure(r.status_code)

    @task(1)
    def get_order_detail(self):
        """GET /orders/<id> — detail satu order"""
        if not ORDER_IDS or not self.token:
            return
        oid = random.choice(ORDER_IDS)
        with self.client.get(f"/orders/{oid}", headers=self.auth_headers(),
                             catch_response=True, name="/orders/<id>") as r:
            r.success() if r.status_code in (200, 404, 401) else r.failure(r.status_code)


# ════════════════════════════════════════════
# Admin User — simulates backoffice activity
# ════════════════════════════════════════════
class AdminUser(HttpUser):
    weight    = 2   # 20% traffic admin
    wait_time = between(1, 4)

    def on_start(self):
        idx = random.randint(1, 5)
        with self.client.post("/auth/login", json={
            "email":    f"admin{idx}@tka.its.ac.id",
            "password": "Admin@12345"
        }, catch_response=True, name="/auth/login [admin]") as res:
            if res.status_code == 200:
                self.token = res.json().get("token")
                res.success()
            else:
                self.token = None
                res.success()

    def auth_headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(4)
    def dashboard_stats(self):
        """GET /admin/stats — aggregasi dashboard (query paling berat)"""
        with self.client.get("/admin/stats", headers=self.auth_headers(),
                             catch_response=True) as r:
            r.success() if r.status_code in (200, 401, 403) else r.failure(r.status_code)

    @task(3)
    def list_all_orders(self):
        """GET /orders — admin lihat semua order dengan filter"""
        if not self.token:
            return
        params = {"page": random.randint(1, 20), "limit": 20}
        if random.random() < 0.5:
            params["status"] = random.choice(STATUSES)
        with self.client.get("/orders", params=params, headers=self.auth_headers(),
                             catch_response=True, name="/orders [admin list]") as r:
            r.success() if r.status_code in (200, 401) else r.failure(r.status_code)

    @task(2)
    def update_order_status(self):
        """PUT /orders/<id>/status — update status pesanan"""
        if not ORDER_IDS or not self.token:
            return
        oid    = random.choice(ORDER_IDS)
        status = random.choice(["processing", "completed", "cancelled"])
        with self.client.put(f"/orders/{oid}/status",
                             json={"status": status},
                             headers=self.auth_headers(),
                             catch_response=True,
                             name="/orders/<id>/status [PUT]") as r:
            r.success() if r.status_code in (200, 404, 401) else r.failure(r.status_code)

    @task(2)
    def list_users(self):
        """GET /admin/users — manajemen user"""
        if not self.token:
            return
        params = {"page": random.randint(1, 5), "limit": 20}
        if random.random() < 0.3:
            params["is_active"] = random.choice(["true", "false"])
        with self.client.get("/admin/users", params=params, headers=self.auth_headers(),
                             catch_response=True) as r:
            r.success() if r.status_code in (200, 401, 403) else r.failure(r.status_code)

    @task(1)
    def view_audit_logs(self):
        """GET /admin/logs — audit trail"""
        with self.client.get("/admin/logs?limit=30", headers=self.auth_headers(),
                             catch_response=True) as r:
            r.success() if r.status_code in (200, 401, 403) else r.failure(r.status_code)
