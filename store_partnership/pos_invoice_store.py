import frappe


def set_store_from_warehouse(doc, method=None):
	"""Populate the Store link from the transaction's warehouse + company so
	POS Invoice / POS Sales Invoice can be filtered by store."""
	if doc.get("store"):
		return

	warehouse = doc.get("set_warehouse")
	if not warehouse or not doc.company:
		return

	store = frappe.db.get_value("Store", {"warehouse": warehouse, "company": doc.company}, "name")
	if store:
		doc.store = store
