import frappe


def monthly():
	settings = frappe.get_single("Store Partnership Settings")
	if settings.store_fee_generation != "Cron (Automatic Monthly)":
		return

	from store_partnership.store_fee import generate_store_fee_statements

	generate_store_fee_statements()
