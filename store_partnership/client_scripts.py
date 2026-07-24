import frappe

SCRIPT_TEMPLATE = """frappe.ui.form.on("{doctype}", {{
	customer(frm) {{
		apply_store_customer_filter(frm);
	}},
	onload(frm) {{
		apply_store_customer_filter(frm);
	}},
}});

function apply_store_customer_filter(frm) {{
	if (frm.doc.customer) {{
		frm.set_query("store", () => ({{filters: {{partner: frm.doc.customer}}}}));
	}} else {{
		frm.set_query("store", () => ({{}}));
	}}
}}
"""

# A partner can run more than one store (e.g. PT Abadi Jaya Makmur has both
# Toko Bekasi and Toko Bandung), so once a Customer is picked, narrow the
# Store link to that partner's own stores only — staff can't attach the
# wrong store to a customer's transaction by mistake.
DOCTYPES = ["Sales Order", "Sales Invoice", "POS Invoice"]


def sync_store_customer_filter_scripts():
	for doctype in DOCTYPES:
		name = f"Store filter by customer - {doctype}"
		script = SCRIPT_TEMPLATE.format(doctype=doctype)
		if frappe.db.exists("Client Script", name):
			doc = frappe.get_doc("Client Script", name)
			if doc.script != script or not doc.enabled:
				doc.script = script
				doc.enabled = 1
				doc.save(ignore_permissions=True)
		else:
			doc = frappe.new_doc("Client Script")
			doc.name = name
			doc.dt = doctype
			doc.view = "Form"
			doc.enabled = 1
			doc.script = script
			doc.insert(ignore_permissions=True)
