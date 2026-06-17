# Panduan Pengujian API dengan Postman - FP TKA Kelompok B-05

Panduan ini berisi daftar request, payload, header, dan respon sukses yang harus didokumentasikan (di-screenshot) untuk laporan akhir.

> **Base URL**: `http://192.168.56.10`

---

## A. AKUN TESTING YANG BISA DIGUNAKAN
Database Anda sudah terisi akun berikut secara default dari dump database:
* **Akun User Biasa**: `user1@example.com` s.d `user50@example.com` (Password: `User@12345`)
* **Akun Admin**: `admin1@tka.its.ac.id` s.d `admin5@tka.its.ac.id` (Password: `Admin@12345`)

---

## B. DAFTAR ENDPOINT & LANGKAH PENGUJIAN

### 1. Register Akun Baru (`POST /auth/register`)
* **URL**: `http://192.168.56.10/auth/register`
* **Method**: `POST`
* **Headers**:
  * `Content-Type: application/json`
* **Body (JSON)**:
  ```json
  {
    "name": "Budi Luhur",
    "email": "budiluhur@example.com",
    "password": "User@12345",
    "city": "Surabaya",
    "phone": "081234567890",
    "address": "Jl. Teknik Kimia, Kampus ITS Sukolilo"
  }
  ```
* **Respon Sukses (201 Created)**: Mengembalikan pesan sukses, user data, dan `token`.
* **Screenshot File**: Simpan tangkapan layar Postman ini dengan nama `postman_register.png` di folder `result/`.

---

### 2. Login Akun (`POST /auth/login`)
* **URL**: `http://192.168.56.10/auth/login`
* **Method**: `POST`
* **Headers**:
  * `Content-Type: application/json`
* **Body (JSON)**:
  ```json
  {
    "email": "user1@example.com",
    "password": "User@12345"
  }
  ```
* **Respon Sukses (200 OK)**: Mengembalikan `token` dan data profil user.
* **Screenshot File**: Simpan dengan nama `postman_login.png` di folder `result/`.
* **CATATAN**: Salin string token yang dikembalikan untuk digunakan pada pengujian endpoint selanjutnya.

---

### 3. Check Current User Details (`GET /auth/me`)
* **URL**: `http://192.168.56.10/auth/me`
* **Method**: `GET`
* **Headers**:
  * `Authorization: Bearer <PASTE_TOKEN_LOGIN_USER_DI_SINI>`
* **Respon Sukses (200 OK)**: Mengembalikan profil lengkap user yang sedang aktif.
* **Screenshot File**: Simpan dengan nama `postman_me.png` di folder `result/`.

---

### 4. Menampilkan Katalog Produk (`GET /products`)
* **URL**: `http://192.168.56.10/products?page=1&limit=5`
* **Method**: `GET`
* **Respon Sukses (200 OK)**: Menampilkan list produk berserta stock, price, rating, dll.
* **Screenshot File**: Simpan dengan nama `postman_products.png` di folder `result/`.

---

### 5. Menampilkan Detail Produk Spesifik (`GET /products/<id>`)
* **URL**: `http://192.168.56.10/products/<id_produk>`
  *(Ambil salah satu `_id` produk dari hasil GET /products di atas, misal: `60b8d3c5f1d8c92b8c8b4567`)*
* **Method**: `GET`
* **Respon Sukses (200 OK)**: Detail deskripsi dan data produk tunggal.
* **Screenshot File**: Simpan dengan nama `postman_product_detail.png` di folder `result/`.

---

### 6. Membuat Pesanan Baru (`POST /orders`)
* **URL**: `http://192.168.56.10/orders`
* **Method**: `POST`
* **Headers**:
  * `Content-Type: application/json`
  * `Authorization: Bearer <TOKEN_USER>`
* **Body (JSON)**:
  ```json
  {
    "items": [
      {
        "product_id": "<MASUKKAN_ID_PRODUK_DI_SINI>",
        "qty": 2
      }
    ],
    "payment_method": "transfer_bank",
    "shipping_cost": 9000,
    "address": "Jl. Raya Kampus ITS Sukolilo, Surabaya",
    "notes": "Tolong kirim sebelum jam 5 sore"
  }
  ```
