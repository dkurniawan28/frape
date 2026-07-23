import frappe
from frappe.model.document import Document


class StorePartnershipSettings(Document):
	@frappe.whitelist()
	def generate_now(self, from_date=None, to_date=None):
		from store_partnership.store_fee import generate_store_fee_statements

		frappe.only_for("System Manager")
		return generate_store_fee_statements(from_date=from_date, to_date=to_date)
