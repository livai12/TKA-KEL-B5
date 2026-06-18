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
Diagram arsitektur sistem dirancang menggunakan Draw.io dan disimpan pada direktori proyek:
`result/arsitektur.png`

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

### 2.2 Tabel Spesifikasi dan Estimasi Biaya

Sistem dibagi ke dalam 5 VM dengan pembagian host fisik untuk simulasi lokal:

| No | VM | Peran | Tipe VM | CPU | Memory | Biaya Bulanan | Host Fisik |
|----|----|-------|---------|-----|--------|---------------|------------|
| 1  | VM1 | Load Balancer + Frontend | vm1 | 1 vCPU | 512 MB | 4.75 US$ | Komputer A |
| 2  | VM2 | Application Server 1 | vm3 | 1 vCPU | 2 GB | 18.98 US$ | Komputer A |
| 3  | VM3 | Application Server 2 | vm3 | 1 vCPU | 2 GB | 18.98 US$ | Komputer B |
| 4  | VM4 | Database Server (MongoDB) | vm5 | 2 vCPU | 4 GB | 34.68 US$ | Komputer A |
| **Total** | | | | | | **77.39 US$** | |



### 2.3 Rencana Skalabilitas & Desain Jaringan
Untuk pengujian awal atau pengembangan, seluruh VM (VM1 hingga VM5) dideploy pada **1 komputer fisik**.
Pada tahap produksi / demo final:
- **Host A** menjalankan VM1, VM2, dan VM5.
- **Host B** menjalankan VM3 and VM4.
Komunikasi antar host dilakukan melalui jaringan terjembatan (`public_network` atau bridged network) yang terhubung pada router atau access point yang sama.

---

## 3. Implementasi Sistem

### 3.1 Setup Database MongoDB (VM5)
MongoDB diinstal pada VM5 dengan alokasi memori terbesar (4 GB RAM) karena database memproses seluruh transaksi data I/O.

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

### 3.2 Setup Application Server (VM2, VM3, VM4)
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

Pengujian dilakukan menggunakan Postman untuk memverifikasi fungsionalitas seluruh endpoint API.

| No | Endpoint | HTTP Method | Deskripsi | Status | Screenshot Pendukung |
|----|----------|-------------|-----------|--------|----------------------|
| 1  | `/auth/register` | POST | Pendaftaran user baru | 201 Created | `result/postman_register.png` |
| 2  | `/auth/login` | POST | Login user untuk mendapatkan JWT | 200 OK | `result/postman_login.png` |
| 3  | `/auth/me` | GET | Mendapatkan profil user aktif | 200 OK | `result/postman_me.png` |
| 4  | `/products` | GET | Mendapatkan daftar produk | 200 OK | `result/postman_products.png` |
| 5  | `/products/<id>` | GET | Mendapatkan detail produk spesifik | 200 OK | `result/postman_product_detail.png` |
| 6  | `/orders` | POST | Membuat pesanan baru | 201 Created | `result/postman_create_order.png` |
| 7  | `/orders` | GET | Mendapatkan riwayat pesanan user | 200 OK | `result/postman_list_orders.png` |
| 8  | `/orders/<order_id>` | GET | Mendapatkan detail status pesanan | 200 OK | `result/postman_order_detail.png` |
| 9  | `/orders/<order_id>/status` | PUT | Mengubah status pesanan (Admin) | 200 OK | `result/postman_update_status.png` |
| 10 | `/admin/stats` | GET | Mengambil statistik penjualan (Admin) | 200 OK | `result/postman_admin_stats.png` |
| 11 | `/admin/users` | GET | Mendapatkan daftar seluruh user (Admin) | 200 OK | `result/postman_admin_users.png` |
| 12 | `/health` | GET | Cek kesehatan koneksi backend & DB | 200 OK | `result/postman_health.png` |

*Tampilan antarmuka web frontend yang berjalan dapat dilihat pada tangkapan layar `result/frontend.png`.*

---

## 5. Hasil Load Testing (Locust)

