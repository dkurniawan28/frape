frappe.ui.form.on("Store Shipping Charge", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.status === "Invoiced") return;

		if (frm.doc.amount) {
			frm.add_custom_button(__("Create Sales Invoice"), () => {
				frappe.confirm(
					__("This will create and submit a separate Sales Invoice to {0} for the shipping cost of {1}. Continue?", [
						frm.doc.customer,
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
