import frappe


def execute():
	if frappe.db.exists("Item", "Franchise Onboarding Fee"):
		return

	item_group = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"
	uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_single_value(
		"Stock Settings", "stock_uom"
	)

	item = frappe.new_doc("Item")
	item.item_code = "Franchise Onboarding Fee"
	item.item_name = "Franchise Onboarding Fee"
	item.item_group = item_group
	item.stock_uom = uom
	item.is_stock_item = 0
	item.include_item_in_manufacturing = 0
	item.is_sales_item = 1
	item.insert(ignore_permissions=True)
