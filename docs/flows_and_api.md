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
| `fee_percentage` | Percent | Rate **acuan/fallback** kalau store belum punya PKS Agreement aktif. Rate riil yang dipakai `Store Fee Statement` diambil dari PKS Agreement aktif milik store itu — lihat §3.2.1. |
| `onboarding_fee` | Currency | Base price acuan onboarding fee (store baru dengan tipe ini) — lihat §4. |
| `upgrade_fee` | Currency | Base price acuan upgrade fee (store existing pindah ke tipe ini) — lihat §4. |
| `default_price_list` | Link Price List | Default price list untuk Sales Order store tipe ini |
| `default_tax_rule` | Link Tax Rule | Default tax rule → resolve ke `Sales Taxes and Charges Template` |
| `is_active` | Check | |

Baik `fee_percentage`, `onboarding_fee`, maupun `upgrade_fee` di sini **cuma acuan/fallback** —
nominal final yang benar-benar ditagihkan selalu bisa di-override per store lewat
`PKS Agreement` (§1.3, §3.2.1, §4).

### 1.2 Store (`store`)

Satu baris = satu outlet/toko fisik.

| Field | Tipe | Keterangan |
|---|---|---|
| `store_name` | Data | |
| `store_type` | Link Store Type | |
| `company` | Link Company | Company pemilik toko |
| `partner` | Link Customer | Kalau toko dijalankan partner/franchisee — customer inilah yang ditagih piutang fee & ongkir |
| `warehouse` | Link Warehouse | Warehouse stock milik toko ini |
| `pos_profile` | Link POS Profile | **Wajib diisi** kalau mau pakai API `create_pos_sale` (§8.2) |
| `city` | Data | |
| `active_pks` | Link PKS Agreement (read-only) | |

### 1.3 PKS Agreement (`pks_agreement`)

Kontrak kerja sama per store, submittable (Draft → Active → Expired/Terminated), berisi
`royalty_percent` / `profit_share_percent` per store, tanggal efektif, `fee_amount`
(onboarding/upgrade — lihat §4), dsb. Begitu disubmit dan `status="Active"`:
- `Store.active_pks` di-set ke PKS ini, PKS aktif sebelumnya (kalau ada) otomatis jadi
  `Expired` (`sync_store()`).
- `royalty_percent`/`profit_share_percent` PKS ini yang dipakai `Store Fee Statement`
  (§3.2.1), bukan `Store Type.fee_percentage` (kecuali store belum pernah punya PKS).
- Kalau ini PKS pertama untuk store itu, atau `store_type`-nya beda dari PKS aktif
  sebelumnya, otomatis membuat `Store Onboarding Fee` (§4) kalau `fee_amount` diisi.

### 1.4 Store Partnership Settings (Single — menu Setting)

Konfigurasi global app ini.

| Field | Default | Keterangan |
|---|---|---|
| `store_fee_generation` | **Manual** | `Manual` = harus klik "Generate Now" tiap bulan. `Cron (Automatic Monthly)` = scheduler otomatis jalan tiap tanggal 1. |
| `fee_item` | `Store Fee` | Item yang dipakai di baris Sales Invoice piutang fee bulanan |
| `shipping_item` | `Shipping Charge` | Item yang dipakai di baris Sales Invoice ongkir |
| `onboarding_fee_item` | `Franchise Onboarding Fee` | Item yang dipakai di baris Sales Invoice onboarding/upgrade fee (§4) |
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

> **Update**: Site sekarang dikonfigurasi pakai doctype **`POS Invoice`** terpisah
> (`POS Settings.invoice_type = "POS Invoice"`, diubah lewat patch
> `switch_pos_invoice_type`). Sebelumnya pakai mode "Sales Invoice untuk POS"
> (`is_pos=1`) — data lama di mode itu **tidak dimigrasikan**, tetap ada sebagai
> record lama. Semua perhitungan total penjualan (§3, §8.2) tetap menghitung dari
> kedua sumber sekaligus (`POS Invoice` + `Sales Invoice` is_pos=1) supaya kompatibel
> dengan histori sebelum switch ini.
>
> **Kenapa pindah ke `POS Invoice`**: memisahkan transaksi POS mentah (operasional,
> per-penjualan) dari `Sales Invoice` yang jadi dokumen billing "resmi" ke store
> (Store Fee Statement §3, Store Shipping Charge §6, Sales Order material §5) — dua
> hal ini secara konsep beda: satu operasional/tinggi-frekuensi, satu billing/piutang.
> **Efek samping yang perlu diketahui**: `POS Invoice` memvalidasi ketersediaan stok
> lebih ketat daripada mode `is_pos` Sales Invoice sebelumnya — item stock yang
> stoknya 0 di warehouse store akan ditolak saat submit (`Item {0} has no stock in
> warehouse {1}`), bukan cuma saat Delivery Note seperti Sales Order material (§5).

