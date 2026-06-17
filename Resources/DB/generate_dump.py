#!/usr/bin/env python3
"""
Generate data realistis dan export ke format mongodump (BSON).
Output: dump/orderdb/{collection}.bson + {collection}.metadata.json

Restore ke MongoDB:
    mongorestore --drop dump/
    # atau ke remote:
    mongorestore --uri="mongodb://IP:27017" --drop dump/
"""

import os, json, struct, random, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import bcrypt
from bson import encode as bson_encode
from bson import ObjectId
from faker import Faker
from tqdm import tqdm

fake = Faker("id_ID")
random.seed(42)

OUT_DIR = Path("dump/orderdb")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════

def ts(days_ago_max=365, days_ago_min=0):
    d = random.randint(int(days_ago_min*86400), int(days_ago_max*86400))
    return datetime.now(timezone.utc) - timedelta(seconds=d)

def write_bson(name: str, docs: list):
    path = OUT_DIR / f"{name}.bson"
    with open(path, "wb") as f:
        for doc in docs:
            data = bson_encode(doc)
            f.write(data)

    meta = {
        "options": {},
        "indexes": [{"v": 2, "key": {"_id": 1}, "name": "_id_"}],
        "uuid":    str(uuid.uuid4()).replace("-","").upper(),
        "collectionName": name,
        "type": "collection"
    }
    with open(OUT_DIR / f"{name}.metadata.json", "w") as f:
        json.dump(meta, f)

    print(f"  ✅ {name:20s} → {len(docs):>6,} dokumen  ({path.stat().st_size/1024:.1f} KB)")

