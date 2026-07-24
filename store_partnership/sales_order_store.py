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


def create_invoices_on_submit(doc, method=None):
	"""When a store material Sales Order is submitted, immediately draft two
	separate Sales Invoices: one for the ordered materials, and — if a
	shipping amount was entered — one for the shipping cost, via a Store
	Shipping Charge record. Both are left as Draft on purpose: staff review
	and submit them from the invoice itself before they hit the store's
	receivable."""
	if not doc.get("store"):
		return

	_create_material_invoice(doc)

	if doc.get("shipping_amount"):
		_create_shipping_invoice(doc)


def _create_material_invoice(doc):
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

	si = make_sales_invoice(doc.name)
	si.insert(ignore_permissions=True)


def _create_shipping_invoice(doc):
	from store_partnership.store_shipping import create_sales_invoice_for_shipping_charge

	ssc = frappe.new_doc("Store Shipping Charge")
	ssc.store = doc.store
	ssc.sales_order = doc.name
	# Bill the same customer/company as the material invoice, even if the
	# Sales Order's customer was manually changed away from Store.partner —
	# Store Shipping Charge.validate() would otherwise silently re-derive it
	# from the Store record and the two invoices would go to different customers.
	ssc.customer = doc.customer
	ssc.company = doc.company
	ssc.amount = doc.shipping_amount
	ssc.description = doc.shipping_description
	ssc.insert(ignore_permissions=True)

	create_sales_invoice_for_shipping_charge(ssc, submit=False)
	ssc.save(ignore_permissions=True)

	doc.db_set("store_shipping_charge", ssc.name, update_modified=False)