### 2.1 Filter `store` berdasarkan `customer` (Sales Order, Sales Invoice, POS Invoice)

Satu partner bisa punya lebih dari satu store (mis. PT Abadi Jaya Makmur punya Toko
Bekasi *dan* Toko Bandung). Supaya staf tidak salah pilih store waktu input manual,
begitu field `customer` diisi, opsi link `store` otomatis dipersempit ke store-store
milik customer itu saja (`filters: {partner: customer}`).

Diimplementasikan sebagai **Client Script** (`store_partnership.client_scripts`,
disinkron lewat patch `sync_store_customer_filter_scripts`) — bukan file `.js` biasa,
supaya tidak butuh `bench build`/Node (environment ini tidak punya Node.js) dan tetap
ter-deploy otomatis lewat `bench migrate` seperti custom field lain. Berlaku di 3
doctype: `Sales Order`, `Sales Invoice`, `POS Invoice`.

Catatan: ini melengkapi (bukan menggantikan) `apply_store_defaults` di §5.1 yang
arahnya kebalikan — store→customer (auto-isi customer dari store yang dipilih).
Dua-duanya bisa jalan bareng: pilih customer dulu → opsi store menyempit; atau pilih
store dulu → customer ter-isi otomatis saat validate.

### 2.2 Arti field `status` di `POS Invoice`

`status` itu read-only, dihitung otomatis oleh ERPNext (`set_status()`), bukan field
yang diisi manual:

| Status | Artinya |
|---|---|
| `Draft` | Belum submit (`docstatus=0`). |
| `Submitted` | Sudah submit, tidak masuk kategori lain di bawah (jarang muncul). |
| `Unpaid` / `Overdue` | Masih ada `outstanding_amount`; `Overdue` kalau sudah lewat `due_date`. |
| `Partly Paid` | Dibayar sebagian. |
| `Paid` | `outstanding_amount = 0`, lunas penuh, **belum** ikut konsolidasi. |
| `Return` | `is_return=1` — nota retur. |
| `Credit Note Issued` | Invoice asli yang sudah ada retur terhadapnya. |
| `Consolidated` | **Sudah digabung** ke sebuah `Sales Invoice` oleh job konsolidasi POS bawaan ERPNext — lihat catatan penting di §3.2. |
| `Cancelled` | `docstatus=2`. |

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
     `Sales Invoice` (`is_pos=1`, submitted, bukan return, **`is_consolidated=0`**) untuk
     store & periode itu. Exclude `is_consolidated=1` itu penting: ERPNext punya job
     bawaan yang menggabung beberapa `POS Invoice` jadi satu `Sales Invoice`
     (`is_pos=1`, `is_consolidated=1`) — invoice hasil gabungan itu isinya total yang
     SAMA dengan POS Invoice komponennya, jadi kalau ikut dijumlah lagi dari sisi Sales
     Invoice, penjualan yang sama kehitung dua kali. Ditemukan & diperbaiki setelah
     insert dummy data lewat `create_pos_sale`: 9 dari 10 POS Invoice otomatis
     ter-konsolidasi, dan tanpa exclusion ini Store Fee Statement akan menagih store
     dua kali lipat dari penjualan asli.
   - `fee_percentage` = `get_fee_percentage()` (lihat §3.2.1) — rate kontrak riil dari
     PKS Agreement yang aktif untuk store itu, bukan rate flat Store Type.
   - `fee_amount` = `total_sales × fee_percentage / 100`.
   - Status → `Calculated`.

