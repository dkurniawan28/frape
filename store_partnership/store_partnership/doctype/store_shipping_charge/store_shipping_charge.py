import frappe
from frappe.model.document import Document


class StoreShippingCharge(Document):
	def validate(self):
		if not self.store:
			return
		store = frappe.get_cached_doc("Store", self.store)
		if not self.customer:
			self.customer = store.partner
		if not self.company:
			self.company = store.company

	@frappe.whitelist()
	def create_sales_invoice(self):
		from store_partnership.store_shipping import create_sales_invoice_for_shipping_charge

		si = create_sales_invoice_for_shipping_charge(self)
		self.save()
		return si.name
