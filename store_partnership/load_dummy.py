import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days

COMPANY = "PT Dedy Jaya (Demo)"


def log(msg):
	print(f"[dummy] {msg}")


def get_or_create(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name if isinstance(name, str) else frappe.get_value(doctype, filters)
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_store_type(code, name, operated_by, requires_pks, settlement_model, price_list):
	if frappe.db.exists("Store Type", code):
		log(f"Store Type {code} sudah ada, skip")
		return
	frappe.get_doc({
		"doctype": "Store Type",
		"type_code": code,
		"type_name": name,
		"operated_by": operated_by,
		"requires_pks": requires_pks,
		"settlement_model": settlement_model,
		"default_price_list": price_list,
		"is_active": 1,
	}).insert(ignore_permissions=True)
	log(f"Store Type {code} dibuat")


def ensure_customer(customer_name, customer_type, customer_group):
	if frappe.db.exists("Customer", customer_name):
		return customer_name
	doc = frappe.get_doc({
		"doctype": "Customer",
		"customer_name": customer_name,
		"customer_type": customer_type,
		"customer_group": customer_group,
		"territory": "Indonesia",
	})
	doc.insert(ignore_permissions=True)
	log(f"Customer {customer_name} dibuat")
	return doc.name


def ensure_warehouse(store_name):
	wh_name = f"{store_name} - PDJD"
	if frappe.db.exists("Warehouse", wh_name):
		return wh_name
	doc = frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": store_name,
		"company": COMPANY,
		"parent_warehouse": "All Warehouses - PDJD",
		"is_group": 0,
	})
	doc.insert(ignore_permissions=True)
	log(f"Warehouse {doc.name} dibuat")
	return doc.name


def ensure_store(store_name, store_type, partner, city):
	existing = frappe.db.exists("Store", {"store_name": store_name})
	if existing:
		return existing
	warehouse = ensure_warehouse(store_name)
	doc = frappe.get_doc({
		"doctype": "Store",
		"store_name": store_name,
		"store_type": store_type,
		"company": COMPANY,
		"partner": partner,
		"warehouse": warehouse,
		"city": city,
	})
	doc.insert(ignore_permissions=True)
	log(f"Store {doc.name} ({store_name}) dibuat")
	return doc.name


def ensure_pks(agreement_no, store, effective_date, end_date, royalty=None, profit_share=None, price_list=None):
	if frappe.db.exists("PKS Agreement", agreement_no):
		log(f"PKS {agreement_no} sudah ada, skip")
		return
	doc = frappe.get_doc({
		"doctype": "PKS Agreement",
		"agreement_no": agreement_no,
		"store": store,
		"effective_date": effective_date,
		"end_date": end_date,
		"royalty_percent": royalty,
		"profit_share_percent": profit_share,
		"price_list": price_list,
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	log(f"PKS {agreement_no} dibuat & submitted -> status {doc.status}")


def ensure_item(item_code, item_name):
	if frappe.db.exists("Item", item_code):
		return item_code
	doc = frappe.get_doc({
		"doctype": "Item",
		"item_code": item_code,
		"item_name": item_name,
		"item_group": "Demo Item Group",
		"stock_uom": "Nos",
		"is_stock_item": 0,
	})
	doc.insert(ignore_permissions=True)
	log(f"Item {item_code} dibuat")
	return item_code


def ensure_sales_invoice(customer, store, posting_date, item_code, rate):
	existing = frappe.db.exists("Sales Invoice", {
		"custom_store": store,
		"posting_date": posting_date,
		"grand_total": rate,
	})
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Sales Invoice",
		"customer": customer,
		"company": COMPANY,
		"set_posting_time": 1,
		"posting_date": posting_date,
		"due_date": add_days(posting_date, 7),
		"custom_store": store,
		"items": [{
			"item_code": item_code,
			"qty": 1,
			"rate": rate,
			"warehouse": frappe.get_value("Store", store, "warehouse"),
		}],
	})
	doc.set_missing_values()
	log(f"  debug posting_date={doc.posting_date} due_date={doc.due_date}")
	doc.insert(ignore_permissions=True)
	doc.submit()
	log(f"Sales Invoice {doc.name} ({store}, Rp {rate:,.0f}) submitted")
	return doc.name


