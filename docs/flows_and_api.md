# Store Partnership — Dokumentasi Flow & API

Dokumen ini menjelaskan semua flow bisnis dan API yang ada di app `store_partnership`:
manajemen Store/PKS, transaksi POS per store, piutang fee (royalty/profit share),
order material antar store, ongkir, dan integrasi API untuk sistem POS eksternal.

Semua contoh nama field/doctype di bawah ini sesuai kode per commit terakhir. Kalau ada
perbedaan dengan yang Anda lihat di Desk, cek dulu `bench --site <site> migrate` sudah
dijalankan.

---

## 1. Model Data Inti

### 1.1 Store Type (`store_type`)

Master data kategori toko. Menentukan bagaimana toko itu dioperasikan dan skema bagi
hasil ke company.

| Field | Tipe | Keterangan |
|---|---|---|
| `type_code` | Data (unique, autoname) | Kode singkat, mis. `OWN`, `FRC`, `APL` |
| `type_name` | Data | Nama lengkap tipe |
| `operated_by` | Select: Company / Partner | Siapa yang menjalankan operasional toko |
| `requires_pks` | Check | Apakah tipe ini wajib punya PKS Agreement |
| `settlement_model` | Select: None / Royalty / Profit Share | Skema bagi hasil ke company |
| `fee_percentage` | Percent | **Wajib diisi** kalau `settlement_model` ≠ None. Dipakai `Store Fee Statement` untuk hitung piutang bulanan (lihat §3). |
| `default_price_list` | Link Price List | Default price list untuk Sales Order store tipe ini |
| `default_tax_rule` | Link Tax Rule | Default tax rule → resolve ke `Sales Taxes and Charges Template` |
| `is_active` | Check | |

> ⚠️ **Batasan yang perlu diketahui**: `fee_percentage` ini **satu angka per Store Type**,
> berlaku sama untuk semua store dengan tipe itu. Kalau persentase riil per store berbeda-beda
> (biasanya tercatat di `PKS Agreement.royalty_percent` / `profit_share_percent`), `Store Fee
> Statement` **belum** otomatis pakai angka per-PKS itu — masih pakai angka flat dari Store
> Type. Kalau butuh akurasi per-store, `store_fee.calculate_statement()` perlu diubah untuk
> ambil dari PKS Agreement aktif milik store tsb, bukan dari Store Type.

### 1.2 Store (`store`)

Satu baris = satu outlet/toko fisik.

| Field | Tipe | Keterangan |
|---|---|---|
| `store_name` | Data | |
| `store_type` | Link Store Type | |
| `company` | Link Company | Company pemilik toko |
| `partner` | Link Customer | Kalau toko dijalankan partner/franchisee — customer inilah yang ditagih piutang fee & ongkir |
| `warehouse` | Link Warehouse | Warehouse stock milik toko ini |
| `pos_profile` | Link POS Profile | **Wajib diisi** kalau mau pakai API `create_pos_sale` (§7.2) |
| `city` | Data | |
| `active_pks` | Link PKS Agreement (read-only) | |

### 1.3 PKS Agreement (`pks_agreement`)

Kontrak kerja sama per store, submittable (Draft → Submitted → Cancelled), berisi
`royalty_percent` / `profit_share_percent` per store, tanggal efektif, dsb. **Belum
terhubung otomatis** ke perhitungan `Store Fee Statement` (lihat catatan §1.1).

### 1.4 Store Partnership Settings (Single — menu Setting)

Konfigurasi global app ini.

| Field | Default | Keterangan |
|---|---|---|
| `store_fee_generation` | **Manual** | `Manual` = harus klik "Generate Now" tiap bulan. `Cron (Automatic Monthly)` = scheduler otomatis jalan tiap tanggal 1. |
| `fee_item` | `Store Fee` | Item yang dipakai di baris Sales Invoice piutang fee |
| `shipping_item` | `Shipping Charge` | Item yang dipakai di baris Sales Invoice ongkir |
| `last_generated_period` | (read-only) | Diisi otomatis setelah generate terakhir |

Tombol **"Generate Now"** di halaman ini memanggil generate untuk semua store yang
eligible (lihat §3), default periode bulan lalu.

---