# ═══════════════════════════════════════════════════════
# 1. PRODUCTS (~100 produk)
# ═══════════════════════════════════════════════════════
PRODUCT_CATALOG = [
    # Elektronik
    ("Laptop ASUS VivoBook 15 OLED",        7_500_000, "Elektronik", 4.3, 120),
    ("Laptop Gaming MSI Katana GF66",       14_000_000, "Elektronik", 4.5,  45),
    ("MacBook Air M2 13 inch 256GB",        18_500_000, "Elektronik", 4.8,  30),
    ("MacBook Pro M3 14 inch 512GB",        29_999_000, "Elektronik", 4.9,  18),
    ("Headphone Sony WH-1000XM5",           3_800_000, "Elektronik", 4.7,  85),
    ("TWS Samsung Galaxy Buds2 Pro",        1_800_000, "Elektronik", 4.4, 200),
    ("Monitor LG 27UK850 4K IPS 27in",      5_500_000, "Elektronik", 4.6,  55),
    ("Monitor Gaming ASUS TUF 144Hz 24in",  2_800_000, "Elektronik", 4.5,  70),
    ("Keyboard Mechanical Keychron K6 RGB", 1_150_000, "Elektronik", 4.6, 150),
    ("Mouse Logitech MX Master 3S",         1_350_000, "Elektronik", 4.8, 180),
    ("Mouse Gaming Razer DeathAdder V3",      950_000, "Elektronik", 4.5, 210),
    ("SSD Samsung 970 EVO Plus 1TB NVMe",   1_600_000, "Elektronik", 4.7,  95),
    ("SSD External WD My Passport 2TB",       850_000, "Elektronik", 4.4, 130),
    ("RAM Corsair Vengeance 16GB DDR4",       750_000, "Elektronik", 4.5, 160),
    ("Webcam Logitech C920 HD Pro 1080p",   1_050_000, "Elektronik", 4.6,  90),
    ("Microphone Blue Yeti USB Cardioid",   2_100_000, "Elektronik", 4.7,  60),
    ("Printer Canon PIXMA G3020 Infus",     1_750_000, "Elektronik", 4.3,  75),
    ("Router WiFi 6 TP-Link Archer AX73",     950_000, "Elektronik", 4.5, 110),
    ("UPS APC Back-UPS 650VA 230V",         1_200_000, "Elektronik", 4.4,  80),
    ("Raspberry Pi 4 Model B 8GB RAM",      1_450_000, "Elektronik", 4.6,  40),
    # Smartphone
    ("Samsung Galaxy S24 Ultra 256GB",      19_999_000, "Smartphone", 4.8,  25),
    ("Samsung Galaxy S24 128GB",            12_000_000, "Smartphone", 4.7,  50),
    ("iPhone 15 Pro 256GB Natural Titanium",20_999_000, "Smartphone", 4.9,  20),
    ("iPhone 15 128GB Black",               14_999_000, "Smartphone", 4.8,  35),
    ("Xiaomi 14 Pro 512GB",                 10_500_000, "Smartphone", 4.6,  60),
    ("OPPO Find X7 256GB",                   9_800_000, "Smartphone", 4.5,  45),
    ("Realme GT 6 256GB",                    6_200_000, "Smartphone", 4.4,  80),
    ("Vivo V30 Pro 256GB",                   6_800_000, "Smartphone", 4.3,  90),
    ("Casing Spigen iPhone 15 Ultra Hybrid",   250_000, "Smartphone", 4.5, 500),
    ("Charger GaN 65W Baseus 3-Port",          320_000, "Smartphone", 4.6, 400),
    ("Power Bank Anker 737 24000mAh",          850_000, "Smartphone", 4.7, 250),
    ("Kabel Data USB-C 2m Ugreen 100W",         95_000, "Smartphone", 4.5, 800),
    ("Tempered Glass Samsung S24 Ultra",        65_000, "Smartphone", 4.3, 600),
    ("Ring Light LED 10in + Tripod",           280_000, "Smartphone", 4.4, 300),
    # Rumah Tangga
    ("Rice Cooker Philips HD3132 2L",          650_000, "Rumah Tangga", 4.4, 200),
    ("Blender Oxone OX-855 Professional",      380_000, "Rumah Tangga", 4.2, 180),
    ("Air Purifier Xiaomi Smart Air Purifier 4 Pro", 1_800_000, "Rumah Tangga", 4.6, 90),
    ("Vacuum Cleaner Dyson V12 Detect Slim",  8_500_000, "Rumah Tangga", 4.8, 25),
    ("Dispenser Galon Bawah Miyako WD-389",     450_000, "Rumah Tangga", 4.3, 150),
    ("Setrika Philips Azur 2600W Steam",        450_000, "Rumah Tangga", 4.4, 120),
    ("Kipas Angin Tower Panasonic F-40TMH",     750_000, "Rumah Tangga", 4.3, 100),
    ("Smart Plug TP-Link Tapo P110 WiFi",       180_000, "Rumah Tangga", 4.5, 300),
    ("Lampu LED Philips 10W E27 Daylight",       45_000, "Rumah Tangga", 4.4, 1000),
    ("Teko Listrik Miyako 1.8L Stainless",      180_000, "Rumah Tangga", 4.2, 250),
    # Fashion
    ("Sepatu Sneakers Nike Air Max 270",       1_950_000, "Fashion", 4.6, 80),
    ("Sepatu Running Adidas Ultraboost 22",    2_200_000, "Fashion", 4.7, 65),
    ("Sepatu Slip-On Vans Old Skool Classic",    850_000, "Fashion", 4.5, 120),
    ("Tas Ransel Laptop Thule Accent 28L",     1_800_000, "Fashion", 4.7, 45),
    ("Tas Selempang Fossil Buckner Sling",       950_000, "Fashion", 4.4, 80),
    ("Kemeja Flanel Uniqlo Slim Fit",            399_000, "Fashion", 4.5, 200),
    ("Celana Chino Erigo Slim 32 Navy",          189_000, "Fashion", 4.3, 350),
    ("Jaket Bomber H&M Oversized Black",         599_000, "Fashion", 4.4, 150),
    ("Topi Baseball New Era 59FIFTY MLB",        450_000, "Fashion", 4.5, 100),
    ("Kacamata Rayban New Wayfarer Classic",   1_650_000, "Fashion", 4.6, 60),
    ("Jam Tangan Casio G-Shock DW5600BB",      1_250_000, "Fashion", 4.7, 75),
    ("Dompet Kulit Fossil Derrick Bifold",       750_000, "Fashion", 4.5, 90),
    ("Ikat Pinggang Kulit Genuine Barada",       195_000, "Fashion", 4.3, 180),
    ("Kaos Polos Cotton Combed 30s Putih",        89_000, "Fashion", 4.4, 500),
    # Olahraga
    ("Sepeda Lipat Polygon Urbano 3 2024",     4_500_000, "Olahraga", 4.6, 20),
    ("Treadmill Electric Welcare WC2053",       7_800_000, "Olahraga", 4.4, 12),
    ("Dumbbell Set Adjustable 5-25kg",          1_200_000, "Olahraga", 4.5, 35),
    ("Barbell Set Olympic 100kg",               3_500_000, "Olahraga", 4.6, 15),
    ("Matras Yoga NBR 10mm Anti-Slip",            250_000, "Olahraga", 4.4, 200),
    ("Raket Badminton Yonex Astrox 88D Pro",    1_850_000, "Olahraga", 4.7, 40),
    ("Sepatu Lari New Balance Fresh Foam 880",  1_950_000, "Olahraga", 4.6, 55),
    ("Smartwatch Garmin Forerunner 255",        5_200_000, "Olahraga", 4.8, 30),
    ("Whey Protein ON Gold Standard 2.27kg",      680_000, "Olahraga", 4.7, 150),
    ("Bola Futsal Mikasa FL450B FIFA Quality",    350_000, "Olahraga", 4.5, 80),
    ("Skipping Rope Speed Cable Premium",         180_000, "Olahraga", 4.4, 200),
    ("Helm Sepeda Giro Syntax MIPS",            1_250_000, "Olahraga", 4.6, 45),
    ("Gloves Gym Harbinger Pro WristWrap",        380_000, "Olahraga", 4.5, 100),
    # Buku & Pendidikan
    ("Clean Code - Robert C. Martin",            185_000, "Buku", 4.9, 80),
    ("Designing Data-Intensive Applications",     320_000, "Buku", 4.8, 60),
    ("The Pragmatic Programmer 20th Ed",          290_000, "Buku", 4.8, 70),
    ("System Design Interview Vol 2",             250_000, "Buku", 4.7, 90),
    ("Kubernetes in Action 2nd Edition",          350_000, "Buku", 4.7, 50),
    ("Docker Deep Dive - Nigel Poulton",          180_000, "Buku", 4.6, 75),
    ("Computer Networking Top-Down Approach",     420_000, "Buku", 4.5, 45),
    ("Introduction to Algorithms 4th Ed",         580_000, "Buku", 4.6, 40),
    ("The Phoenix Project",                       210_000, "Buku", 4.8, 85),
    ("Site Reliability Engineering (Google)",     380_000, "Buku", 4.7, 55),
    ("Buku Tulis Sidu 58 Lembar (isi 10)",         35_000, "Buku", 4.2, 500),
    ("Pulpen Pilot G2 0.5mm Hitam (12pcs)",        78_000, "Buku", 4.5, 400),
    ("Stabilo Boss Highlighter 4 Warna",            45_000, "Buku", 4.4, 600),
    ("Sticky Note Post-it 3x3 Assorted 12 Pad",   120_000, "Buku", 4.5, 300),
    ("Papan Tulis Whiteboard Deli 60x90cm",       280_000, "Buku", 4.3, 100),
    # Makanan & Minuman
    ("Kopi Arabica Flores Bajawa 250g",            85_000, "Makanan", 4.7, 300),
    ("Green Tea Matcha Premium Kyoto 100g",        120_000, "Makanan", 4.6, 250),
    ("Madu Hutan Murni Trigona 250ml",             145_000, "Makanan", 4.8, 200),
    ("Granola Oat Banana Walnut 500g",              95_000, "Makanan", 4.5, 350),
    ("Cokelat Dark 70% Cacao Lindt 100g",           55_000, "Makanan", 4.6, 400),
    ("Kurma Medjool Premium Saudi 500g",           180_000, "Makanan", 4.7, 280),
    ("Susu Almond Unsweetened 1L Oatside",          38_000, "Makanan", 4.4, 500),
    ("Keripik Tempe Original Renyah 200g",          32_000, "Makanan", 4.3, 600),
    ("Teh Herbal Celup Camomile Lipton 25s",        28_000, "Makanan", 4.4, 700),
    ("Selai Kacang Skippy Creamy 462g",             58_000, "Makanan", 4.5, 450),
]

