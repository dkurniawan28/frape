from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from store_partnership.custom_fields import custom_fields


def execute():
	create_custom_fields(custom_fields, update=True)
