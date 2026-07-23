custom_fields = {
	"Sales Order": [
		dict(
			fieldname="store",
			label="Store",
			fieldtype="Link",
			options="Store",
			insert_after="customer",
			in_list_view=1,
			in_standard_filter=1,
		),
	],
	"POS Invoice": [
		dict(
			fieldname="store",
			label="Store",
			fieldtype="Link",
			options="Store",
			insert_after="pos_profile",
			in_list_view=1,
			in_standard_filter=1,
			allow_on_submit=1,
		),
	],
	"Sales Invoice": [
		dict(
			fieldname="store",
			label="Store",
			fieldtype="Link",
			options="Store",
			insert_after="pos_profile",
			in_list_view=1,
			in_standard_filter=1,
			allow_on_submit=1,
			depends_on="eval:doc.is_pos",
		),
		dict(
			fieldname="pos_reference",
			label="POS Reference",
			fieldtype="Data",
			insert_after="store",
			in_standard_filter=1,
			allow_on_submit=1,
			read_only=1,
			description="External transaction id from the store's own POS system, used to make repeated API calls idempotent.",
		),
	],
}
