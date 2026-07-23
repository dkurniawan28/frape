import frappe


def apply_store_defaults(doc, method=None):
	"""When a Sales Order is raised for a Store, default its customer, price
	list and tax template from that Store / its Store Type, without
	overriding anything the user already filled in manually."""
	if not doc.get("store"):
		return

	store = frappe.get_cached_doc("Store", doc.store)

	if not doc.customer and store.partner:
		doc.customer = store.partner
	if not doc.company and store.company:
		doc.company = store.company

	if not store.store_type:
		return
	store_type = frappe.get_cached_doc("Store Type", store.store_type)

	if not doc.selling_price_list and store_type.default_price_list:
		doc.selling_price_list = store_type.default_price_list

	if not doc.taxes_and_charges and store_type.default_tax_rule:
		sales_tax_template = frappe.db.get_value(
			"Tax Rule", store_type.default_tax_rule, "sales_tax_template"
		)
		if sales_tax_template:
			doc.taxes_and_charges = sales_tax_template
