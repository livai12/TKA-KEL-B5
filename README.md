# Laporan Final Project Teknologi Komputasi Awan - Kelompok 5

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

## 1. Pendahuluan

Laporan ini disusun untuk memenuhi tugas Final Project mata kuliah Teknologi Komputasi Awan 2026. Fokus utama proyek ini adalah merancang, mengimplementasikan, dan mengoptimalkan layanan backend **Order Processing Service** berbasis REST API untuk platform e-commerce yang menggunakan basis data MongoDB.

### Permasalahan dan Batasan
1. **Layanan Inti**: Mengelola pembuatan pesanan (`POST /order`), pengecekan status pesanan (`GET /order/<order_id>`), riwayat pesanan (`GET /orders`), dan pembaruan status pesanan (`PUT /order/<order_id>`).
2. **Skalabilitas**: Sistem harus dioptimalkan untuk menangani lonjakan beban trafik (flash sale) secara andal dan efisien.
3. **Batasan Anggaran**: Anggaran maksimal untuk seluruh infrastruktur adalah 75 US$ per bulan.
4. **Batasan Infrastruktur**: Layanan dideploy menggunakan arsitektur terdistribusi dengan VM yang dibagi pada minimal 2 komputer fisik berbeda (pada lingkungan produksi/simulasi final).

### Solusi yang Diusulkan
Untuk mencapai hasil performa maksimal dalam batas anggaran 75 US$/bulan, diimplementasikan arsitektur cluster sebagai berikut:
- **Load Balancer**: Nginx dengan algoritma `least_conn` dan optimasi HTTP keepalive.
- **Backend App Server**: 3 instance Flask Server yang dijalankan menggunakan WSGI HTTP Server Gunicorn dengan `gevent` asynchronous worker (coroutine).
- **Database Server**: 1 instance MongoDB Server yang dioptimalkan dengan indexing serta konfigurasi cache WiredTiger.

---

## 2. Arsitektur Cloud

### 2.1 Diagram Arsitektur


```
                           +-------------------+
                           |   VM1 (512MB)     |
                           |   Nginx LB +      |
   Trafik Pengguna ------->|   Frontend        |
                           +--------+----------+
                                    |
                    +---------------+---------------+
                    |                               |
             +------+------+                 +------+------+
             | VM2 (2GB)   |                 | VM3 (2GB)   |
             | Flask +     |                 | Flask +     |
             | Gunicorn    |                 | Gunicorn    |
             +------+------+                 +------+------+
                    |                               |
                    +---------------+---------------+
                                    |
                           +--------+----------+
                           |   VM4 (4GB)       |
                           |   MongoDB 7.0     |
                           +-------------------+
```

<img width="609" height="363" alt="TKA drawio" src="https://github.com/user-attachments/assets/4dc94adb-164e-48dc-8ad4-119b578f2706" />

### 2.2 Tabel Spesifikasi dan Estimasi Biaya

Sistem dibagi ke dalam 4 VM dengan pembagian host fisik untuk simulasi lokal:

| No | VM | Peran | Tipe VM | CPU | RAM | Harga/bulan | Host Fisik |
|----|------|-------|------|-----|-----|-------------|------|
| 1 | VM1 | Load Balancer (Nginx) + Frontend | B1ls | 1 vCPU | 512 MB | $4,75 | VM Azure  |
| 2 | VM2 | App Server 1 (Flask + Gunicorn) | B1ms | 1 vCPU | 2 GB | $17,37 | VM Azure |
| 3 | VM3 | App Server 2 (Flask + Gunicorn) | B1ms | 1 vCPU | 2 GB | $17,37 | VM Azure |
| 4 | VM4 | Database Server (MongoDB) | B2ls_v2 | 2 vCPU | 4 GB | $34,68 | VM Azure |
| | | | **TOTAL** | | | **$74,17** | |