#### 3.2.1 Sumber `fee_percentage`: PKS Agreement aktif, bukan flat Store Type

Tiap store punya rate kontrak sendiri (`PKS Agreement.royalty_percent` untuk store
`Royalty`, `profit_share_percent` untuk `Profit Share`) yang bisa beda dari rate default
Store Type dan berubah dari waktu ke waktu (renegosiasi kontrak). `get_fee_percentage()`:

1. Kalau store punya `active_pks` (field native di `Store`, otomatis di-sync oleh
   `PKSAgreement.on_submit()` — PKS Agreement yang baru disubmit jadi `Active`, yang lama
   otomatis jadi `Expired`) → ambil `royalty_percent` atau `profit_share_percent` dari PKS
   itu (field mana yang dipakai ditentukan dari `Store Type.settlement_model`).
2. Kalau tidak ada `active_pks` sama sekali (store belum pernah punya PKS Agreement
   submitted) → fallback ke rate flat `Store Type.fee_percentage`.

Ini penting karena rate flat Store Type gampang basi begitu ada store yang
renegosiasi kontrak (kejadian nyata: Store Bekasi awalnya 12% lalu direnegosiasi jadi
10% lewat PKS-2026-002, sementara Store Type FRC tetap di rate default 9% — kalau
`fee_percentage` dihitung dari Store Type, Bekasi jadi kurang tertagih terus).
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

## 4. Flow: Onboarding & Upgrade Fee (`Store Onboarding Fee`)

Biaya **sekali bayar** per store — beda sifatnya dari fee bulanan (§3) yang recurring.
Ada dua kejadian yang kena biaya ini:

- **Onboarding**: store baru pertama kali dibuat (PKS Agreement pertama untuk store itu).
- **Upgrade**: store existing pindah tipe (mis. Franchise → Autopilot), PKS Agreement
  baru dengan `store_type` beda dari PKS aktif sebelumnya.

Perpanjangan/renegosiasi PKS dengan **Store Type yang sama** bukan keduanya — **tidak
ada fee** yang ditagih untuk kasus itu.

### 4.1 Base price vs nominal final (proses penawaran)

`Store Type.onboarding_fee` / `Store Type.upgrade_fee` (§1.1) itu **cuma harga
acuan/starting point**, bukan angka yang dipaksakan. Nominal final yang benar-benar
ditagihkan selalu diisi manual di `PKS Agreement.fee_amount` (§1.3) — hasil negosiasi,
bisa beda dari acuan tergantung kesepakatan dengan partner.

Kalau proses penawarannya formal/tertulis (bukan sekadar nego lisan), pakai fitur
bawaan ERPNext **Quotation** (module Selling) untuk mengirim penawaran resmi ke calon
partner sebelum PKS Agreement dibuat — tidak perlu integrasi khusus, item "Onboarding
Fee" tinggal dipakai di baris Quotation dengan harga awal dari `Store Type`, lalu
diedit sesuai hasil nego. `PKS Agreement.fee_amount` tetap diisi manual dengan angka
final setelah penawaran disepakati (belum ada link otomatis Quotation → PKS Agreement).

### 4.2 Trigger & alur otomatis

Hook `on_submit` (`pks_agreement.py` → `create_onboarding_fee()` →
`store_partnership.store_onboarding.create_onboarding_fee_if_applicable()`), jalan
begitu PKS Agreement disubmit, setelah `sync_store()`:

1. Cari PKS Agreement **lain** yang submitted untuk store yang sama.
2. **Tidak ada sama sekali** → `fee_type = "Onboarding"`.
3. **Ada, tapi `store_type` beda** dari PKS ini → `fee_type = "Upgrade"`.
4. **Ada, `store_type` sama** → berhenti, tidak ada fee.
5. Kalau `fee_amount` di PKS ini kosong/0 → berhenti juga (dianggap tidak ada fee /
   sengaja di-waive).
6. Cek idempotency: kalau sudah ada `Store Onboarding Fee` untuk PKS ini → skip (aman
   dipanggil berulang, mis. kalau ada retry).
7. Buat `Store Onboarding Fee` baru (Draft): `store`, `pks_agreement`, `fee_type`,
   `amount` (disalin dari `PKS Agreement.fee_amount`), `customer`/`company` (auto-isi
   dari Store saat `validate`, seperti `Store Shipping Charge`).

