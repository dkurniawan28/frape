import frappe
from frappe.utils import get_date_str, get_datetime, today


def get_or_open_pos_opening_entry(pos_profile, company, user=None):
	"""Return a POS Opening Entry for `pos_profile` that is open and dated
	today, opening a new one (and properly closing any stale one from a
	previous day) if needed. ERPNext requires exactly one open entry per
	profile, dated today, before any is_pos Sales Invoice can be submitted."""
	user = user or frappe.session.user

	open_entries = frappe.get_all(
		"POS Opening Entry",
		filters={"pos_profile": pos_profile, "status": "Open"},
		fields=["name", "period_start_date"],
		order_by="period_start_date desc",
	)

	if len(open_entries) > 1:
		frappe.throw(
			frappe._(
				"POS Profile {0} has multiple open POS Opening Entries. Please resolve this "
				"manually (close or cancel the extra ones) before more POS sales can be posted."
			).format(pos_profile)
		)

	if open_entries:
		entry = open_entries[0]
		if get_date_str(entry.period_start_date) == today():
			return entry.name
		_close_pos_opening_entry(entry.name)

	return _open_new_pos_opening_entry(pos_profile, company, user)


def _close_pos_opening_entry(opening_entry_name):
	from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
		make_closing_entry_from_opening,
	)

	opening = frappe.get_doc("POS Opening Entry", opening_entry_name)
	closing = make_closing_entry_from_opening(opening)
	closing.insert(ignore_permissions=True)
	closing.submit()


def _open_new_pos_opening_entry(pos_profile, company, user):
	profile = frappe.get_cached_doc("POS Profile", pos_profile)

	opening = frappe.new_doc("POS Opening Entry")
	opening.pos_profile = pos_profile
	opening.company = company
	opening.user = user
	opening.period_start_date = get_datetime()
	for row in profile.payments:
		opening.append("balance_details", {"mode_of_payment": row.mode_of_payment, "opening_amount": 0})
	opening.insert(ignore_permissions=True)
	opening.submit()
	return opening.name
