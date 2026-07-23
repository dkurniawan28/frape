import frappe
from frappe import _
from frappe.utils import add_days, cint, today


@frappe.whitelist()
def create_store_sales_order(store, items, delivery_date=None, submit=0):
	"""Create a Sales Order for a store's raw-material purchase.

	Intended to be called over the REST API (e.g. POST
	/api/method/store_partnership.api.create_store_sales_order with an API
	key/secret) so a store's own POS/ordering system can raise material
	orders directly, without a staff member using the Desk UI.

	Args:
		store: name of a Store.
		items: list of {"item_code": str, "qty": number, "rate": number (optional),
			"warehouse": str (optional, required by ERPNext for stock items if
			not otherwise defaulted)}. Accepts a JSON string too (as REST calls
			will send it).
		delivery_date: optional, defaults to 7 days from today.
		submit: if truthy, submits the Sales Order immediately instead of
			leaving it as a Draft for staff to review.

	Returns:
		{"name": <Sales Order name>, "docstatus": int}
	"""
	if not frappe.has_permission("Sales Order", "create"):
		frappe.throw(_("Not permitted to create Sales Order"), frappe.PermissionError)

	if not frappe.db.exists("Store", store):
		frappe.throw(_("Store {0} not found").format(store))

	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not items:
		frappe.throw(_("At least one item is required"))

	so = frappe.new_doc("Sales Order")
	so.store = store
	so.delivery_date = delivery_date or add_days(today(), 7)

	for row in items:
		so.append(
			"items",
			{
				"item_code": row["item_code"],
				"qty": row["qty"],
				"rate": row.get("rate"),
				"warehouse": row.get("warehouse"),
				"delivery_date": so.delivery_date,
			},
		)

	so.insert()

	if cint(submit):
		so.submit()

	return {"name": so.name, "docstatus": so.docstatus}


@frappe.whitelist()
def create_pos_sale(store, items, payments, customer=None, posting_date=None, pos_reference=None):
	"""Post a completed/paid POS sale from a store's own POS system into ERPNext.

	Unlike create_store_sales_order (which leaves a Draft for staff review),
	this represents a transaction the store's POS already closed and
	collected payment for, so the resulting Sales Invoice is submitted
	immediately.

	The Store must have a POS Profile configured (Store.pos_profile). The
	underlying POS session (POS Opening Entry) that ERPNext requires is
	managed automatically: reused if already open for today, or opened
	(closing out any stale one from a previous day first) if not — callers
	don't need to know Frappe's POS session mechanics.

	Args:
		store: name of a Store.
		items: list of {"item_code", "qty", "rate" (optional), "warehouse"
			(optional, defaults to the store's warehouse)}.
		payments: list of {"mode_of_payment", "amount"} covering the total.
		customer: optional; defaults to the POS Profile's default customer.
		posting_date: optional; defaults to today.
		pos_reference: optional external transaction id. If a Sales Invoice
			was already posted with this reference, that same invoice is
			returned instead of creating a duplicate — makes retries safe.
		Both `items` and `payments` accept JSON strings too (as REST calls
		will send them).

	Returns:
		{"name": <Sales Invoice name>, "docstatus": int, "duplicate": bool}
	"""
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("Not permitted to create Sales Invoice"), frappe.PermissionError)

	store_doc = frappe.db.get_value(
		"Store", store, ["name", "company", "warehouse", "pos_profile"], as_dict=True
	)
	if not store_doc:
		frappe.throw(_("Store {0} not found").format(store))
	if not store_doc.pos_profile:
		frappe.throw(_("Store {0} has no POS Profile configured.").format(store))

	if isinstance(items, str):
		items = frappe.parse_json(items)
	if isinstance(payments, str):
		payments = frappe.parse_json(payments)
	if not items:
		frappe.throw(_("At least one item is required"))
	if not payments:
		frappe.throw(_("At least one payment is required"))

	if pos_reference:
		existing = frappe.db.get_value("Sales Invoice", {"pos_reference": pos_reference}, "name")
		if existing:
			return {
				"name": existing,
				"docstatus": frappe.db.get_value("Sales Invoice", existing, "docstatus"),
				"duplicate": True,
			}

	from store_partnership.pos_session import get_or_open_pos_opening_entry

	opening_entry = get_or_open_pos_opening_entry(store_doc.pos_profile, store_doc.company)

	si = frappe.new_doc("Sales Invoice")
	si.is_pos = 1
	si.pos_profile = store_doc.pos_profile
	si.pos_opening_entry = opening_entry
	si.company = store_doc.company
	si.customer = customer or frappe.db.get_value("POS Profile", store_doc.pos_profile, "customer")
	si.store = store_doc.name
	si.set_warehouse = store_doc.warehouse
	si.posting_date = posting_date or today()
	if pos_reference:
		si.pos_reference = pos_reference

	for row in items:
		si.append(
			"items",
			{
				"item_code": row["item_code"],
				"qty": row["qty"],
				"rate": row.get("rate"),
				"warehouse": row.get("warehouse") or store_doc.warehouse,
			},
		)

	for row in payments:
		si.append("payments", {"mode_of_payment": row["mode_of_payment"], "amount": row["amount"]})

	si.insert()
	si.submit()

	return {"name": si.name, "docstatus": si.docstatus, "duplicate": False}
