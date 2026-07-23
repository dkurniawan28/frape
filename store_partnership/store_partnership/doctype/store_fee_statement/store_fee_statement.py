import frappe
from frappe import _
from frappe.model.document import Document


class StoreFeeStatement(Document):
	def validate(self):
		duplicate = frappe.db.exists(
			"Store Fee Statement",
			{
				"store": self.store,
				"from_date": self.from_date,
				"to_date": self.to_date,
				"name": ["!=", self.name],
			},
		)
		if duplicate:
			frappe.throw(
				_("A Store Fee Statement for {0} covering {1} - {2} already exists ({3}).").format(
					self.store, self.from_date, self.to_date, duplicate
				)
			)

	@frappe.whitelist()
	def calculate(self):
		from store_partnership.store_fee import calculate_statement

		calculate_statement(self)
		self.save()

	@frappe.whitelist()
	def create_sales_invoice(self):
		from store_partnership.store_fee import create_sales_invoice_for_statement

		si = create_sales_invoice_for_statement(self)
		self.save()
		return si.name
