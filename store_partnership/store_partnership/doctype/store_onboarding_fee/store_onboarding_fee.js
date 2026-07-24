frappe.ui.form.on("Store Onboarding Fee", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Invoiced") return;

		if (frm.doc.amount) {
			frm.add_custom_button(__("Create Sales Invoice"), () => {
				frappe.confirm(
					__("This will create and submit a Sales Invoice to {0} for the {1} fee of {2}. Continue?", [
						frm.doc.customer,
						frm.doc.fee_type,
						format_currency(frm.doc.amount),
					]),
					() => {
						frm.call("create_sales_invoice").then(() => frm.reload_doc());
					}
				);
			});
		}
	},
});
