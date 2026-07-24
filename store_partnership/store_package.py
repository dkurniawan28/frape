import frappe
from frappe.utils import add_days, today


def create_starter_kit_order_if_applicable(pks_doc):
	"""When a PKS Agreement is submitted, check whether the store's Package
	(location-size tier — products/layout, unrelated to Store Type/fee) is
	different from the one on its previous PKS Agreement, and draft a
	starter-kit Sales Order from that Package's included_items if so. This is
	deliberately independent from create_onboarding_fee_if_applicable(): a
	Store Type change alone never triggers this, and a Package change alone
	never triggers a Store Onboarding Fee — the two dimensions don't interact."""
	if not pks_doc.package:
		return

	previous = frappe.get_all(
		"PKS Agreement",
		filters={
			"store": pks_doc.store,
			"docstatus": 1,
			"name": ["!=", pks_doc.name],
		},
		fields=["name", "package"],
		order_by="effective_date desc",
		limit=1,
	)

	if previous and previous[0].package == pks_doc.package:
		return

	package = frappe.get_doc("Store Package", pks_doc.package)
	if not package.included_items:
		return

	store = frappe.get_cached_doc("Store", pks_doc.store)

	so = frappe.new_doc("Sales Order")
	so.store = pks_doc.store
	so.delivery_date = add_days(today(), 7)
	for row in package.included_items:
		so.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"warehouse": store.warehouse,
				"delivery_date": so.delivery_date,
			},
		)
	so.insert(ignore_permissions=True)
	return so