* **Respon Sukses (201 Created)**: Mengembalikan detail pesanan baru berserta status `"pending"`, total harga, dan `order_id` (berupa UUID).
* **Screenshot File**: Simpan dengan nama `postman_create_order.png` di folder `result/`.
* **CATATAN**: Salin string `order_id` (UUID) yang dikembalikan untuk pengujian status order berikutnya.

---

### 7. Menampilkan Riwayat Pesanan User (`GET /orders`)
* **URL**: `http://192.168.56.10/orders`
* **Method**: `GET`
* **Headers**:
  * `Authorization: Bearer <TOKEN_USER>`
* **Respon Sukses (200 OK)**: Daftar riwayat transaksi order milik user.
* **Screenshot File**: Simpan dengan nama `postman_list_orders.png` di folder `result/`.

---

### 8. Menampilkan Detail Pesanan Tertentu (`GET /orders/<order_id>`)
* **URL**: `http://192.168.56.10/orders/<PASTE_ORDER_ID_UUID_DI_SINI>`
* **Method**: `GET`
* **Headers**:
  * `Authorization: Bearer <TOKEN_USER>`
* **Respon Sukses (200 OK)**: Menampilkan detail item belanja, subtotal, ongkir, alamat, dan metode bayar untuk order terkait.
* **Screenshot File**: Simpan dengan nama `postman_order_detail.png` di folder `result/`.

---

### 9. Mengubah Status Pesanan (`PUT /orders/<order_id>/status`)
* **URL**: `http://192.168.56.10/orders/<PASTE_ORDER_ID_UUID_DI_SINI>/status`
* **Method**: `PUT`
* **Headers**:
  * `Content-Type: application/json`
  * `Authorization: Bearer <PASTE_TOKEN_ADMIN_DI_SINI>` *(Harus token admin!)*
* **Body (JSON)**:
  ```json
  {
    "status": "completed"
  }
  ```
* **Respon Sukses (200 OK)**: Mengembalikan status pesanan baru yang sudah sukses dirubah menjadi `"completed"`.
* **Screenshot File**: Simpan dengan nama `postman_update_status.png` di folder `result/`.

---

### 10. Dashboard Statistik Admin (`GET /admin/stats`)
* **URL**: `http://192.168.56.10/admin/stats`
* **Method**: `GET`
* **Headers**:
  * `Authorization: Bearer <TOKEN_ADMIN>`
* **Respon Sukses (200 OK)**: Mengembalikan ringkasan data total revenue, total users, total products, dan total orders.
* **Screenshot File**: Simpan dengan nama `postman_admin_stats.png` di folder `result/`.

---

### 11. Daftar Semua Pengguna (`GET /admin/users`)
* **URL**: `http://192.168.56.10/admin/users`
* **Method**: `GET`
* **Headers**:
  * `Authorization: Bearer <TOKEN_ADMIN>`
* **Respon Sukses (200 OK)**: Daftar akun user terdaftar di dalam sistem (kecuali password).
* **Screenshot File**: Simpan dengan nama `postman_admin_users.png` di folder `result/`.

---

### 12. Health Check System (`GET /health`)
* **URL**: `http://192.168.56.10/health`
* **Method**: `GET`
* **Respon Sukses (200 OK)**: Mengembalikan status operasional sistem dan koneksi database.
* **Screenshot File**: Simpan dengan nama `postman_health.png` di folder `result/`.

---

## C. CARA AGAR OTOMATIS MUNCUL DI LAPORAN
Setelah Anda meng-screenshot masing-masing respons pengujian di atas di Postman:
1. Simpan tangkapan layar tersebut di folder **`result/`** dengan nama file yang sesuai (misalnya: `postman_login.png`, `postman_health.png`, dsb.).
2. Saat Anda meng-push file-file tersebut ke GitHub kelompok Anda, file `README.md` laporan secara otomatis menampilkan gambar-gambar tersebut pada tabel laporan.