def run():
	log("=== 1. Custom field Sales Invoice.custom_store ===")
	create_custom_fields({
		"Sales Invoice": [{
			"fieldname": "custom_store",
			"label": "Store",
			"fieldtype": "Link",
			"options": "Store",
			"insert_after": "customer",
			"in_list_view": 1,
		}]
	}, ignore_validate=True)

	log("=== 2. Price List tambahan ===")
	promo_price_list = get_or_create(
		"Price List",
		{"price_list_name": "Price List Promo Kemang"},
		{"doctype": "Price List", "price_list_name": "Price List Promo Kemang", "currency": "IDR", "selling": 1},
	)

	log("=== 3. Store Type ===")
	ensure_store_type("OWN", "Owned Store", "Company", 0, "None", "Standard Selling")
	ensure_store_type("FRC", "Franchise", "Partner", 1, "Royalty", "Standard Selling")
	ensure_store_type("APL", "Autopilot", "Company", 1, "Profit Share", "Standard Selling")

	log("=== 4. Customer (partner) ===")
	c_abadi = ensure_customer("PT Abadi Jaya Makmur", "Company", "Commercial")
	c_budi = ensure_customer("Budi Santoso", "Individual", "Individual")
	c_siti = ensure_customer("Siti Rahayu", "Individual", "Individual")
	c_modal = ensure_customer("PT Modal Investama", "Company", "Commercial")
	c_walkin = ensure_customer("Pelanggan Umum (POS)", "Individual", "Individual")

	log("=== 5. Store ===")
	str_sudirman = ensure_store("Toko Sudirman", "OWN", None, "Jakarta Pusat")
	str_kemang = ensure_store("Toko Kemang", "FRC", c_budi, "Jakarta Selatan")
	str_bekasi = ensure_store("Toko Bekasi", "FRC", c_abadi, "Bekasi")
	str_bandung = ensure_store("Toko Bandung", "APL", c_abadi, "Bandung")
	str_cibubur = ensure_store("Toko Cibubur", "APL", c_siti, "Cibubur")
	str_depok = ensure_store("Toko Depok", "APL", c_modal, "Depok")
	str_tangerang = ensure_store("Toko Tangerang", "FRC", c_modal, "Tangerang")

	log("=== 6. PKS Agreement (urut supaya histori Bekasi keliatan) ===")
	ensure_pks("PKS-2024-011", str_bekasi, "2024-06-01", "2026-01-31", royalty=12)
	ensure_pks("PKS-2026-001", str_kemang, "2025-01-01", "2027-12-31", royalty=8, price_list=promo_price_list)
	ensure_pks("PKS-2026-002", str_bekasi, "2026-02-01", "2028-01-31", royalty=10)
	ensure_pks("PKS-2026-003", str_bandung, "2025-03-01", "2028-02-29", profit_share=30)
	ensure_pks("PKS-2026-004", str_cibubur, "2025-01-15", "2027-01-14", profit_share=35)
	ensure_pks("PKS-2026-005", str_depok, "2026-01-01", "2028-12-31", profit_share=25)
	ensure_pks("PKS-2026-006", str_tangerang, "2026-02-01", "2029-01-31", royalty=9)
	frappe.db.commit()

	log("=== 7. Item katalog ===")
	ensure_item("PRD-A", "Produk A")
	ensure_item("PRD-B", "Produk B")
	ensure_item("PRD-C", "Produk C")
	ensure_item("PRD-D", "Produk D")
	ensure_item("PRD-E", "Produk E")
	frappe.db.commit()

	log("=== 8. Transaksi POS (Sales Invoice) ===")
	ensure_sales_invoice(c_walkin, str_sudirman, "2026-06-02", "PRD-A", 145000)
	ensure_sales_invoice(c_walkin, str_kemang, "2026-06-02", "PRD-B", 87500)
	ensure_sales_invoice(c_walkin, str_bekasi, "2026-06-03", "PRD-C", 210000)
	ensure_sales_invoice(c_walkin, str_bandung, "2026-06-03", "PRD-D", 45000)
	ensure_sales_invoice(c_walkin, str_cibubur, "2026-06-04", "PRD-E", 178000)
	ensure_sales_invoice(c_walkin, str_depok, "2026-06-05", "PRD-A", 92000)
	ensure_sales_invoice(c_walkin, str_tangerang, "2026-06-05", "PRD-B", 133500)
	ensure_sales_invoice(c_walkin, str_kemang, "2026-06-06", "PRD-C", 256000)
	ensure_sales_invoice(c_walkin, str_bandung, "2026-06-07", "PRD-D", 98000)
	ensure_sales_invoice(c_walkin, str_sudirman, "2026-06-07", "PRD-E", 32000)

	frappe.db.commit()
	log("=== SELESAI ===")


def link_store_to_customer():
	"""Tambah 'Connections' di form Customer -> Store & PKS Agreement.
	Insert langsung sebagai 'DocType Link' custom=1 (jalur yang sama dipakai Customize Form),
	tanpa perlu Developer Mode dan tanpa menyentuh file core Customer."""
	meta = frappe.get_meta("Customer", cached=False)
	existing = {(l.link_doctype, l.link_fieldname) for l in meta.links}
	next_idx = len(meta.links)

	to_add = []
	if ("Store", "partner") not in existing:
		to_add.append({"link_doctype": "Store", "link_fieldname": "partner"})
	if ("PKS Agreement", "partner") not in existing:
		to_add.append({"link_doctype": "PKS Agreement", "link_fieldname": "partner"})

	for i, item in enumerate(to_add):
		frappe.get_doc({
			"doctype": "DocType Link",
			"parent": "Customer",
			"parenttype": "DocType",
			"parentfield": "links",
			"idx": next_idx + i + 1,
			"group": "Store Partnership",
			"custom": 1,
			**item,
		}).insert(ignore_permissions=True)

	frappe.db.commit()
	frappe.clear_cache(doctype="Customer")

	meta = frappe.get_meta("Customer", cached=False)
	print("Customer links sekarang:", [(l.link_doctype, l.link_fieldname, l.group) for l in meta.links])


def debug_invoice():
	import erpnext.accounts.party as party_mod

	original = party_mod.validate_due_date

	def traced(posting_date, due_date, **kwargs):
		print(f"VALIDATE_DUE_DATE called with posting_date={posting_date!r} due_date={due_date!r} kwargs={kwargs}")
		return original(posting_date, due_date, **kwargs)

	party_mod.validate_due_date = traced
	try:
		doc = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "Pelanggan Umum (POS)",
			"company": "PT Dedy Jaya (Demo)",
			"posting_date": "2026-06-02",
			"due_date": "2026-06-09",
			"items": [{"item_code": "PRD-A", "qty": 1, "rate": 145000, "warehouse": frappe.get_value("Store", {"store_name": "Toko Sudirman"}, "warehouse")}],
		})
		doc.set_missing_values()
		print("after set_missing_values:", doc.posting_date, doc.due_date)
		doc.insert(ignore_permissions=True)
		print("inserted:", doc.name, doc.posting_date, doc.due_date)
	finally:
		party_mod.validate_due_date = original
