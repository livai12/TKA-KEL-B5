# Final Project Teknologi Komputasi Awan - Kelompok B-05

## Anggota Kelompok

| No | Nama | NRP |
|:---:|---|---|
| 1 | Nabilah Anindya Paramesti | 5027241006 |
| 2 | Mochkamad Maulana Syafaat | 5027241021 |
| 3 | Zein Muhammad Hasan | 5027241035 |
| 4 | Khumaidi Kharis Az-zacky | 5027241049 |
| 5 | Dimas Muhammad Putra | 5027241076 |
| 6 | Jofanka Al-kautsar Pangestu Abady | 5027241107 |
| 7 | Naufal Ardhana | 5027241118 |

---

## 1. Introduction

Proyek ini merupakan Final Project mata kuliah Teknologi Komputasi Awan yang bertujuan untuk merancang, mengimplementasikan, dan mengoptimalkan **Order Processing Service** -- sebuah layanan backend berbasis REST API untuk platform e-commerce. Layanan ini menangani pembuatan pesanan, pengecekan status, dan riwayat transaksi.

Tantangan utama yang dihadapi adalah men-deploy layanan ini pada infrastruktur cloud dengan **budget maksimal 75 US$/bulan** sambil memaksimalkan kemampuan sistem dalam menangani traffic tinggi (diukur melalui RPS - Request Per Second).

Teknologi yang digunakan:
- **Backend**: Python Flask + Gunicorn (gevent worker)
- **Database**: MongoDB
- **Load Balancer**: Nginx (least_conn)
- **Load Testing**: Locust
- **Deployment**: Local Virtual Machine (VirtualBox/Vagrant)

---

## 2. Arsitektur Cloud

### 2.1 Diagram Arsitektur

<!-- Ganti path berikut dengan gambar diagram dari draw.io -->
![Diagram Arsitektur](result/arsitektur/arsitektur.png)

### 2.2 Tabel Spesifikasi dan Harga

| No | VM | Peran | Tipe | CPU | RAM | Harga/bulan | Host |
|----|------|-------|------|-----|-----|-------------|------|
| 1 | VM1 | Load Balancer (Nginx) + Frontend | vm1 | 1 vCPU | 512 MB | $4 | Komputer A |
| 2 | VM2 | App Server 1 (Flask + Gunicorn) | vm3 | 1 vCPU | 2 GB | $12 | Komputer A |
| 3 | VM3 | App Server 2 (Flask + Gunicorn) | vm3 | 1 vCPU | 2 GB | $12 | Komputer B |
| 4 | VM4 | App Server 3 (Flask + Gunicorn) | vm3 | 1 vCPU | 2 GB | $12 | Komputer B |
| 5 | VM5 | Database Server (MongoDB) | vm5 | 2 vCPU | 4 GB | $24 | Komputer A |
| | | | **TOTAL** | | | **$64** | |

Budget terpakai: $64 dari $75 (sisa $11).

### 2.3 Justifikasi Arsitektur

**Pemisahan Database dari App Server**
MongoDB ditempatkan di VM terpisah dengan spesifikasi tertinggi (vm5, 2vCPU, 4GB) karena database merupakan bottleneck utama pada operasi I/O. Dengan RAM 4GB, WiredTiger cache engine MongoDB mendapat alokasi ~2GB yang cukup untuk menampung working set dari 10.000+ orders.

**3 App Server dengan Horizontal Scaling**
Menggunakan 3 instance app server (vm3, 2GB masing-masing) dibanding 1 instance besar karena:
- Horizontal scaling memberikan fault tolerance (jika 1 VM mati, 2 lainnya tetap melayani)
- Setiap VM menjalankan 3 Gunicorn workers dengan gevent (async I/O) sehingga total ada 9 workers
- Beban request terdistribusi merata melalui load balancer

**Nginx sebagai Load Balancer**
Nginx dipilih karena ringan (hanya butuh 512MB) dan mendukung berbagai strategi distribusi traffic. Menggunakan `least_conn` agar request diarahkan ke server dengan koneksi aktif paling sedikit, optimal untuk workload dengan response time bervariasi.