### 4.3 Cara pakai (panduan staf)

**Setup awal, sekali saja per Store Type** (opsional, tapi disarankan biar ada acuan):
1. Buka **Store Type** (mis. `FRC`, `APL`) → isi field **Onboarding Fee (Acuan)** dan
   **Upgrade Fee (Acuan)** → Save. Kalau dikosongkan, tidak masalah — ini cuma
   referensi harga, tidak wajib dan tidak memblokir apapun.
2. Kalau mau item Sales Invoice-nya beda dari default: buka **Store Partnership
   Settings** → ganti **Onboarding Fee Item**.

**Onboard store baru:**
1. Buat **Store** baru seperti biasa (isi `store_type`, `partner`, dll).
2. Buat **PKS Agreement** baru untuk store itu. Cek dulu harga acuan di Store Type
   (langkah setup di atas) sebagai starting point negosiasi — kalau ada proses
   penawaran formal, bisa juga bikin **Quotation** (menu Selling bawaan ERPNext)
   dulu ke calon partner sebelum PKS dibuat.
3. Isi field **Onboarding/Upgrade Fee (Nominal Final)** di PKS Agreement dengan
   angka hasil negosiasi (boleh beda dari acuan Store Type). Kosongkan/0 kalau
   memang tidak ada fee untuk kasus ini.
4. **Submit** PKS Agreement.
5. Buka menu **Store Onboarding Fee** — akan otomatis muncul record baru
   berstatus Draft, `fee_type = Onboarding`, nominal sesuai langkah 3.
6. Cek nominalnya, lalu klik tombol **"Create Sales Invoice"** di form itu. Sales
   Invoice langsung dibuat & submit ke `Store.partner`.

**Upgrade store existing** (mis. Franchise → Autopilot): langkah sama persis
seperti onboard di atas, bedanya:
1. Ubah dulu **Store.store_type** ke tipe baru (mis. `FRC` → `APL`), Save.
2. Buat **PKS Agreement** baru untuk store itu dengan tipe barunya, isi
   **Onboarding/Upgrade Fee (Nominal Final)** dengan angka upgrade (acuan: Store
   Type tipe baru → field **Upgrade Fee (Acuan)**).
3. Submit → otomatis muncul **Store Onboarding Fee** dengan `fee_type = Upgrade`.
   PKS Agreement lama otomatis jadi `Expired`.
4. Sama seperti di atas: cek, klik **"Create Sales Invoice"**.

**Perpanjangan PKS biasa** (Store Type tidak berubah): tidak ada langkah tambahan —
submit PKS Agreement seperti biasa, tidak akan muncul **Store Onboarding Fee** sama
sekali karena memang tidak ada fee onboarding/upgrade untuk kasus ini.

### 4.4 Doctype `Store Onboarding Fee`

| Field | Keterangan |
|---|---|
| `store`, `pks_agreement` | Read-only, terisi otomatis dari trigger di atas |
| `fee_type` | `Onboarding` / `Upgrade`, read-only |
| `customer`, `company` | Read-only, auto-isi dari Store |
| `amount` | Nominal yang ditagihkan |
| `status` | `Draft` → `Invoiced` |
| `sales_invoice` | Read-only, terisi setelah invoice dibuat |

Tombol **"Create Sales Invoice"** di form-nya →
`store_onboarding.create_sales_invoice_for_onboarding_fee()` → Sales Invoice baru
&amp; terpisah ke `Store.partner`, 1 baris item (`Store Partnership
Settings.onboarding_fee_item`), insert + **langsung submit**. Sama seperti Store Fee
Statement dan Store Shipping Charge, ini invoice yang **berdiri sendiri** — tidak
pernah digabung dengan invoice material/ongkir/fee bulanan.

Sudah diverifikasi 3 skenario: onboarding (PKS pertama → fee tercatat), upgrade
(ganti Store Type → fee tercatat, PKS lama otomatis Expired seperti biasa), dan
renewal (Store Type sama → tidak ada `Store Onboarding Fee` yang terbentuk sama
sekali).

### 4.5 `Store Package` — starter kit produk, **independen total dari fee**