CITIES   = ["Surabaya","Jakarta","Bandung","Medan","Semarang","Makassar",
            "Palembang","Denpasar","Yogyakarta","Malang","Tangerang","Depok",
            "Bekasi","Bogor","Solo","Balikpapan","Samarinda","Pontianak"]
STATUSES = ["pending","processing","completed","cancelled"]
ST_W     = [8, 15, 68, 9]
PAYMENTS = ["transfer_bank","kartu_kredit","gopay","ovo","dana","qris","cod"]
PAY_W    = [20, 12, 22, 18, 12, 12, 4]

print("\n📦 Generating data ...\n")

# ── products ──────────────────────────────────
product_docs = []
product_ids  = []
for name, price, cat, rating, stock in PRODUCT_CATALOG:
    oid = ObjectId()
    product_ids.append(oid)
    created = ts(500, 180)
    product_docs.append({
        "_id":          oid,
        "name":         name,
        "category":     cat,
        "price":        price,
        "stock":        stock,
        "rating":       rating,
        "rating_count": random.randint(10, 500),
        "description":  fake.paragraph(nb_sentences=3),
        "image_url":    f"https://placehold.co/400x400?text={name[:20].replace(' ','+')}",
        "is_active":    random.random() > 0.05,
        "created_at":   created,
        "updated_at":   created,
    })

