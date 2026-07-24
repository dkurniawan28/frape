import frappe
from frappe.model.document import Document


class PKSAgreement(Document):
	def on_submit(self):
		if self.status == "Draft":
			self.status = "Active"
			self.db_set("status", "Active")
		self.sync_store()
		self.create_onboarding_fee()
		self.create_starter_kit_order()

	def create_onboarding_fee(self):
		from store_partnership.store_onboarding import create_onboarding_fee_if_applicable

		create_onboarding_fee_if_applicable(self)

	def create_starter_kit_order(self):
		from store_partnership.store_package import create_starter_kit_order_if_applicable

		create_starter_kit_order_if_applicable(self)

	def on_cancel(self):
		if self.status == "Active":
			self.db_set("status", "Terminated")
		if frappe.db.get_value("Store", self.store, "active_pks") == self.name:
			frappe.db.set_value("Store", self.store, "active_pks", None)

	def sync_store(self):
		if self.status != "Active":
			return

		other_active = frappe.get_all(
			"PKS Agreement",
			filters={
				"store": self.store,
				"status": "Active",
				"docstatus": 1,
				"name": ["!=", self.name],
			},
			pluck="name",
		)
		for name in other_active:
			frappe.db.set_value("PKS Agreement", name, "status", "Expired")

		frappe.db.set_value("Store", self.store, "active_pks", self.name)