Franchise biasanya punya paket turunan berdasarkan ukuran lokasi (mis. luas kecil vs
besar) yang menentukan produk apa saja yang dikirim & referensi layout — ini **sumbu
yang sama sekali beda** dari Store Type:

- **Store Type** → urusan **fee**: royalty/profit-share recurring (§3.2.1) + one-time
  Onboarding/Upgrade fee (§4.1-§4.4).
- **Store Package** → urusan **barang**: starter kit produk otomatis via Sales Order.
  **Tidak menyentuh fee/royalty/price list/tax rule sama sekali** — kalau cuma
  package yang berubah (Store Type tetap), tidak ada `Store Onboarding Fee` yang
  terbentuk, cuma Sales Order.

| Field `Store Package` | Keterangan |
|---|---|
| `package_code`, `package_name` | mis. "Paket Kecil", "Paket Besar" |
| `store_type` | Link Store Type — paket ini buat tipe apa; dipakai buat filter opsi Package di Store |
| `min_area_sqm` / `max_area_sqm` | Acuan luas lokasi (informasi saja, tidak divalidasi otomatis) |
| `included_items` | Child table (Item + Qty) — starter kit |
| `layout_reference` | Attachment + deskripsi |

**Store** dapat field baru `package` (Link → Store Package), difilter berdasarkan
`store_type` yang dipilih (`store.js`, pola sama seperti filter customer→store di
§2.1, tapi ini di dalam satu form yang sama).

**PKS Agreement** dapat field baru `package` — snapshot read-only, fetched dari
`store.package` (persis pola `store_type` yang sudah ada), supaya bisa dibandingkan
antar PKS.

**Trigger** (`pks_agreement.py` → `create_starter_kit_order()` →
`store_partnership.store_package.create_starter_kit_order_if_applicable()`), jalan
di `on_submit`, **independen sepenuhnya** dari pengecekan onboarding fee di §4.2:

1. Cari PKS Agreement lain yang submitted untuk store yang sama.
2. Bandingkan `package` PKS ini vs PKS sebelumnya (termasuk kasus tidak ada PKS
   sebelumnya — dianggap "beda").
3. Kalau **sama** → berhenti, tidak ada apa-apa.
4. Kalau **beda** dan `package` ini punya `included_items` → buat **Sales Order
   Draft** untuk store itu, isi item + qty dari `included_items`, `warehouse` default
   dari `Store.warehouse`. Staf review/adjust seperti alur material biasa (§5).

Matriks hasil (2 kondisi independen, store_type vs package):

| Store Type | Package | Hasil |
|---|---|---|
| Beda (pertama kali / upgrade) | Beda (pertama kali / ganti) | `Store Onboarding Fee` **+** Sales Order (kasus PKS pertama — keduanya kebetulan sama-sama "baru") |
| Beda (upgrade) | Sama | Cuma `Store Onboarding Fee` (fee_type Upgrade), **tidak ada** Sales Order baru |
| Sama | Beda (ganti package) | Cuma Sales Order, **tidak ada** fee sama sekali |
| Sama | Sama | Tidak ada keduanya — renewal murni |

Sudah diverifikasi ke-4 kombinasi di atas persis sesuai tabel.

### 4.6 Takeover jadi Store `OWN` — bukan flow baru, pakai fitur ERPNext yang sudah ada

Kejadian lain yang mirip tapi **arah pembayarannya kebalikan** (company yang bayar ke
partner, bukan partner bayar ke company) — sengaja **tidak** dibuatkan mekanisme
custom di app ini, base price-nya juga sengaja tidak dipatok (nominal buyout terlalu
variatif per kasus). Cukup 3 langkah manual pakai fitur ERPNext bawaan:

1. **Payment Entry** — `Payment Type = "Pay"`, `Party Type = "Customer"`, `Party` =
   partner store itu, nominal = hasil negosiasi buyout. Ini fitur bawaan ERPNext untuk
   "perusahaan bayar keluar ke seorang Customer", tidak butuh Supplier atau Purchase
   Invoice.
2. **Cancel PKS Agreement** aktif store itu — `on_cancel()` (§1.3) otomatis set status
   `Terminated` dan mengosongkan `Store.active_pks`, tidak perlu kode tambahan.
