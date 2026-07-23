frappe.ui.form.on("Store Fee Statement", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status !== "Invoiced") {
			frm.add_custom_button(__("Calculate"), () => {
				frm.call("calculate").then(() => frm.reload_doc());
			});
		}

		if (frm.doc.status === "Calculated" && frm.doc.fee_amount) {
			frm.add_custom_button(__("Create Sales Invoice"), () => {
				frappe.confirm(
					__("This will create and submit a Sales Invoice to {0} for {1}. Continue?", [
						frm.doc.customer,
						format_currency(frm.doc.fee_amount),
					]),
					() => {
						frm.call("create_sales_invoice").then(() => frm.reload_doc());
					}
				);
			});
		}

		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("View Sales Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			});
		}
	},
});