## 2. Transaksi POS: field `store` & filter by Company/Store

**Masalah awal**: transaksi POS bisa dilihat di invoice tapi tidak bisa difilter per
company/store.

**Solusi**: custom field `store` (Link → Store) ditambahkan ke:
- `POS Invoice` — kalau site pakai doctype POS Invoice terpisah.
- `Sales Invoice` — kalau site pakai mode "Sales Invoice untuk POS" (`is_pos=1`).
  Field ini `depends_on: doc.is_pos`, jadi cuma tampil untuk transaksi POS, bukan
  sales invoice biasa.

Keduanya `in_list_view=1` dan `in_standard_filter=1` — otomatis jadi kolom di
list/report view dan muncul di panel filter standar, sejajar dengan filter Company.

**Auto-fill**: hook `validate` (`store_partnership.pos_invoice_store.set_store_from_warehouse`)
mengisi `store` otomatis dari kombinasi `set_warehouse` + `company` transaksi, dicocokkan
ke `Store.warehouse` + `Store.company`. Kalau `store` sudah diisi manual, hook ini tidak
menimpa.

> Site saat ini terkonfirmasi pakai mode **"Sales Invoice untuk POS"** (`is_pos=1`), bukan
> doctype `POS Invoice` terpisah. Semua perhitungan total penjualan (§3, §7.2) menghitung
> dari kedua sumber sekaligus supaya kompatibel di kedua mode.

---

## 3. Flow: Piutang Fee Bulanan (`Store Fee Statement`)

Menghitung & menagihkan royalty/profit-share bulanan dari store partner ke company.

### 3.1 Store yang eligible

`store_fee.get_eligible_stores()` — store yang punya `partner` terisi **dan**
`Store Type.settlement_model` ≠ `None`. Store tipe `OWN` (settlement None) otomatis
dilewati.

### 3.2 Alur generate (`store_fee.generate_store_fee_statements(from_date, to_date)`)

Untuk tiap store eligible, per periode (default: bulan kalender sebelumnya):

1. Skip kalau sudah ada `Store Fee Statement` untuk store+periode yang sama (idempotent).
2. `calculate_statement()`:
   - `total_sales` = SUM(`grand_total`) dari `POS Invoice` (submitted, bukan return) **+**
     `Sales Invoice` (`is_pos=1`, submitted, bukan return) untuk store & periode itu.
   - `fee_percentage` = `Store Type.fee_percentage` milik store itu.
   - `fee_amount` = `total_sales × fee_percentage / 100`.
   - Status → `Calculated`.
3. Kalau `fee_amount` > 0 → `create_sales_invoice_for_statement()`: buat **Sales Invoice**
   baru ke `Customer` = `Store.partner`, 1 baris item (`Store Partnership Settings.fee_item`,
   qty=1, rate=fee_amount), langsung **insert + submit**. Status Store Fee Statement →
   `Invoiced`, field `sales_invoice` terisi.

Hasilnya piutang riil, muncul normal di **Accounts Receivable / AR Aging** ERPNext
terhadap customer partner tsb.

### 3.3 Cara trigger

| Cara | Kapan jalan |
|---|---|
| Tombol **"Generate Now"** di Store Partnership Settings | Kapan saja, manual, untuk periode bebas (default bulan lalu) |
| Tombol **"Calculate"** lalu **"Create Sales Invoice"** di form `Store Fee Statement` | Per-store, satu-satu, untuk koreksi/kasus khusus |
| Scheduler bulanan (`store_partnership.tasks.monthly`) | **Hanya** kalau `Store Partnership Settings.store_fee_generation = "Cron (Automatic Monthly)"`. Kalau `Manual` (default), scheduler tidak melakukan apa-apa. |

### 3.4 Status `Store Fee Statement`

`Draft` (baru dibuat, belum dihitung) → `Calculated` (sudah dihitung, belum ditagih) →
`Invoiced` (Sales Invoice sudah dibuat & submit, tidak bisa diubah lagi).

---

## 4. Flow: Order Material Raw Material dari Store

Alur staf input Sales Order untuk store yang mau beli raw material dari company.

### 4.1 Field `store` di Sales Order

Custom field `store` (Link → Store), `in_list_view=1`, `in_standard_filter=1`.