**Gunicorn dengan Gevent Worker**
Dibandingkan sync worker standar, gevent worker memungkinkan setiap worker menangani ratusan request secara concurrent melalui coroutine. Ini sangat efektif untuk I/O-bound workload (menunggu response MongoDB).

---

## 3. Implementasi

### 3.1 Setup MongoDB (VM5)

<!-- Screenshot terminal saat instalasi dan konfigurasi MongoDB -->
<!-- ![Setup MongoDB](result/setup/setup_mongodb.png) -->

Langkah-langkah:

1. **Install MongoDB 7.0** pada Ubuntu 22.04
2. **Konfigurasi** `bindIp: 0.0.0.0` agar dapat diakses dari app server
3. **Restore data awal** menggunakan `mongorestore --drop dump/`
4. **Buat index** untuk optimasi query:
   - `orders.order_id` - lookup by order ID
   - `orders.user_id + created_at` - list orders per user
   - `orders.status` - filter by status
   - `orders.created_at` - sort by date
   - `products.category + is_active` - filter produk
   - `users.email` (unique) - login lookup

```bash
# Contoh pembuatan index
mongosh orderdb --eval '
  db.orders.createIndex({order_id: 1});
  db.orders.createIndex({user_id: 1, created_at: -1});
  db.orders.createIndex({status: 1});
  db.orders.createIndex({created_at: -1});
  db.products.createIndex({category: 1, is_active: 1});
  db.users.createIndex({email: 1}, {unique: true});
'
```

### 3.2 Deploy Backend - App Server (VM2, VM3, VM4)

<!-- Screenshot terminal saat deploy backend -->
<!-- ![Setup App Server](result/setup/setup_appserver.png) -->

Langkah-langkah (diulang di setiap app server):

1. **Install Python 3, pip, virtualenv**
2. **Copy source code** `app.py` dan `requirements.txt`
3. **Install dependencies** + `gevent` untuk async worker
4. **Konfigurasi environment variables**:
   - `MONGO_URI=mongodb://<IP_VM5>:27017/`
   - `JWT_SECRET=<secret-key>`
5. **Buat systemd service** untuk Gunicorn:
   ```
   gunicorn -w 3 -k gevent -b 0.0.0.0:5000 app:app --timeout 120
   ```
6. **Verifikasi** dengan `curl http://localhost:5000/health`

### 3.3 Setup Nginx Load Balancer (VM1)

<!-- Screenshot konfigurasi Nginx -->
<!-- ![Setup Nginx](result/setup/setup_nginx.png) -->

Konfigurasi utama:
```nginx
upstream flask_backend {
    least_conn;
    server <IP_VM2>:5000;
    server <IP_VM3>:5000;
    server <IP_VM4>:5000;
    keepalive 64;
}
```

Frontend (static files) di-serve langsung oleh Nginx dari `/var/www/frontend/`.
Semua request API (`/auth/`, `/products`, `/orders`, `/admin/`, `/health`) di-proxy ke upstream backend.

### 3.4 Deploy Frontend (VM1)

<!-- Screenshot frontend yang berjalan -->
<!-- ![Frontend](result/frontend/frontend.png) -->

Frontend berupa file HTML + CSS statis yang sudah disesuaikan dengan backend API:
- Halaman login/registrasi dengan JWT authentication
- Katalog produk dengan filter dan sorting
- Pembuatan pesanan dengan sistem keranjang
- Daftar dan detail pesanan
- Admin panel (statistik, update status, manajemen user)

---

## 4. Hasil Pengujian Endpoint

Pengujian dilakukan menggunakan Postman terhadap semua endpoint yang tersedia. Berikut adalah daftar seluruh endpoint REST API yang telah dikonfigurasi:

<p align="center">
  <img src="result/postman/postman_list_endpoints.png" width="400" alt="Daftar Seluruh Endpoint Postman"><br>
  <em>Gambar 4.0: Daftar Seluruh Endpoint REST API pada Postman</em>
</p>

<br>

### 4.1 Auth Endpoints