write_bson("products", product_docs)

# ── users (500 user + 5 admin) ────────────────
user_docs = []
user_ids  = []

# Admin accounts (password: Admin@12345)
for i in range(1, 6):
    oid = ObjectId()
    user_ids.append(oid)
    pw  = bcrypt.hashpw(b"Admin@12345", bcrypt.gensalt()).decode()
    created = ts(400, 300)
    user_docs.append({
        "_id":        oid,
        "name":       f"Admin TKA {i}",
        "email":      f"admin{i}@tka.its.ac.id",
        "password":   pw,
        "role":       "admin",
        "city":       random.choice(CITIES),
        "phone":      fake.phone_number(),
        "is_active":  True,
        "created_at": created,
        "updated_at": created,
        "last_login": ts(30, 0),
    })

# Regular users (password: User@12345)
for _ in tqdm(range(500), desc="  users    "):
    oid = ObjectId()
    user_ids.append(oid)
    pw  = bcrypt.hashpw(b"User@12345", bcrypt.gensalt()).decode()
    created = ts(365, 0)
    user_docs.append({
        "_id":        oid,
        "name":       fake.name(),
        "email":      fake.unique.email(),
        "password":   pw,
        "role":       "user",
        "city":       random.choice(CITIES),
        "phone":      fake.phone_number(),
        "address":    fake.address().replace("\n", ", "),
        "is_active":  random.random() > 0.04,
        "created_at": created,
        "updated_at": created,
        "last_login": ts(60, 0) if random.random() > 0.2 else None,
    })

write_bson("users", user_docs)
regular_user_ids = [u["_id"] for u in user_docs if u["role"] == "user"]

# ── orders (10.000) ───────────────────────────
order_docs = []
order_ids  = []