Hook `validate` (`store_partnership.sales_order_store.apply_store_defaults`) — begitu
`store` dipilih, otomatis isi (**hanya kalau field itu masih kosong**, tidak menimpa input
manual):
- `customer` ← `Store.partner`
- `company` ← `Store.company`
- `selling_price_list` ← `Store Type.default_price_list` (kalau ada)
- `taxes_and_charges` ← resolve dari `Store Type.default_tax_rule` → `Tax Rule.sales_tax_template`

### 4.2 Field ongkir di Sales Order & auto-invoice saat Submit

Section "Ongkir (Invoice Terpisah)" di Sales Order (di bawah field `store`):

| Field | Keterangan |
|---|---|
| `shipping_amount` | Currency, opsional. Diisi kalau order ini kena biaya kirim ke store |
| `shipping_description` | Catatan ongkir, opsional |
| `store_shipping_charge` | Read-only, terisi otomatis setelah SO submit (link ke §5) |

Hook `on_submit` (`store_partnership.sales_order_store.create_invoices_on_submit`) —
begitu staf men-submit Sales Order (`store` terisi), otomatis membuat **dua Sales Invoice
terpisah sebagai Draft** (tidak langsung ke-submit — staf tetap harus cek & submit manual
dari masing-masing invoice sebelum masuk piutang):

1. **Invoice material** — dari item-item SO, lewat `make_sales_invoice()` bawaan ERPNext
   (sama seperti tombol "Create > Sales Invoice" manual), `insert()` sebagai Draft.
2. **Invoice ongkir** — hanya kalau `shipping_amount` diisi. Otomatis membuat record
   `Store Shipping Charge` baru (lihat §5) yang ter-link ke SO ini (`sales_order`), lalu
   membuat Sales Invoice-nya sebagai Draft juga (lewat
   `create_sales_invoice_for_shipping_charge(doc, submit=False)`). Nama `Store Shipping
   Charge` yang terbentuk disimpan balik ke field `store_shipping_charge` di SO.

Hasilnya: **1 Sales Order material submit → langsung ada 2 invoice Draft** — 1 untuk
barang, 1 untuk ongkir (kalau diisi) — tidak pernah digabung jadi satu invoice. Staf
tinggal buka masing-masing invoice dari Connections/`store_shipping_charge` dan submit
kalau sudah oke.

Kalau `shipping_amount` kosong saat submit, hanya invoice material yang dibuat (tidak ada
`Store Shipping Charge` yang terbentuk).

---

## 5. Flow: Ongkir (`Store Shipping Charge`)

Selain otomatis terbentuk dari Sales Order (§4.2), `Store Shipping Charge` juga bisa
diinput manual langsung (misal ongkir susulan yang tidak terkait Sales Order tertentu).

| Field | Keterangan |
|---|---|
| `store` | Wajib |
| `sales_order` | Opsional, referensi ke Sales Order material terkait (§4) — terisi otomatis kalau dibuat dari alur §4.2 |
| `customer`, `company` | Read-only, auto-isi dari `Store.partner` / `Store.company` saat `validate` |
| `amount` | Input manual biaya kirim |
| `description` | Opsional |
| `status` | `Draft` → `Invoiced` (berarti Sales Invoice sudah *dibuat*, belum tentu sudah *submit*) |
| `sales_invoice` | Read-only, terisi setelah invoice dibuat |

Tombol **"Create Sales Invoice"** di form-nya (dipakai untuk entri manual) →
`store_shipping.create_sales_invoice_for_shipping_charge(doc, submit=True)` → Sales
Invoice **baru dan terpisah** ke `Customer` = `Store.partner`, 1 baris item
(`Store Partnership Settings.shipping_item`), insert + **langsung submit**.

Untuk yang dibuat otomatis dari SO (§4.2), fungsi yang sama dipanggil dengan
`submit=False` — jadi Sales Invoice-nya **tetap Draft** sampai staf submit manual.

---

## 6. Manajemen Sesi POS (internal)

Modul `store_partnership.pos_session` — dipakai oleh `create_pos_sale` (§7.2), tidak
perlu dipanggil manual.

