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
