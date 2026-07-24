frappe.ui.form.on("Store", {
	store_type(frm) {
		apply_package_filter(frm);
	},
	onload(frm) {
		apply_package_filter(frm);
	},
});

function apply_package_filter(frm) {
	if (frm.doc.store_type) {
		frm.set_query("package", () => ({ filters: { store_type: frm.doc.store_type, is_active: 1 } }));
	} else {
		frm.set_query("package", () => ({ filters: { is_active: 1 } }));
	}
}