ERPNext mewajibkan setiap `Sales Invoice` dengan `is_pos=1` terkait ke **POS Opening
Entry** yang:
- Berstatus `Open`.
- `period_start_date` = hari ini (kalau bukan hari ini → dianggap "outdated", ERPNext
  menolak submit).
- Hanya boleh **ada satu** yang `Open` per POS Profile — kalau ada dua, ERPNext error
  "Multiple POS Opening Entry".

`get_or_open_pos_opening_entry(pos_profile, company)`:

1. Cari POS Opening Entry berstatus `Open` untuk profile itu.
2. Kalau ada 1 dan tanggalnya hari ini → dipakai langsung.
3. Kalau ada 1 tapi tanggalnya bukan hari ini (sesi kemarin yang lupa ditutup) →
   otomatis ditutup dulu pakai `make_closing_entry_from_opening()` bawaan ERPNext
   (hitung ulang total dari invoice-invoice yang sudah masuk di sesi itu, insert +
   submit POS Closing Entry), baru buka sesi baru untuk hari ini.
4. Kalau ada lebih dari 1 yang `Open` (kondisi tak terduga, mestinya tidak terjadi kalau
   selalu lewat fungsi ini) → **berhenti dengan error jelas**, minta admin selesaikan
   manual lewat Desk. Sengaja tidak auto-close banyak sekaligus tanpa pengawasan.
5. Kalau tidak ada sama sekali → buka baru, `opening_amount=0` untuk tiap payment method
   yang terdaftar di POS Profile itu.

Caller (`create_pos_sale`) **tidak perlu tahu** mekanisme ini sama sekali — cukup kirim
data penjualan.

---

## 7. API Reference

Kedua endpoint di bawah adalah method **whitelisted** Frappe — bisa dipanggil lewat REST:

```
POST /api/method/store_partnership.api.<nama_fungsi>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

API key/secret dibuat per User lewat Desk (**User** doctype → **API Access** →
**Generate Keys**). Permission mengikuti role user tsb — pastikan user API punya izin
`create` di doctype terkait (`Sales Order` / `Sales Invoice`).

### 7.1 `create_store_sales_order`

Order material (raw material) dari store ke company. Ditinggalkan sebagai **Draft**
secara default supaya staf sempat review sebelum diproses — order material tidak
otomatis "selesai" begitu API dipanggil.

**Endpoint**: `store_partnership.api.create_store_sales_order`

| Parameter | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `store` | string | ✅ | Nama Store (mis. `STR-00002`) |
| `items` | list of object (atau JSON string) | ✅ | `[{"item_code", "qty", "rate"?, "warehouse"?}]`. `warehouse` wajib untuk item stock kalau tidak ada default lain. |
| `delivery_date` | date string | — | Default: hari ini + 7 hari |
| `submit` | 0/1 | — | Default `0` (Draft). Set `1` untuk langsung submit tanpa review. |

**Return**: `{"name": "SAL-ORD-2026-00006", "docstatus": 0}`

**Auto-fill**: `customer`/`company`/`selling_price_list`/`taxes_and_charges` mengikuti
§4 (dari Store + Store Type), tidak perlu dikirim manual.

**Contoh**:
```bash
curl -X POST https://<site>/api/method/store_partnership.api.create_store_sales_order \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "store": "STR-00002",
    "items": [
      {"item_code": "PRD-A", "qty": 20, "rate": 100000, "warehouse": "Finished Goods - PDJD"}
    ]
  }'