3. **Edit Store** manual: `store_type` → `OWN`, `partner` → dikosongkan.

---

## 5. Flow: Order Material Raw Material dari Store

Alur staf input Sales Order untuk store yang mau beli raw material dari company.

### 5.1 Field `store` di Sales Order

Custom field `store` (Link → Store), `in_list_view=1`, `in_standard_filter=1`.

Hook `validate` (`store_partnership.sales_order_store.apply_store_defaults`) — begitu
`store` dipilih, otomatis isi (**hanya kalau field itu masih kosong**, tidak menimpa input
manual):
- `customer` ← `Store.partner`
- `company` ← `Store.company`
- `selling_price_list` ← `Store Type.default_price_list` (kalau ada)
- `taxes_and_charges` ← resolve dari `Store Type.default_tax_rule` → `Tax Rule.sales_tax_template`

### 5.2 Field ongkir di Sales Order & auto-invoice saat Submit

Section "Ongkir (Invoice Terpisah)" di Sales Order (di bawah field `store`):

| Field | Keterangan |
|---|---|
| `shipping_amount` | Currency, opsional. Diisi kalau order ini kena biaya kirim ke store |
| `shipping_description` | Catatan ongkir, opsional |
| `store_shipping_charge` | Read-only, terisi otomatis setelah SO submit (link ke §6) |

Hook `on_submit` (`store_partnership.sales_order_store.create_invoices_on_submit`) —
begitu staf men-submit Sales Order (`store` terisi), otomatis membuat **dua Sales Invoice
terpisah sebagai Draft** (tidak langsung ke-submit — staf tetap harus cek & submit manual
dari masing-masing invoice sebelum masuk piutang):

1. **Invoice material** — dari item-item SO, lewat `make_sales_invoice()` bawaan ERPNext
   (sama seperti tombol "Create > Sales Invoice" manual), `insert()` sebagai Draft.
2. **Invoice ongkir** — hanya kalau `shipping_amount` diisi. Otomatis membuat record
   `Store Shipping Charge` baru (lihat §6) yang ter-link ke SO ini (`sales_order`), lalu
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

## 6. Flow: Ongkir (`Store Shipping Charge`)

Selain otomatis terbentuk dari Sales Order (§5.2), `Store Shipping Charge` juga bisa
diinput manual langsung (misal ongkir susulan yang tidak terkait Sales Order tertentu).

| Field | Keterangan |
|---|---|
| `store` | Wajib |
| `sales_order` | Opsional, referensi ke Sales Order material terkait (§5) — terisi otomatis kalau dibuat dari alur §5.2 |
| `customer`, `company` | Read-only, auto-isi dari `Store.partner` / `Store.company` saat `validate` |
| `amount` | Input manual biaya kirim |
| `description` | Opsional |
| `status` | `Draft` → `Invoiced` (berarti Sales Invoice sudah *dibuat*, belum tentu sudah *submit*) |
| `sales_invoice` | Read-only, terisi setelah invoice dibuat |

Tombol **"Create Sales Invoice"** di form-nya (dipakai untuk entri manual) →
`store_shipping.create_sales_invoice_for_shipping_charge(doc, submit=True)` → Sales
Invoice **baru dan terpisah** ke `Customer` = `Store.partner`, 1 baris item
(`Store Partnership Settings.shipping_item`), insert + **langsung submit**.

Untuk yang dibuat otomatis dari SO (§5.2), fungsi yang sama dipanggil dengan
`submit=False` — jadi Sales Invoice-nya **tetap Draft** sampai staf submit manual.

---

## 7. Manajemen Sesi POS (internal)

Modul `store_partnership.pos_session` — dipakai oleh `create_pos_sale` (§8.2), tidak
perlu dipanggil manual.

ERPNext mewajibkan setiap `POS Invoice` (atau `Sales Invoice` dengan `is_pos=1`, kalau
masih ada data lama di mode itu) terkait ke **POS Opening Entry** yang:
- Berstatus `Open`.
- `period_start_date` = hari ini (kalau bukan hari ini → dianggap "outdated", ERPNext
  menolak submit).