Budget terpakai: $74,17 dari $75 (Biaya tersisa sekitar $0,83).

---

## 3. Implementasi Sistem

### 3.1 Setup Database MongoDB 
MongoDB diinstal pada VM4 dengan alokasi memori terbesar (4 GB RAM) karena database memproses seluruh transaksi data I/O.

Langkah konfigurasi:
1. Pemasangan repositori MongoDB dan instalasi paket `mongodb-org`.
2. Pengaturan `bindIp` pada file `/etc/mongod.conf` menjadi `0.0.0.0` untuk memperbolehkan koneksi dari luar VM.
3. Import data awal e-commerce menggunakan perintah `mongorestore --drop dump/`.
4. Pembuatan database index untuk mempercepat pencarian data order, user, dan product:
   ```bash
   mongosh orderdb --eval '
     db.orders.createIndex({order_id: 1});
     db.orders.createIndex({user_id: 1, created_at: -1});
     db.orders.createIndex({status: 1});
     db.orders.createIndex({created_at: -1});
     db.products.createIndex({category: 1, is_active: 1});
     db.users.createIndex({email: 1}, {unique: true});
   '
   ```

### 3.2 Setup Application Server (VM2, VM3)
Masing-masing dari ketiga server aplikasi dipasang runtime Python dan diatur menggunakan systemd service agar aplikasi Flask berjalan di latar belakang secara otomatis.

Langkah konfigurasi:
1. Pemasangan `python3-pip` dan `python3-venv`.
2. Pembuatan virtual environment di `/home/ubuntu/app/venv`.
3. Pemasangan dependensi Python (Flask, PyMongo, Gevent, Gunicorn, PyJWT).
4. Pembuatan unit service systemd `/etc/systemd/system/flask-app.service` dengan konfigurasi:
   ```ini
   [Unit]
   Description=Gunicorn instance to serve Order Processing REST API
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/app
   Environment="MONGO_URI=mongodb://<IP_VM5>:27017/"
   Environment="JWT_SECRET=rahasia-bersama-tka-26"
   ExecStart=/home/ubuntu/app/venv/bin/gunicorn -w 3 -k gevent -b 0.0.0.0:5000 app:app --timeout 120 --max-requests 1000

   [Install]
   WantedBy=multi-user.target
   ```
5. Menjalankan service dengan perintah `sudo systemctl enable --now flask-app`.

### 3.3 Setup Load Balancer Nginx (VM1)
Nginx dipasang pada VM1 untuk bertindak sebagai Reverse Proxy sekaligus Load Balancer yang mendistribusikan beban secara efisien.

Langkah konfigurasi:
1. Instalasi Nginx dengan perintah `sudo apt install nginx`.
2. Konfigurasi file upstream server `/etc/nginx/sites-available/orderservice`:
   ```nginx
   upstream backend_servers {
       least_conn;
       server <IP_VM2_APP1>:5000 max_fails=3 fail_timeout=10s;
       server <IP_VM3_APP2>:5000 max_fails=3 fail_timeout=10s;
       server <IP_VM4_APP3>:5000 max_fails=3 fail_timeout=10s;
       keepalive 64;
   }

   server {
       listen 80;
       server_name localhost;

       # Serve static frontend files
       location / {
           root /var/www/frontend;
           index index.html;
           try_files $uri $uri/ =404;
       }

       # Proxy API requests to Flask backend
       location ~ ^/(auth|products|orders|admin|health) {
           proxy_pass http://backend_servers;
           proxy_http_version 1.1;
           proxy_set_header Connection "";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_read_timeout 60s;
           proxy_connect_timeout 5s;
       }
   }
   ```
3. Membuat symlink ke direktori `sites-enabled` dan reload Nginx.

---

## 4. Hasil Pengujian Endpoint

Pengujian dilakukan menggunakan Postman untuk memverifikasi fungsionalitas seluruh endpoint API. Berikut adalah daftar seluruh endpoint REST API yang telah dikonfigurasi:

<p align="center">
  <img src="result/postman/postman_list_endpoints.png" width="250" alt="Daftar Seluruh Endpoint Postman"><br>
  <em>Gambar 4.0: Daftar Seluruh Endpoint REST API pada Postman</em>
</p>

<br>

| No | Endpoint | HTTP Method | Deskripsi | Status | Screenshot |
|----|----------|-------------|-----------|--------|------------|
| 1  | `/auth/register` | POST | Pendaftaran user baru | 201 Created | <img src="result/postman/postman_register.png" width="150" alt="Register"> |
| 2  | `/auth/login` | POST | Login user untuk mendapatkan JWT | 200 OK | <img src="result/postman/postman_login.png" width="150" alt="Login"> |
| 3  | `/auth/me` | GET | Mendapatkan profil user aktif | 200 OK | <img src="result/postman/postman_me.png" width="150" alt="Me"> |
| 4  | `/products` | GET | Mendapatkan daftar produk | 200 OK | <img src="result/postman/postman_products.png" width="150" alt="Products"> |
| 5  | `/products/<id>` | GET | Mendapatkan detail produk spesifik | 200 OK | <img src="result/postman/postman_product_detail.png" width="150" alt="Product Detail"> |
| 6  | `/orders` | POST | Membuat pesanan baru | 201 Created | <img src="result/postman/postman_create_order.png" width="150" alt="Create Order"> |
| 7  | `/orders` | GET | Mendapatkan riwayat pesanan user | 200 OK | <img src="result/postman/postman_list_orders.png" width="150" alt="List Orders"> |
| 8  | `/orders/<order_id>` | GET | Mendapatkan detail status pesanan | 200 OK | <img src="result/postman/postman_order_detail.png" width="150" alt="Order Detail"> |
| 9  | `/orders/<order_id>/status` | PUT | Mengubah status pesanan (Admin) | 200 OK | <img src="result/postman/postman_update_status.png" width="150" alt="Update Status"> |
| 10 | `/admin/stats` | GET | Mengambil statistik penjualan (Admin) | 200 OK | <img src="result/postman/postman_admin_stats.png" width="150" alt="Stats"> |
| 11 | `/admin/users` | GET | Mendapatkan daftar seluruh user (Admin) | 200 OK | <img src="result/postman/postman_admin_users.png" width="150" alt="Users"> |
| 12 | `/health` | GET | Cek kesehatan koneksi backend & DB | 200 OK | <img src="result/postman/postman_health.png" width="150" alt="Health"> |

### 4.5 Tampilan Frontend

Berikut adalah beberapa tampilan antarmuka web frontend yang telah berhasil diuji dan berjalan melalui IP Load Balancer (`20.41.112.161`):

<p align="center">
  <img src="result/frontend/frontend_create_order.png" width="250" alt="Frontend - Buat Pesanan Baru"><br>
  <em>Gambar 4.1: Tampilan Halaman Pembuatan Pesanan Baru</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_check_status.png" width="250" alt="Frontend - Cek Status Pesanan"><br>
  <em>Gambar 4.2: Tampilan Halaman Pengecekan Status Pesanan</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_update_status.png" width="250" alt="Frontend - Update Status Pesanan"><br>
  <em>Gambar 4.3: Tampilan Halaman Pembaruan Status Pesanan (Admin)</em>
</p>

<br>

<p align="center">
  <img src="result/frontend/frontend_order_history.png" width="250" alt="Frontend - Riwayat Pesanan"><br>
  <em>Gambar 4.4: Tampilan Halaman Riwayat Transaksi Pesanan</em>
</p>

---

## 5. Hasil Load Testing (Locust)

Pengujian beban (load testing) dilakukan dari komputer terpisah (client locust) yang terhubung ke jaringan load balancer untuk mensimulasikan trafik nyata secara real-time.