for _ in tqdm(range(10_000), desc="  orders   "):
    oid      = ObjectId()
    order_ids.append(oid)
    uid      = random.choice(regular_user_ids)
    user     = next(u for u in user_docs if u["_id"] == uid)

    # 1–4 item per order
    n_items  = random.choices([1,2,3,4], weights=[55,28,12,5])[0]
    chosen   = random.sample(product_docs, n_items)
    items    = []
    subtotal = 0
    for p in chosen:
        qty   = random.choices([1,2,3,5], weights=[60,25,10,5])[0]
        price = p["price"] * random.uniform(0.9, 1.0)
        price = round(price / 500) * 500
        items.append({
            "product_id":   p["_id"],
            "product_name": p["name"],
            "category":     p["category"],
            "qty":          qty,
            "price":        price,
            "subtotal":     qty * price,
        })
        subtotal += qty * price

    discount     = random.choice([0, 0, 0, 0, 5, 10, 15, 20]) / 100
    discount_amt = round(subtotal * discount / 500) * 500
    shipping     = random.choice([0, 9_000, 15_000, 25_000, 35_000])
    total        = subtotal - discount_amt + shipping

    status   = random.choices(STATUSES, weights=ST_W)[0]
    created  = ts(365, 0)
    updated  = created + timedelta(hours=random.randint(1, 96)) if status != "pending" else created
    if updated > datetime.now(timezone.utc):
        updated = datetime.now(timezone.utc)

    order_docs.append({
        "_id":             oid,
        "order_id":        str(uuid.uuid4()),
        "user_id":         uid,
        "customer_name":   user["name"],
        "customer_email":  user["email"],
        "customer_city":   user.get("city",""),
        "customer_address":user.get("address", fake.address().replace("\n",", ")),
        "items":           items,
        "subtotal":        subtotal,
        "discount_pct":    int(discount * 100),
        "discount_amt":    discount_amt,
        "shipping_cost":   shipping,
        "total":           total,
        "status":          status,
        "payment_method":  random.choices(PAYMENTS, weights=PAY_W)[0],
        "payment_status":  "paid" if status in ("processing","completed") else "unpaid",
        "notes":           fake.sentence() if random.random() < 0.25 else "",
        "created_at":      created,
        "updated_at":      updated,
    })

write_bson("orders", order_docs)

# ── audit_logs ────────────────────────────────
admin_ids  = [u["_id"] for u in user_docs if u["role"] == "admin"]
LOG_ACTIONS = [
    ("update_order_status", "orders"),
    ("suspend_user",        "users"),
    ("activate_user",       "users"),
    ("update_product",      "products"),
    ("delete_product",      "products"),
    ("create_product",      "products"),
]

log_docs = []
for _ in range(2_000):
    action, col = random.choice(LOG_ACTIONS)
    log_docs.append({
        "_id":        ObjectId(),
        "admin_id":   random.choice(admin_ids),
        "action":     action,
        "collection": col,
        "target_id":  str(random.choice(order_ids if col == "orders"
                          else (user_ids if col == "users" else product_ids))),
        "detail":     {"note": fake.sentence(nb_words=6)},
        "created_at": ts(180, 0),
    })

write_bson("audit_logs", log_docs)

# ── sessions (minimal, untuk referensi) ───────
session_docs = []
for uid in random.sample(regular_user_ids, 100):
    session_docs.append({
        "_id":        ObjectId(),
        "user_id":    uid,
        "token_hash": uuid.uuid4().hex,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": ts(7, 0),
    })

write_bson("sessions", session_docs)

print(f"\n🎉 Dump selesai → folder: dump/orderdb/")
print(f"\n📋 Akun default:")
print(f"   Admin  → admin1@tka.its.ac.id  / Admin@12345")
print(f"   User   → (lihat collection users) / User@12345")
print(f"\n🔄 Cara restore:")
print(f"   mongorestore --drop dump/")
print(f"   mongorestore --uri='mongodb://IP:27017' --drop dump/")