```

**Error umum**:
- `Store {0} not found` — nama store salah.
- `At least one item is required` — `items` kosong.
- ERPNext sendiri bisa menolak dengan `Source warehouse required for stock item ...`
  kalau item stock tapi `warehouse` tidak dikirim & tidak ada default lain.

### 7.2 `create_pos_sale`

Posting transaksi POS yang **sudah closed/paid** di sistem POS store, langsung jadi
Sales Invoice **submitted** (bukan draft — transaksi dianggap sudah final & terbayar).

**Endpoint**: `store_partnership.api.create_pos_sale`

| Parameter | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `store` | string | ✅ | Nama Store. **Harus** sudah punya `pos_profile` terisi (§1.2), kalau belum → error `Store {0} has no POS Profile configured.` |
| `items` | list of object (atau JSON string) | ✅ | `[{"item_code", "qty", "rate"?, "warehouse"?}]`. `warehouse` default ke `Store.warehouse` kalau tidak dikirim. |
| `payments` | list of object (atau JSON string) | ✅ | `[{"mode_of_payment", "amount"}]`, total harus menutup `grand_total` (aturan standar ERPNext POS). |
| `customer` | string | — | Default: customer default di POS Profile store itu. |
| `posting_date` | date string | — | Default: hari ini. |
| `pos_reference` | string | — | ID transaksi dari sistem POS eksternal. Kalau dikirim dan sudah pernah dipakai sebelumnya, **tidak** buat invoice baru — langsung balikin invoice yang sudah ada (`duplicate: true`). Pakai ini supaya retry akibat network gagal tidak menghasilkan invoice dobel. |

**Return**: `{"name": "ACC-SINV-2026-00025", "docstatus": 1, "duplicate": false}`

**Contoh**:
```bash
curl -X POST https://<site>/api/method/store_partnership.api.create_pos_sale \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{
    "store": "STR-00002",
    "items": [{"item_code": "SKU001", "qty": 1, "rate": 50000}],
    "payments": [{"mode_of_payment": "Cash", "amount": 50000}],
    "pos_reference": "TRX-KEMANG-20260723-0001"
  }'
```

**Error umum**:
- `Store {0} has no POS Profile configured.` — isi dulu `Store.pos_profile`.
- `At least one payment is required` — `payments` kosong.
- `POS Profile {0} has multiple open POS Opening Entries...` — kondisi tak terduga
  (lihat §6 langkah 4), butuh penyelesaian manual sekali di Desk sebelum API bisa
  jalan lagi untuk profile itu.
- Error mandatory field ERPNext standar (mis. `Customer` kosong & POS Profile juga tidak
  punya default customer).

**Penting — idempotency**: selalu kirim `pos_reference` unik per transaksi dari sisi
POS store (mis. ID transaksi internal mereka). Tanpa ini, retry otomatis dari sistem POS
(krn timeout dsb) akan membuat Sales Invoice dobel untuk penjualan yang sama.

---

## 8. Ringkasan Custom Field yang Ditambahkan

| Doctype | Field | Tipe | Catatan |
|---|---|---|---|
| Store Type | `fee_percentage` | Percent | Native field (bukan Custom Field) |
| Store | `pos_profile` | Link POS Profile | Native field |
| POS Invoice | `store` | Link Store | Custom Field |
| Sales Invoice | `store` | Link Store | Custom Field, `depends_on: is_pos` |
| Sales Invoice | `pos_reference` | Data | Custom Field, untuk idempotency §7.2 |
| Sales Order | `store` | Link Store | Custom Field |
| Sales Order | `shipping_amount` | Currency | Custom Field, lihat §4.2 |
| Sales Order | `shipping_description` | Small Text | Custom Field, lihat §4.2 |
| Sales Order | `store_shipping_charge` | Link Store Shipping Charge | Custom Field, read-only, auto-isi saat submit §4.2 |

Semua Custom Field disinkronkan lewat patch (`bench migrate`), didefinisikan terpusat di
`store_partnership/custom_fields.py`.

---

## 9. Known Gaps / Ide Lanjutan

- **Fee percentage per-store vs per-Store-Type** (lihat §1.1) — kalau tarif riil beda per
  store, `Store Fee Statement` perlu diarahkan baca dari PKS Agreement aktif, bukan Store
  Type.
- **`create_store_sales_order` belum validasi stok** — Sales Order tidak cek ketersediaan
  stok saat insert (memang standar ERPNext, baru dicek saat Delivery Note).
- **Belum ada Customer Portal / self-service** untuk partner store order sendiri dari
  luar — API saat ini untuk dipanggil sistem eksternal (POS/ordering app milik store),
  bukan untuk diakses langsung end-user tanpa aplikasi perantara.
- **`create_pos_sale` tidak menangani retur/void** — kalau transaksi POS dibatalkan di
  sisi store setelah terlanjur ter-post, pembatalannya perlu ditangani manual di ERPNext
  (cancel Sales Invoice) atau perlu endpoint tambahan `create_pos_return`.
