import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, today


def get_eligible_stores():
	"""Stores with a partner and a fee-bearing Store Type (settlement_model != None)."""
	return frappe.db.sql(
		"""
		select s.name, s.company, s.partner, s.store_type, st.settlement_model, st.fee_percentage
		from `tabStore` s
		inner join `tabStore Type` st on st.name = s.store_type
		where ifnull(s.partner, '') != ''
			and ifnull(st.settlement_model, 'None') != 'None'
		""",
		as_dict=True,
	)


def get_previous_month_period():
	first_of_this_month = get_first_day(today())
	prev_month_date = add_months(first_of_this_month, -1)
	return get_first_day(prev_month_date), get_last_day(prev_month_date)


def compute_total_sales(store, from_date, to_date):
	"""Sum POS sales for a store in a period. Depending on site configuration,
	POS transactions live in the `POS Invoice` doctype, or (when the site uses
	"Sales Invoice for POS" mode) in `Sales Invoice` with is_pos=1 — a site only
	ever uses one of the two, so summing both is safe and covers either mode."""
	params = {"store": store, "from_date": from_date, "to_date": to_date}

	pos_invoice_total = frappe.db.sql(
		"""
		select coalesce(sum(grand_total), 0)
		from `tabPOS Invoice`
		where store = %(store)s
			and docstatus = 1
			and is_return = 0
			and posting_date between %(from_date)s and %(to_date)s
		""",
		params,
	)[0][0]

	sales_invoice_total = frappe.db.sql(
		"""
		select coalesce(sum(grand_total), 0)
		from `tabSales Invoice`
		where store = %(store)s
			and is_pos = 1
			and docstatus = 1
			and is_return = 0
			and posting_date between %(from_date)s and %(to_date)s
		""",
		params,
	)[0][0]

	return flt(pos_invoice_total) + flt(sales_invoice_total)


def calculate_statement(doc):
	"""Fill company / customer / total_sales / fee_percentage / fee_amount on a
	Store Fee Statement, based on its store, store type and date range."""
	store = frappe.get_doc("Store", doc.store)
	if not store.store_type:
		frappe.throw(_("Store {0} has no Store Type set.").format(store.name))

	fee_percentage = frappe.db.get_value("Store Type", store.store_type, "fee_percentage") or 0

	doc.company = store.company
	doc.customer = store.partner
	doc.total_sales = compute_total_sales(doc.store, doc.from_date, doc.to_date)
	doc.fee_percentage = fee_percentage
	doc.fee_amount = flt(doc.total_sales) * flt(fee_percentage) / 100
	doc.status = "Calculated"
	return doc


def create_sales_invoice_for_statement(doc):
	if doc.status == "Invoiced":
		frappe.throw(_("{0} is already invoiced.").format(doc.name))
	if not doc.customer:
		frappe.throw(_("Store {0} has no Partner (Customer) set.").format(doc.store))
	if not doc.fee_amount:
		frappe.throw(_("Fee amount is zero, nothing to invoice."))

	settings = frappe.get_single("Store Partnership Settings")
	item_code = settings.fee_item or "Store Fee"

	si = frappe.new_doc("Sales Invoice")
	si.customer = doc.customer
	si.company = doc.company
	si.append(
		"items",
		{
			"item_code": item_code,
			"qty": 1,
			"rate": doc.fee_amount,
			"description": _("Store fee for {0} ({1} - {2})").format(
				doc.store, doc.from_date, doc.to_date
			),
		},
	)
	si.insert(ignore_permissions=True)
	si.submit()

	doc.sales_invoice = si.name
	doc.status = "Invoiced"
	return si


def generate_store_fee_statements(from_date=None, to_date=None):
	"""Create (and invoice) Store Fee Statements for every eligible store for the
	given period, defaulting to last calendar month. Used by both the manual
	"Generate Now" button and the monthly cron job. Skips stores that already
	have a statement for the exact same period."""
	if not from_date or not to_date:
		from_date, to_date = get_previous_month_period()

	created = []
	for store in get_eligible_stores():
		if frappe.db.exists(
			"Store Fee Statement",
			{"store": store.name, "from_date": from_date, "to_date": to_date},
		):
			continue

		doc = frappe.new_doc("Store Fee Statement")
		doc.store = store.name
		doc.from_date = from_date
		doc.to_date = to_date
		calculate_statement(doc)
		doc.insert(ignore_permissions=True)

		if doc.fee_amount:
			create_sales_invoice_for_statement(doc)
			doc.save(ignore_permissions=True)

		created.append(doc.name)

	frappe.db.set_single_value(
		"Store Partnership Settings", "last_generated_period", f"{from_date} - {to_date}"
	)
	return created
