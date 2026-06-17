# MongoDB Dump — Order Processing Service

## Isi Dump

| Collection   | Dokumen  | Keterangan                          |
|--------------|----------|-------------------------------------|
| users        | 505      | 5 admin + 500 user biasa            |
| products     | 96       | 7 kategori produk                   |
| orders       | 10.000   | Riwayat transaksi 1 tahun terakhir  |
| audit_logs   | 2.000    | Log aksi admin                      |
| sessions     | 100      | Sample sesi aktif                   |

## Akun Default

| Role  | Email                     | Password     |
|-------|---------------------------|--------------|
| Admin | admin1@tka.its.ac.id      | Admin@12345  |
| Admin | admin2@tka.its.ac.id      | Admin@12345  |
| User  | (lihat collection users)  | User@12345   |

## Cara Restore

```bash
# Restore ke MongoDB lokal
mongorestore --drop dump/

# Restore ke MongoDB remote
mongorestore --uri="mongodb://IP:27017" --drop dump/

# Restore ke MongoDB dengan auth
mongorestore --uri="mongodb://user:pass@IP:27017" --drop dump/
```

## Re-generate Data

Jika ingin generate ulang dengan jumlah berbeda:

```bash
pip install pymongo faker tqdm bcrypt
python generate_dump.py   # output ke folder dump/
```