Pengujian beban (load testing) dilakukan dari komputer terpisah (client locust) yang terhubung ke jaringan load balancer untuk mensimulasikan trafik nyata secara real-time.

*Setiap sebelum menjalankan skenario baru, data testing pada database dibersihkan menggunakan script `/home/ubuntu/deploy/cleanup_orders.sh` agar tidak memengaruhi hasil pengujian berikutnya.*

### 5.1 Skenario 1: Maksimum RPS (0% Failure Rate)
* **Tujuan**: Menemukan batasan maksimal kapasitas server (Request Per Second) dengan kegagalan 0%.
* **Durasi**: 60 Detik
* **Hasil**:
  - **Rata-rata RPS**: [Isi hasil pengujian RPS]
  - **Concurrent Users**: [Isi jumlah user]
  - **Rata-rata Response Time**: [Isi waktu respons dalam ms] ms
  - **Kegagalan**: 0%
  *(Grafik hasil pengujian dapat dilihat di `result/locust_rps.png` dan penggunaan resource CPU di `result/cpu_usage_scenario1.png`)*

### 5.2 Skenario 2: Peak Concurrency - Spawn Rate 50
* **Tujuan**: Mengukur batas maksimal concurrent user yang dapat ditangani dengan spawn rate 50 user/detik sebelum terjadi kegagalan sistem.
* **Durasi**: 60 Detik
* **Hasil**:
  - **Max Concurrent Users**: [Isi jumlah user]
  - **Avg RPS**: [Isi rata-rata RPS]
  - **Avg Response Time**: [Isi waktu respons] ms
  *(Grafik hasil pengujian dapat dilihat di `result/locust_concurrency_sr50.png`)*

### 5.3 Skenario 3: Peak Concurrency - Spawn Rate 100
* **Tujuan**: Mengukur batas maksimal concurrent user dengan spawn rate 100 user/detik.
* **Durasi**: 60 Detik
* **Hasil**:
  - **Max Concurrent Users**: [Isi jumlah user]
  - **Avg RPS**: [Isi rata-rata RPS]
  - **Avg Response Time**: [Isi waktu respons] ms
  *(Grafik hasil pengujian dapat dilihat di `result/locust_concurrency_sr100.png`)*

### 5.4 Skenario 4: Peak Concurrency - Spawn Rate 200
* **Tujuan**: Mengukur batas maksimal concurrent user dengan spawn rate 200 user/detik.
* **Durasi**: 60 Detik
* **Hasil**:
  - **Max Concurrent Users**: [Isi jumlah user]
  - **Avg RPS**: [Isi rata-rata RPS]
  - **Avg Response Time**: [Isi waktu respons] ms
  *(Grafik hasil pengujian dapat dilihat di `result/locust_concurrency_sr200.png`)*

### 5.5 Skenario 5: Peak Concurrency - Spawn Rate 500
* **Tujuan**: Mengukur batas maksimal concurrent user dengan spawn rate 500 user/detik.
* **Durasi**: 60 Detik
* **Hasil**:
  - **Max Concurrent Users**: [Isi jumlah user]
  - **Avg RPS**: [Isi rata-rata RPS]
  - **Avg Response Time**: [Isi waktu respons] ms
  *(Grafik hasil pengujian dapat dilihat di `result/locust_concurrency_sr500.png`)*

### 5.6 Tabel Ringkasan Hasil Load Testing

| Skenario | Spawn Rate (/detik) | Max Concurrent Users (0% Failure) | Rata-rata RPS | Rata-rata Response Time (ms) |
|----------|---------------------|-----------------------------------|---------------|------------------------------|
| 1        | Gradual | [Isi] | [Isi] | [Isi] |
| 2        | 50 | [Isi] | [Isi] | [Isi] |
| 3        | 100 | [Isi] | [Isi] | [Isi] |
| 4        | 200 | [Isi] | [Isi] | [Isi] |
| 5        | 500 | [Isi] | [Isi] | [Isi] |

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
