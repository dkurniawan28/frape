import frappe
from frappe import _


def create_sales_invoice_for_shipping_charge(doc):
	"""Post a Sales Invoice for a Store Shipping Charge. Kept as a separate
	Sales Invoice from the material order on purpose, so store partners get
	distinct invoices for goods vs. delivery cost."""
	if doc.status == "Invoiced":
		frappe.throw(_("{0} is already invoiced.").format(doc.name))
	if not doc.customer:
		frappe.throw(_("Store {0} has no Partner (Customer) set.").format(doc.store))
	if not doc.amount:
		frappe.throw(_("Amount is zero, nothing to invoice."))

	settings = frappe.get_single("Store Partnership Settings")
	item_code = settings.shipping_item or "Shipping Charge"

	description = doc.description or _("Shipping charge for {0}").format(doc.store)
	if doc.sales_order:
		description = _("{0} (Sales Order: {1})").format(description, doc.sales_order)

	si = frappe.new_doc("Sales Invoice")
	si.customer = doc.customer
	si.company = doc.company
	si.append(
		"items",
		{
			"item_code": item_code,
			"qty": 1,
			"rate": doc.amount,
			"description": description,
		},
	)
	si.insert(ignore_permissions=True)
	si.submit()

	doc.sales_invoice = si.name
	doc.status = "Invoiced"
	return si
