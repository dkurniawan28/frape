import frappe
from frappe import _
from frappe.utils import flt


def create_onboarding_fee_if_applicable(pks_doc):
	"""When a PKS Agreement is submitted, check whether it represents a
	brand-new store onboarding or an upgrade to a different Store Type for
	an existing store, and draft a one-time Store Onboarding Fee record for
	it. Renewing/renegotiating a PKS Agreement for the SAME Store Type (e.g.
	Bekasi's PKS-2026-002 replacing PKS-2024-011, both FRC) is neither —
	no fee is charged."""
	previous = frappe.get_all(
		"PKS Agreement",
		filters={
			"store": pks_doc.store,
			"docstatus": 1,
			"name": ["!=", pks_doc.name],
		},
		fields=["name", "store_type"],
		order_by="effective_date desc",
		limit=1,
	)

	if not previous:
		fee_type = "Onboarding"
	elif previous[0].store_type != pks_doc.store_type:
		fee_type = "Upgrade"
	else:
		return

	if not flt(pks_doc.fee_amount):
		return

	if frappe.db.exists("Store Onboarding Fee", {"pks_agreement": pks_doc.name}):
		return

	doc = frappe.new_doc("Store Onboarding Fee")
	doc.store = pks_doc.store
	doc.pks_agreement = pks_doc.name
	doc.fee_type = fee_type
	doc.amount = pks_doc.fee_amount
	doc.insert(ignore_permissions=True)


def create_sales_invoice_for_onboarding_fee(doc):
	"""Post a Sales Invoice for a Store Onboarding Fee. Kept as its own
	Sales Invoice, separate from the monthly royalty/profit-share (Store Fee
	Statement) and shipping invoices — this is a one-time charge, not a
	recurring one."""
	if doc.status == "Invoiced":
		frappe.throw(_("{0} is already invoiced.").format(doc.name))
	if not doc.customer:
		frappe.throw(_("Store {0} has no Partner (Customer) set.").format(doc.store))
	if not doc.amount:
		frappe.throw(_("Amount is zero, nothing to invoice."))

	settings = frappe.get_single("Store Partnership Settings")
	item_code = settings.onboarding_fee_item or "Franchise Onboarding Fee"

	description = _("{0} fee for {1} (PKS Agreement: {2})").format(
		doc.fee_type, doc.store, doc.pks_agreement
	)

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
