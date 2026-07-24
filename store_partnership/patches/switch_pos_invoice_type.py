import frappe


def execute():
	"""Point ERPNext's built-in POS screen (and this app's create_pos_sale) at
	the dedicated POS Invoice doctype instead of Sales Invoice with is_pos=1.
	Keeps raw point-of-sale transactions separate from the Sales Invoices
	that actually represent billing to a store (Store Fee Statement, Store
	Shipping Charge, Sales Order material) — those keep using Sales Invoice
	as before. Existing is_pos Sales Invoice records are left as-is; only
	new transactions are affected."""
	frappe.db.set_single_value("POS Settings", "invoice_type", "POS Invoice")