| No | Endpoint | Method | Status | Screenshot |
|----|----------|--------|--------|------------|
| 1 | `/auth/register` | POST | 201 Created | <img src="result/postman/postman_register.png" width="400" alt="Register"> |
| 2 | `/auth/login` | POST | 200 OK | <img src="result/postman/postman_login.png" width="400" alt="Login"> |
| 3 | `/auth/me` | GET | 200 OK | <img src="result/postman/postman_me.png" width="400" alt="Me"> |

### 4.2 Product Endpoints

| No | Endpoint | Method | Status | Screenshot |
|----|----------|--------|--------|------------|
| 4 | `/products` | GET | 200 OK | <img src="result/postman/postman_products.png" width="400" alt="Products"> |
| 5 | `/products/<id>` | GET | 200 OK | <img src="result/postman/postman_product_detail.png" width="400" alt="Product Detail"> |

### 4.3 Order Endpoints

| No | Endpoint | Method | Status | Screenshot |
|----|----------|--------|--------|------------|
| 6 | `/orders` | POST | 201 Created | <img src="result/postman/postman_create_order.png" width="400" alt="Create Order"> |
| 7 | `/orders` | GET | 200 OK | <img src="result/postman/postman_list_orders.png" width="400" alt="List Orders"> |
| 8 | `/orders/<order_id>` | GET | 200 OK | <img src="result/postman/postman_order_detail.png" width="400" alt="Order Detail"> |
| 9 | `/orders/<order_id>/status` | PUT | 200 OK | <img src="result/postman/postman_update_status.png" width="400" alt="Update Status"> |

### 4.4 Admin Endpoints

| No | Endpoint | Method | Status | Screenshot |
|----|----------|--------|--------|------------|
| 10 | `/admin/stats` | GET | 200 OK | <img src="result/postman/postman_admin_stats.png" width="400" alt="Stats"> |
| 11 | `/admin/users` | GET | 200 OK | <img src="result/postman/postman_admin_users.png" width="400" alt="Users"> |
| 12 | `/health` | GET | 200 OK | <img src="result/postman/postman_health.png" width="400" alt="Health"> |

### 4.5 Tampilan Frontend

Berikut adalah beberapa tampilan antarmuka web frontend yang telah berhasil diuji dan berjalan melalui IP Load Balancer (`20.41.112.161`):

<p align="center">
  <img src="result/frontend/frontend_create_order.png" width="450" alt="Frontend - Buat Pesanan Baru"><br>
  <em>Gambar 4.1: Tampilan Halaman Pembuatan Pesanan Baru</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_check_status.png" width="450" alt="Frontend - Cek Status Pesanan"><br>
  <em>Gambar 4.2: Tampilan Halaman Pengecekan Status Pesanan</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_update_status.png" width="450" alt="Frontend - Update Status Pesanan"><br>
  <em>Gambar 4.3: Tampilan Halaman Pembaruan Status Pesanan (Admin)</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_order_history.png" width="450" alt="Frontend - Riwayat Pesanan"><br>
  <em>Gambar 4.4: Tampilan Halaman Riwayat Transaksi Pesanan</em>
</p>

---

## 5. Hasil Load Testing

Load testing dilakukan menggunakan Locust dari host yang berbeda dari server aplikasi.

**Konfigurasi Locust:**
- File: `locustfile.py` (disediakan)
- Host target: `http://<IP_LOAD_BALANCER>`
- User types: CustomerUser (80%) + AdminUser (20%)

**Catatan:** Database orders yang di-insert selama testing dihapus sebelum setiap skenario baru. Data awal (dump) tidak dihapus.

### 5.1 Skenario 1: Maksimum RPS (0% Failure)

Skenario 1 diuji dengan tiga kondisi pembebanan bertahap:

#### 5.1.1 Skenario 1A: Beban Konkurensi 700 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 15 / detik (Gradual)
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Jumlah User | 700 |
| Rata-rata RPS | **127.14** (Peak: 200.9) |
| Failure Rate | 0% |
| Avg Response Time | 310 ms |

<p align="center">
  <img src="result/skenario1/locust_rps.png" width="600" alt="Locust Skenario 1A"><br>
  <em>Gambar 5.1: Grafik Pengetesan Skenario 1A (700 Users)</em>