- Hanya boleh **ada satu** yang `Open` per POS Profile — kalau ada dua, ERPNext error
  "Multiple POS Opening Entry".
- **Hanya boleh ada satu yang `Open` per *user*, lintas SEMUA POS Profile** — batasan
  ini ternyata ada di ERPNext sendiri (`POSOpeningEntry.check_user_already_assigned`),
  bukan cuma per profile. Kalau tidak ditangani, satu API user yang melayani lebih dari
  satu store di hari yang sama akan kena error `Cashier is currently assigned to
  another POS.` begitu store kedua dipanggil.

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
5. **Tutup dulu sesi `Open` lain milik *user* yang sama tapi untuk POS Profile
   berbeda** (`_close_other_profile_sessions_for_user`) — supaya satu API user bisa
   bebas pindah-pindah melayani store berbeda tanpa kena batasan "satu cashier satu
   sesi" di atas.
6. Kalau tidak ada sama sekali → buka baru, `opening_amount=0` untuk tiap payment method
   yang terdaftar di POS Profile itu.

Caller (`create_pos_sale`) **tidak perlu tahu** mekanisme ini sama sekali — cukup kirim
data penjualan, termasuk saat berpindah store dalam satu batch pemanggilan.

---

## 8. API Reference

Kedua endpoint di bawah adalah method **whitelisted** Frappe — bisa dipanggil lewat REST:

```
POST /api/method/store_partnership.api.<nama_fungsi>
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

API key/secret dibuat per User lewat Desk (**User** doctype → **API Access** →
**Generate Keys**). Permission mengikuti role user tsb — pastikan user API punya izin
`create` di doctype terkait (`Sales Order` / `POS Invoice`).

### 8.1 `create_store_sales_order`

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
§5 (dari Store + Store Type), tidak perlu dikirim manual.

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

### 8.2 `create_pos_sale`

Posting transaksi POS yang **sudah closed/paid** di sistem POS store, langsung jadi
**POS Invoice** **submitted** (bukan draft — transaksi dianggap sudah final & terbayar).

**Endpoint**: `store_partnership.api.create_pos_sale`

| Parameter | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `store` | string | ✅ | Nama Store. **Harus** sudah punya `pos_profile` terisi (§1.2), kalau belum → error `Store {0} has no POS Profile configured.` |
| `items` | list of object (atau JSON string) | ✅ | `[{"item_code", "qty", "rate"?, "warehouse"?}]`. `warehouse` default ke `Store.warehouse` kalau tidak dikirim. |
| `payments` | list of object (atau JSON string) | ✅ | `[{"mode_of_payment", "amount"}]`, total harus menutup `grand_total` (aturan standar ERPNext POS). |
| `customer` | string | — | Default: `Store.partner` toko itu; kalau store tidak punya partner (mis. store `OWN`), fallback ke customer default di POS Profile. |
| `posting_date` | date string | — | Default: hari ini. |
| `pos_reference` | string | — | ID transaksi dari sistem POS eksternal. Kalau dikirim dan sudah pernah dipakai sebelumnya, **tidak** buat invoice baru — langsung balikin invoice yang sudah ada (`duplicate: true`). Pakai ini supaya retry akibat network gagal tidak menghasilkan invoice dobel. |

**Return**: `{"name": "ACC-PSINV-2026-00001", "docstatus": 1, "duplicate": false}` (nama
mengikuti naming series `POS Invoice`, biasanya prefix `ACC-PSINV-`).

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
  (lihat §7 langkah 4), butuh penyelesaian manual sekali di Desk sebelum API bisa
  jalan lagi untuk profile itu.
- `Item {0} has no stock in warehouse {1}` — `POS Invoice` memvalidasi stok lebih
  ketat dibanding mode `is_pos` Sales Invoice yang lama; item stock butuh saldo cukup
  di `Store.warehouse` (isi lewat Stock Reconciliation/Purchase Receipt kalau belum
  ada, atau kirim item non-stock untuk testing).
- Error mandatory field ERPNext standar (mis. `Customer` kosong & POS Profile juga tidak
  punya default customer).

**Penting — idempotency**: selalu kirim `pos_reference` unik per transaksi dari sisi
POS store (mis. ID transaksi internal mereka). Tanpa ini, retry otomatis dari sistem POS
(krn timeout dsb) akan membuat POS Invoice dobel untuk penjualan yang sama.

> Catatan: pengecekan duplikat hanya melihat apakah `pos_reference` **sudah ada**, tidak
> peduli statusnya. Kalau attempt pertama gagal di tengah jalan sebelum sempat submit
> (mis. kena error stok di atas) dan sempat ter-insert sebagai Draft, retry berikutnya
> akan dianggap "duplicate" dan mengembalikan Draft yang gagal itu apa adanya —
> **bukan** otomatis mencoba submit ulang. Kalau ini terjadi, invoice Draft yang stuck
> itu perlu diperbaiki/submit manual dulu di Desk.

---

## 9. Ringkasan Custom Field yang Ditambahkan

| Doctype | Field | Tipe | Catatan |
|---|---|---|---|
| Store Type | `fee_percentage` | Percent | Native field (bukan Custom Field) |
| Store Type | `onboarding_fee` | Currency | Native field, harga acuan onboarding — lihat §4.1 |
| Store Type | `upgrade_fee` | Currency | Native field, harga acuan upgrade — lihat §4.1 |
| Store | `pos_profile` | Link POS Profile | Native field |
| Store | `package` | Link Store Package | Native field, difilter berdasarkan store_type — lihat §4.5 |
| PKS Agreement | `fee_amount` | Currency | Native field, nominal final onboarding/upgrade fee — lihat §4.1 |
| PKS Agreement | `package` | Data (fetched, read-only) | Native field, snapshot Store.package — lihat §4.5 |
| Store Partnership Settings | `onboarding_fee_item` | Link Item | Native field, default `Franchise Onboarding Fee` |
| Store Onboarding Fee | (semua field) | — | Doctype baru, lihat §4.4 |
| Store Package | (semua field) | — | Doctype baru, lihat §4.5 |
| Store Package Item | (semua field) | — | Child table dari Store Package (item_code, qty) |
| POS Invoice | `store` | Link Store | Custom Field |
| POS Invoice | `pos_reference` | Data | Custom Field, untuk idempotency §8.2 |
| Sales Invoice | `store` | Link Store | Custom Field, `depends_on: is_pos` — dipakai kalau ada data lama dari mode `is_pos` sebelum switch ke POS Invoice |
| Sales Invoice | `pos_reference` | Data | Custom Field, idem — legacy dari mode sebelumnya |
| Sales Order | `store` | Link Store | Custom Field |
| Sales Order | `shipping_amount` | Currency | Custom Field, lihat §5.2 |
| Sales Order | `shipping_description` | Small Text | Custom Field, lihat §5.2 |
| Sales Order | `store_shipping_charge` | Link Store Shipping Charge | Custom Field, read-only, auto-isi saat submit §5.2 |

Semua Custom Field disinkronkan lewat patch (`bench migrate`), didefinisikan terpusat di
`store_partnership/custom_fields.py`.

---

## 10. Known Gaps / Ide Lanjutan

- ~~Fee percentage per-store vs per-Store-Type~~ — **sudah diperbaiki**, lihat §3.2.1.
- **`create_store_sales_order` belum validasi stok** — Sales Order tidak cek ketersediaan
  stok saat insert (memang standar ERPNext, baru dicek saat Delivery Note).
- **Belum ada Customer Portal / self-service** untuk partner store order sendiri dari
  luar — API saat ini untuk dipanggil sistem eksternal (POS/ordering app milik store),
  bukan untuk diakses langsung end-user tanpa aplikasi perantara.
- **`create_pos_sale` tidak menangani retur/void** — kalau transaksi POS dibatalkan di
  sisi store setelah terlanjur ter-post, pembatalannya perlu ditangani manual di ERPNext
  (cancel POS Invoice) atau perlu endpoint tambahan `create_pos_return`.
- **Retry setelah gagal submit bisa nyangkut sebagai Draft** (lihat catatan idempotency
  §8.2) — dedup `pos_reference` tidak membedakan Draft vs Submitted, jadi POS Invoice
  yang gagal submit (mis. kena validasi stok) akan terus dikembalikan apa adanya oleh
  retry berikutnya, bukan diperbaiki otomatis.