*Setiap sebelum menjalankan skenario baru, data testing pada database dibersihkan menggunakan script `/home/ubuntu/deploy/cleanup_orders.sh` agar tidak memengaruhi hasil pengujian berikutnya.*


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
  <img src="result/skenario1/locust_rps.png" width="400" alt="Locust Skenario 1A"><br>
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
  <img src="result/skenario1/locust_concurrency_sr15_1050.png" width="400" alt="Locust Skenario 1B"><br>
  <em>Gambar 5.1a: Grafik Pengetesan Skenario 1B (1050 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_app1_scenario1_1050.png" width="200" alt="CPU App Server 1 1050">
  <img src="result/skenario1/cpu_app2_scenario1_1050.png" width="200" alt="CPU App Server 2 1050"><br>
  <em>Gambar 5.1b: CPU & Memory App Server 1 & 2 (Skenario 1B - 1050 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_db_scenario1_1050.png" width="300" alt="CPU Database MongoDB 1050"><br>
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
  <img src="result/skenario1/locust_concurrency_sr15_1150.png" width="400" alt="Locust Skenario 1C"><br>
  <em>Gambar 5.1d: Grafik Pengetesan Skenario 1C (1150 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_app1_scenario1_1150.png" width="200" alt="CPU App Server 1 1150">
  <img src="result/skenario1/cpu_app2_scenario1_1150.png" width="200" alt="CPU App Server 2 1150"><br>
  <em>Gambar 5.1e: CPU & Memory App Server 1 & 2 (Skenario 1C - 1150 Users)</em>
</p>

<p align="center">
  <img src="result/skenario1/cpu_db_scenario1_1150.png" width="300" alt="CPU Database MongoDB 1150"><br>
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
  <img src="result/skenario2/locust_concurrency_sr50_300.jpg" width="400" alt="Locust Skenario 2A"><br>
  <em>Gambar 5.2: Grafik Pengetesan Skenario 2A (300 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_300.jpg" width="200" alt="CPU App Server 1 300">
  <img src="result/skenario2/cpu_app2_scenario2_300.jpg" width="200" alt="CPU App Server 2 300"><br>
  <em>Gambar 5.3: CPU & Memory App Server 1 & 2 (Skenario 2A - 300 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_300.jpg" width="300" alt="CPU Database MongoDB 300"><br>
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
  <img src="result/skenario2/locust_concurrency_sr50_350.jpg" width="400" alt="Locust Skenario 2B"><br>
  <em>Gambar 5.5: Grafik Pengetesan Skenario 2B (350 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_350.jpg" width="200" alt="CPU App Server 1 350">
  <img src="result/skenario2/cpu_app2_scenario2_350.jpg" width="200" alt="CPU App Server 2 350"><br>
  <em>Gambar 5.6: CPU & Memory App Server 1 & 2 (Skenario 2B - 350 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_350.jpg" width="300" alt="CPU Database MongoDB 350"><br>
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
  <img src="result/skenario2/locust_concurrency_sr50_700.png" width="400" alt="Locust Skenario 2C"><br>
  <em>Gambar 5.8: Grafik Pengetesan Skenario 2C (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_700.png" width="200" alt="CPU App Server 1 700">
  <img src="result/skenario2/cpu_app2_scenario2_700.png" width="200" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.9: CPU & Memory App Server 1 & 2 (Skenario 2C - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_700.png" width="300" alt="CPU Database MongoDB 700"><br>
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
  <img src="result/skenario2/locust_concurrency_sr50_900.png" width="400" alt="Locust Skenario 2D"><br>
  <em>Gambar 5.11: Grafik Pengetesan Skenario 2D (900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_app1_scenario2_900.png" width="200" alt="CPU App Server 1 900">
  <img src="result/skenario2/cpu_app2_scenario2_900.png" width="200" alt="CPU App Server 2 900"><br>
  <em>Gambar 5.12: CPU & Memory App Server 1 & 2 (Skenario 2D - 900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario2/cpu_db_scenario2_900.png" width="300" alt="CPU Database MongoDB 900"><br>
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
  <img src="result/skenario3/locust_concurrency_sr100_500.png" width="400" alt="Locust Skenario 3A"><br>
  <em>Gambar 5.14: Grafik Pengetesan Skenario 3A (500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_500.png" width="200" alt="CPU App Server 1 500">
  <img src="result/skenario3/cpu_app2_scenario3_500.png" width="200" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.15: CPU & Memory App Server 1 & 2 (Skenario 3A - 500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_500.png" width="300" alt="CPU Database MongoDB 500"><br>
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
  <img src="result/skenario3/locust_concurrency_sr100_700.png" width="400" alt="Locust Skenario 3B"><br>
  <em>Gambar 5.17: Grafik Pengetesan Skenario 3B (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_700.png" width="200" alt="CPU App Server 1 700">
  <img src="result/skenario3/cpu_app2_scenario3_700.png" width="200" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.18: CPU & Memory App Server 1 & 2 (Skenario 3B - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_700.png" width="300" alt="CPU Database MongoDB 700"><br>
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
  <img src="result/skenario3/locust_concurrency_sr100_900.png" width="400" alt="Locust Skenario 3C"><br>
  <em>Gambar 5.20: Grafik Pengetesan Skenario 3C (900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_app1_scenario3_900.png" width="200" alt="CPU App Server 1 900">
  <img src="result/skenario3/cpu_app2_scenario3_900.png" width="200" alt="CPU App Server 2 900"><br>
  <em>Gambar 5.21: CPU & Memory App Server 1 & 2 (Skenario 3C - 900 Users)</em>
</p>

<p align="center">
  <img src="result/skenario3/cpu_db_scenario3_900.png" width="300" alt="CPU Database MongoDB 900"><br>
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
  <img src="result/skenario4/locust_concurrency_sr200_500.png" width="400" alt="Locust Skenario 4A"><br>
  <em>Gambar 5.23: Grafik Pengetesan Skenario 4A (500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_app1_scenario4_500.png" width="200" alt="CPU App Server 1 500">
  <img src="result/skenario4/cpu_app2_scenario4_500.png" width="200" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.24: CPU & Memory App Server 1 & 2 (Skenario 4A - 500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_db_scenario4_500.png" width="300" alt="CPU Database MongoDB 500"><br>
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
  <img src="result/skenario4/locust_concurrency_sr200_700.png" width="400" alt="Locust Skenario 4B"><br>
  <em>Gambar 5.26: Grafik Pengetesan Skenario 4B (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_app1_scenario4_700.png" width="200" alt="CPU App Server 1 700">
  <img src="result/skenario4/cpu_app2_scenario4_700.png" width="200" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.27: CPU & Memory App Server 1 & 2 (Skenario 4B - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario4/cpu_db_scenario4_700.png" width="300" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.28: Penggunaan Resource pada Database MongoDB (Skenario 4B - 700 Users)</em>
</p>

### 5.5 Skenario 5: Peak Concurrency - Spawn Rate 500

Skenario 5 diuji dengan dua kondisi pembebanan yang berbeda:

#### 5.5.1 Skenario 5A: Beban Konkurensi 500 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 500
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (0% fail) | **500** |
| Rata-rata RPS | 234.3 |
| Avg Response Time | 180 ms |

<p align="center">
  <img src="result/skenario5/locust_concurrency_sr500_500.png" width="400" alt="Locust Skenario 5A"><br>
  <em>Gambar 5.29: Grafik Pengetesan Skenario 5A (500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_app1_scenario5_500.png" width="200" alt="CPU App Server 1 500">
  <img src="result/skenario5/cpu_app2_scenario5_500.png" width="200" alt="CPU App Server 2 500"><br>
  <em>Gambar 5.30: CPU & Memory App Server 1 & 2 (Skenario 5A - 500 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_db_scenario5_500.png" width="300" alt="CPU Database MongoDB 500"><br>
  <em>Gambar 5.31: Penggunaan Resource pada Database MongoDB (Skenario 5A - 500 Users)</em>
</p>

#### 5.5.2 Skenario 5B: Beban Konkurensi 700 Users
- **Durasi:** 60 detik
- **Spawn Rate:** 500
- **Hasil:**

| Metrik | Nilai |
|--------|-------|
| Max Concurrent Users (dengan fail) | **700** |
| Rata-rata RPS | 215.15 |
| Avg Response Time | 310 ms |
| Failure Rate | 1.1% |

<p align="center">
  <img src="result/skenario5/locust_concurrency_sr500_700.png" width="400" alt="Locust Skenario 5B"><br>
  <em>Gambar 5.32: Grafik Pengetesan Skenario 5B (700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_app1_scenario5_700.png" width="200" alt="CPU App Server 1 700">
  <img src="result/skenario5/cpu_app2_scenario5_700.png" width="200" alt="CPU App Server 2 700"><br>
  <em>Gambar 5.33: CPU & Memory App Server 1 & 2 (Skenario 5B - 700 Users)</em>
</p>

<p align="center">
  <img src="result/skenario5/cpu_db_scenario5_700.png" width="300" alt="CPU Database MongoDB 700"><br>
  <em>Gambar 5.34: Penggunaan Resource pada Database MongoDB (Skenario 5B - 700 Users)</em>
</p>

### 5.6 Ringkasan Hasil Load Testing

| Skenario | Spawn Rate | Max Users (0% fail) | Avg RPS | Avg Response Time |
|----------|------------|---------------------|---------|-------------------|
| 1 - Max RPS | bertahap | 1050 | **144.69** | 320 ms |
| 2 - Peak Concurrency | 50 | 700 | 206.29 | 170 ms |
| 3 - Peak Concurrency | 100 | 700 | 216.76 | 330 ms |
| 4 - Peak Concurrency | 200 | 500 | 130.87 | 180 ms |
| 5 - Peak Concurrency | 500 | 500 | 234.3 | 180 ms |

---

## 6. Kesimpulan dan Rekomendasi

### 6.1 Kesimpulan Analisis Sistem
1. Desain arsitektur dengan pemisahan database server (MongoDB) pada VM berspesifikasi tinggi (2 vCPU, 4 GB RAM) terbukti efektif meminimalkan hambatan (bottleneck) penulisan transaksi database.
2. Penggunaan 3 instance Application Server yang di-load balance oleh Nginx mendistribusikan trafik secara merata dan mencegah kelebihan beban pada satu node.
3. Penerapan `gevent` worker pada Gunicorn secara signifikan meningkatkan jumlah pemrosesan request secara concurrent dibandingkan sync worker biasa karena mampu mengelola blocking I/O secara asynchronous.

### 6.2 Rekomendasi Optimasi Masa Depan
1. **Caching Layer**: Menambahkan Redis di depan MongoDB untuk meng-cache produk (`GET /products`) dan data statistik (`GET /admin/stats`) yang jarang berubah, sehingga menurunkan utilisasi database.
2. **MongoDB Replica Set**: Mengonfigurasi replikasi database MongoDB dengan read preference diarahkan ke secondary nodes untuk mendistribusikan beban operasi baca.
3. **Database Connection Pool**: Mengatur setting `maxPoolSize` pada PyMongo agar koneksi reuse berjalan optimal tanpa menyebabkan error kehabisan file descriptor di sisi MongoDB server.
4. **Auto-scaling & Containerization**: Migrasi aplikasi dari virtual machine biasa ke Docker Container dengan orchestrator Kubernetes (K8s) agar scale up/down aplikasi backend berjalan dinamis sesuai beban trafik.
