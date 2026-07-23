frappe.ui.form.on("Store Partnership Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Generate Now"), () => {
			frappe.confirm(
				__("This will generate Store Fee Statements and post + submit Sales Invoices for last month's POS sales, for every eligible store. Continue?"),
				() => {
					frappe.call({
						method: "generate_now",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Generating store fee statements..."),
						callback: (r) => {
							frappe.msgprint(
								__("Generated {0} statement(s).", [r.message ? r.message.length : 0])
							);
							frm.reload_doc();
						},
					});
				}
			);
		});
	},
});