</p>

#### 5.1.2 Skenario 1B: Beban Konkurensi 1050 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 15 / detik (Gradual)
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Jumlah User | 1050 |
| Rata-rata RPS | **144.69** |
| Failure Rate | 0% |
| Avg Response Time | 320 ms |

<p align="center">
  <img src="result/skenario1/locust_concurrency_sr15_1050.png" width="550" alt="Locust Skenario 1B"><br>
  <em>Gambar 5.1a: Grafik Pengetesan Skenario 1B (1050 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_app1_scenario1_1050.png" width="300" alt="CPU App Server 1 1050">
  <img src="result/skenario1/cpu_app2_scenario1_1050.png" width="300" alt="CPU App Server 2 1050"><br>
  <em>Gambar 5.1b: CPU & Memory App Server 1 & 2 (Skenario 1B - 1050 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_db_scenario1_1050.png" width="450" alt="CPU Database MongoDB 1050"><br>
  <em>Gambar 5.1c: Penggunaan Resource pada Database MongoDB (Skenario 1B - 1050 Users)</em>
</p>

#### 5.1.3 Skenario 1C: Beban Konkurensi 1150 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 15 / detik (Gradual)
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Jumlah User | 1150 |
| Rata-rata RPS | **147.06** |
| Failure Rate | 1% |
| Avg Response Time | 220 ms |

<p align="center">
  <img src="result/skenario1/locust_concurrency_sr15_1150.png" width="550" alt="Locust Skenario 1C"><br>
  <em>Gambar 5.1d: Grafik Pengetesan Skenario 1C (1150 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_app1_scenario1_1150.png" width="300" alt="CPU App Server 1 1150">
  <img src="result/skenario1/cpu_app2_scenario1_1150.png" width="300" alt="CPU App Server 2 1150"><br>
  <em>Gambar 5.1e: CPU & Memory App Server 1 & 2 (Skenario 1C - 1150 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_db_scenario1_1150.png" width="450" alt="CPU Database MongoDB 1150"><br>
  <em>Gambar 5.1f: Penggunaan Resource pada Database MongoDB (Skenario 1C - 1150 Users)</em>
</p>

### 5.2 Skenario 2: Peak Concurrency - Spawn Rate 50

Skenario 2 diuji dengan empat kondisi pembebanan yang berbeda:

#### 5.2.1 Skenario 2A: Beban Konkurensi 300 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 50
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **300** |
| Rata-rata RPS | 93.97 |
| Avg Response Time | 180 ms |

<p align="center">
  <img src="result/skenario2/locust_concurrency_sr50_300.jpg" width="550" alt="Locust Skenario 2A"><br>
  <em>Gambar 5.2: Grafik Pengetesan Skenario 2A (300 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_300.jpg" width="300" alt="CPU App Server 1 300">
  <img src="result/skenario2/cpu_app2_scenario2_300.jpg" width="300" alt="CPU App Server 2 300"><br>
  <em>Gambar 5.3: CPU & Memory App Server 1 & 2 (Skenario 2A - 300 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_300.jpg" width="450" alt="CPU Database MongoDB 300"><br>
  <em>Gambar 5.4: Penggunaan Resource pada Database MongoDB (Skenario 2A - 300 Users)</em>
</p>

#### 5.2.2 Skenario 2B: Beban Konkurensi 350 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 50
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **350** |
| Rata-rata RPS | 111.73 |
| Avg Response Time | 280 ms |

<p align="center">
  <img src="result/skenario2/locust_concurrency_sr50_350.jpg" width="550" alt="Locust Skenario 2B"><br>
  <em>Gambar 5.5: Grafik Pengetesan Skenario 2B (350 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_350.jpg" width="300" alt="CPU App Server 1 350">
  <img src="result/skenario2/cpu_app2_scenario2_350.jpg" width="300" alt="CPU App Server 2 350"><br>
  <em>Gambar 5.6: CPU & Memory App Server 1 & 2 (Skenario 2B - 350 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_350.jpg" width="450" alt="CPU Database MongoDB 350"><br>
  <em>Gambar 5.7: Penggunaan Resource pada Database MongoDB (Skenario 2B - 350 Users)</em>
</p>

#### 5.2.3 Skenario 2C: Beban Konkurensi 700 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 50
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **700** |
| Rata-rata RPS | 206.29 |
| Avg Response Time | 170 ms |

<p align="center">
  <img src="result/skenario2/locust_concurrency_sr50_700.png" width="550" alt="Locust Skenario 2C"><br>
  <em>Gambar 5.8: Grafik Pengetesan Skenario 2C (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_700.png" width="300" alt="CPU App Server 1 700">
  <img src="result/skenario2/cpu_app2_scenario2_700.png" width="300" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.9: CPU & Memory App Server 1 & 2 (Skenario 2C - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_700.png" width="450" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.10: Penggunaan Resource pada Database MongoDB (Skenario 2C - 700 Users)</em>
</p>

#### 5.2.4 Skenario 2D: Beban Konkurensi 900 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 50
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (dengan fail) | **900** |
| Rata-rata RPS | 243.17 |
| Avg Response Time | 170 ms |
| Failure Rate | 1% |

<p align="center">
  <img src="result/skenario2/locust_concurrency_sr50_900.png" width="550" alt="Locust Skenario 2D"><br>
  <em>Gambar 5.11: Grafik Pengetesan Skenario 2D (900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_900.png" width="300" alt="CPU App Server 1 900">
  <img src="result/skenario2/cpu_app2_scenario2_900.png" width="300" alt="CPU App Server 2 900"><br>
  <em>Gambar 5.12: CPU & Memory App Server 1 & 2 (Skenario 2D - 900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_900.png" width="450" alt="CPU Database MongoDB 900"><br>
  <em>Gambar 5.13: Penggunaan Resource pada Database MongoDB (Skenario 2D - 900 Users)</em>
</p>

### 5.3 Skenario 3: Peak Concurrency - Spawn Rate 100

Skenario 3 diuji dengan tiga kondisi pembebanan yang berbeda:

#### 5.3.1 Skenario 3A: Beban Konkurensi 500 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 100
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **500** |
| Rata-rata RPS | 156.88 |
| Avg Response Time | 170 ms |

<p align="center">
  <img src="result/skenario3/locust_concurrency_sr100_500.png" width="550" alt="Locust Skenario 3A"><br>
  <em>Gambar 5.14: Grafik Pengetesan Skenario 3A (500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_500.png" width="300" alt="CPU App Server 1 500">
  <img src="result/skenario3/cpu_app2_scenario3_500.png" width="300" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.15: CPU & Memory App Server 1 & 2 (Skenario 3A - 500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_500.png" width="450" alt="CPU Database MongoDB 500"><br>
  <em>Gambar 5.16: Penggunaan Resource pada Database MongoDB (Skenario 3A - 500 Users)</em>
</p>

#### 5.3.2 Skenario 3B: Beban Konkurensi 700 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 100
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **700** |
| Rata-rata RPS | 216.76 |
| Avg Response Time | 330 ms |

<p align="center">
  <img src="result/skenario3/locust_concurrency_sr100_700.png" width="550" alt="Locust Skenario 3B"><br>
  <em>Gambar 5.17: Grafik Pengetesan Skenario 3B (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_700.png" width="300" alt="CPU App Server 1 700">
  <img src="result/skenario3/cpu_app2_scenario3_700.png" width="300" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.18: CPU & Memory App Server 1 & 2 (Skenario 3B - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_700.png" width="450" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.19: Penggunaan Resource pada Database MongoDB (Skenario 3B - 700 Users)</em>
</p>

#### 5.3.3 Skenario 3C: Beban Konkurensi 900 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 100
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (dengan fail) | **900** |
| Rata-rata RPS | 206.76 |
| Avg Response Time | 300 ms |
| Failure Rate | 2% |

<p align="center">
  <img src="result/skenario3/locust_concurrency_sr100_900.png" width="550" alt="Locust Skenario 3C"><br>
  <em>Gambar 5.20: Grafik Pengetesan Skenario 3C (900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_900.png" width="300" alt="CPU App Server 1 900">
  <img src="result/skenario3/cpu_app2_scenario3_900.png" width="300" alt="CPU App Server 2 900"><br>
  <em>Gambar 5.21: CPU & Memory App Server 1 & 2 (Skenario 3C - 900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_900.png" width="450" alt="CPU Database MongoDB 900"><br>
  <em>Gambar 5.22: Penggunaan Resource pada Database MongoDB (Skenario 3C - 900 Users)</em>
</p>

### 5.4 Skenario 4: Peak Concurrency - Spawn Rate 200

Skenario 4 diuji dengan dua kondisi pembebanan yang berbeda:

#### 5.4.1 Skenario 4A: Beban Konkurensi 500 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 200
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **500** |
| Rata-rata RPS | 130.87 |
| Avg Response Time | 180 ms |

<p align="center">
  <img src="result/skenario4/locust_concurrency_sr200_500.png" width="550" alt="Locust Skenario 4A"><br>
  <em>Gambar 5.23: Grafik Pengetesan Skenario 4A (500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_app1_scenario4_500.png" width="300" alt="CPU App Server 1 500">
  <img src="result/skenario4/cpu_app2_scenario4_500.png" width="300" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.24: CPU & Memory App Server 1 & 2 (Skenario 4A - 500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_db_scenario4_500.png" width="450" alt="CPU Database MongoDB 500"><br>
  <em>Gambar 5.25: Penggunaan Resource pada Database MongoDB (Skenario 4A - 500 Users)</em>
</p>

#### 5.4.2 Skenario 4B: Beban Konkurensi 700 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 200
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (dengan fail) | **700** |
| Rata-rata RPS | 165.28 |
| Avg Response Time | 320 ms |
| Failure Rate | 1% |

<p align="center">
  <img src="result/skenario4/locust_concurrency_sr200_700.png" width="550" alt="Locust Skenario 4B"><br>
  <em>Gambar 5.26: Grafik Pengetesan Skenario 4B (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_app1_scenario4_700.png" width="300" alt="CPU App Server 1 700">
  <img src="result/skenario4/cpu_app2_scenario4_700.png" width="300" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.27: CPU & Memory App Server 1 & 2 (Skenario 4B - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_db_scenario4_700.png" width="450" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.28: Penggunaan Resource pada Database MongoDB (Skenario 4B - 700 Users)</em>
</p>

### 5.5 Skenario 5: Peak Concurrency - Spawn Rate 500

Skenario 5 diuji dengan dua kondisi pembebanan yang berbeda:

#### 5.5.1 Skenario 5A: Beban Konkurensi 600 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 500
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **600** |
| Rata-rata RPS | 154.53 |
| Avg Response Time | 180 ms |

<p align="center">
  <img src="result/skenario5/locust_concurrency_sr500_700.png" width="550" alt="Locust Skenario 5A"><br>
  <em>Gambar 5.29: Grafik Pengetesan Skenario 5A (600 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_app1_scenario5_700.png" width="300" alt="CPU App Server 1 700">
  <img src="result/skenario5/cpu_app2_scenario5_700.png" width="300" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.30: CPU & Memory App Server 1 & 2 (Skenario 5A - 600 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_db_scenario5_700.png" width="450" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.31: Penggunaan Resource pada Database MongoDB (Skenario 5A - 600 Users)</em>
</p>

#### 5.5.2 Skenario 5B: Beban Konkurensi 1000 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 500
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (dengan fail) | **1000** |
| Rata-rata RPS | 196.75 |
| Avg Response Time | 310 ms |
| Failure Rate | 3% |

<p align="center">
  <img src="result/skenario5/locust_concurrency_sr500_500.png" width="550" alt="Locust Skenario 5B"><br>
  <em>Gambar 5.32: Grafik Pengetesan Skenario 5B (1000 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_app1_scenario5_500.png" width="300" alt="CPU App Server 1 500">
  <img src="result/skenario5/cpu_app2_scenario5_500.png" width="300" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.33: CPU & Memory App Server 1 & 2 (Skenario 5B - 1000 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_db_scenario5_500.png" width="450" alt="CPU Database MongoDB 500"><br>
  <em>Gambar 5.34: Penggunaan Resource pada Database MongoDB (Skenario 5B - 1000 Users)</em>
</p>

### 5.6 Ringkasan Hasil Load Testing

| Skenario | Spawn Rate | Max Users (0% fail) | Avg RPS | Avg Response Time |
|----------|------------|---------------------|---------|-------------------|
| 1 - Max RPS | bertahap | 1050 | **144.69** | 320 ms |
| 2 - Peak Concurrency | 50 | 700 | 206.29 | 170 ms |
| 3 - Peak Concurrency | 100 | 700 | 216.76 | 330 ms |
| 4 - Peak Concurrency | 200 | 500 | 130.87 | 180 ms |
| 5 - Peak Concurrency | 500 | 600 | 154.53 | 180 ms |

---

## 6. Kesimpulan dan Saran

### 6.1 Kesimpulan

### 6.1 Kesimpulan

Berdasarkan hasil load testing yang telah dilakukan pada kelima skenario, berikut adalah analisis dan kesimpulan mengenai performa sistem:

- **Kapasitas Maksimal Sistem**: Arsitektur dengan 3 App Server (VM2, VM3, & VM4) yang di-load balance oleh Nginx (VM1) serta menggunakan database MongoDB terpisah (VM5) mampu menangani hingga **1050 concurrent users** dengan **0% failure rate** pada Skenario 1B (rata-rata RPS **144.69**).
- **Bottleneck Utama**: Bottleneck utama sistem terletak pada **Database Server (MongoDB)**. Ketika jumlah user meningkat sangat tinggi, penggunaan CPU pada VM5 (Database Server) melonjak tajam (mencapai >140% pada Docker Stats), karena MongoDB harus melakukan operasi penulisan transaksi (`POST /orders`) yang melibatkan I/O disk dan pembaruan index secara terus-menerus.
- **Pengaruh Spawn Rate**: Spawn rate yang lebih tinggi (seperti 200 dan 500 user/detik) menyebabkan penurunan jumlah concurrent user maksimal yang dapat ditangani dengan aman (0% fail). Hal ini dikarenakan lonjakan trafik yang tiba-tiba membuat database connection pool dan antrean request Nginx langsung penuh seketika sebelum sistem sempat menyeimbangkan resource, mengakibatkan beberapa request mengalami timeout.
- **Efektivitas Gevent Worker**: Penggunaan `gevent` worker pada Gunicorn terbukti **sangat efektif** dibanding sync worker standar. Dengan total hanya 9 workers (3 worker per VM), sistem mampu menangani lebih dari 1000 concurrent users karena gevent menggunakan coroutine asynchronous untuk mengalihkan pemrosesan request lain selagi menunggu respon I/O dari MongoDB.

### 6.2 Saran untuk Deployment Masa Depan

1. **Caching Layer** - Menambahkan Redis sebagai cache untuk endpoint read-heavy seperti `/products` dan `/admin/stats` dapat mengurangi beban MongoDB secara signifikan
2. **MongoDB Replica Set** - Menggunakan replica set dengan read preference `secondaryPreferred` untuk mendistribusikan query read ke secondary nodes
3. **Connection Pooling** - Mengoptimalkan `maxPoolSize` pada PyMongo sesuai jumlah concurrent connections yang diharapkan
4. **Container Orchestration** - Migrasi ke Docker + Kubernetes untuk auto-scaling berdasarkan metrik CPU/memory
5. **CDN untuk Frontend** - Menggunakan CDN (Cloudflare, CloudFront) untuk menyajikan static assets agar mengurangi beban pada load balancer
6. **Monitoring** - Implementasi monitoring stack (Prometheus + Grafana) untuk pemantauan real-time

### 6.3 Estimasi Biaya pada Cloud Provider

| Provider | Konfigurasi Setara | Estimasi/bulan |
|----------|-------------------|----------------|
| Google Cloud Platform | 4x e2-small + 1x e2-medium | ~$50-70 |
| Digital Ocean | 4x Basic $12 + 1x Basic $24 | ~$72 |
| Microsoft Azure | 4x B1s + 1x B2s | ~$60-80 |
