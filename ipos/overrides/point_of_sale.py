import frappe
from frappe.query_builder import DocType, Order
from frappe.utils import cint
from frappe.utils.nestedset import get_root_of

from erpnext.accounts.doctype.pos_invoice.pos_invoice import (
	get_stock_availability,
)
from erpnext.selling.page.point_of_sale.point_of_sale import (
	filter_result_items,
	get_conditions,
	get_item_group_condition,
	search_by_term,
)
from erpnext.stock.get_item_details import get_conversion_factor


@frappe.whitelist()
def get_items(
	start,
	page_length,
	price_list,
	item_group,
	pos_profile,
	search_term="",
):
	warehouse, hide_unavailable_items = frappe.db.get_value(
		"POS Profile",
		pos_profile,
		["warehouse", "hide_unavailable_items"],
	)

	result = []

	# Keep ERPNext v15 barcode / serial / batch search behavior
	if search_term:
		result = search_by_term(
			search_term,
			warehouse,
			price_list,
		) or []

		# Important in v15:
		# prevent scanned/searched items outside POS Profile Item Groups
		filter_result_items(result, pos_profile)

		if result:
			return result

	# Fallback to root item group if invalid
	if not frappe.db.exists("Item Group", item_group):
		item_group = get_root_of("Item Group")

	condition = get_conditions(search_term)
	condition += get_item_group_condition(pos_profile)

	lft, rgt = frappe.db.get_value(
		"Item Group",
		item_group,
		["lft", "rgt"],
	)

	# ---------------------------------------------------------
	# CUSTOM IPOS BEHAVIOR
	# Preserve your original Item Group expansion.
	# ---------------------------------------------------------
	if cint(rgt) < 12:
		max_rgt = frappe.get_all(
			"Item Group",
			fields=["max(rgt) as max_rgt"],
		)

		if max_rgt and max_rgt[0].get("max_rgt"):
			rgt = max_rgt[0].get("max_rgt")

	# ---------------------------------------------------------
	# ERPNext v15 stock availability behavior
	# ---------------------------------------------------------
	bin_join_selection = ""
	bin_join_condition = ""

	if hide_unavailable_items:
		bin_join_selection = (
			"LEFT JOIN `tabBin` bin ON bin.item_code = item.name"
		)

		# v15 keeps non-stock items visible.
		bin_join_condition = """
			AND (
				item.is_stock_item = 0
				OR (
					item.is_stock_item = 1
					AND bin.warehouse = %(warehouse)s
					AND bin.actual_qty > 0
				)
			)
		"""

	items_data = frappe.db.sql(
		"""
		SELECT
			item.name AS item_code,
			item.item_name,
			item.description,
			item.stock_uom,
			item.image AS item_image,
			item.is_stock_item,
			item.sales_uom
		FROM
			`tabItem` item
			{bin_join_selection}
		WHERE
			item.disabled = 0
			AND item.has_variants = 0
			AND item.is_sales_item = 1
			AND item.is_fixed_asset = 0
			AND item.item_group IN (
				SELECT name
				FROM `tabItem Group`
				WHERE lft >= {lft}
				AND rgt <= {rgt}
			)
			AND {condition}
			{bin_join_condition}
		ORDER BY
			item.name ASC
		LIMIT
			{page_length}
		OFFSET
			{start}
		""".format(
			start=cint(start),
			page_length=cint(page_length),
			lft=cint(lft),
			rgt=cint(rgt),
			condition=condition,
			bin_join_selection=bin_join_selection,
			bin_join_condition=bin_join_condition,
		),
		{
			"warehouse": warehouse,
		},
		as_dict=True,
	)

	if not items_data:
		return result

	current_date = frappe.utils.today()

	ItemPrice = DocType("Item Price")

	for item in items_data:
		# v15 returns:
		# actual_qty, is_stock_item, is_negative_stock_allowed
		stock_actual_qty, _, _ = get_stock_availability(
			item.item_code,
			warehouse,
		)

		# -----------------------------------------------------
		# Use v15 Item Price validity logic.
		# -----------------------------------------------------
		item_prices = (
			frappe.qb.from_(ItemPrice)
			.select(
				ItemPrice.price_list_rate,
				ItemPrice.currency,
				ItemPrice.uom,
				ItemPrice.batch_no,
				ItemPrice.valid_from,
				ItemPrice.valid_upto,
			)
			.where(ItemPrice.price_list == price_list)
			.where(ItemPrice.item_code == item.item_code)
			.where(ItemPrice.selling == 1)
			.where(
				(ItemPrice.valid_from <= current_date)
				| (ItemPrice.valid_from.isnull())
			)
			.where(
				(ItemPrice.valid_upto >= current_date)
				| (ItemPrice.valid_upto.isnull())
			)
			.orderby(
				ItemPrice.valid_from,
				order=Order.desc,
			)
		).run(as_dict=True)

		# -----------------------------------------------------
		# No Item Price
		#
		# Follow v15 behavior by preferring Sales UOM.
		# -----------------------------------------------------
		if not item_prices:
			item_uom = item.sales_uom or item.stock_uom

			conversion_factor = (
				get_conversion_factor(
					item.item_code,
					item_uom,
				).get("conversion_factor")
				or 1
			)

			actual_qty = stock_actual_qty

			if item.stock_uom != item_uom:
				actual_qty = (
					stock_actual_qty // conversion_factor
				)

			result.append(
				{
					**item,
					"actual_qty": actual_qty,
					"price_list_rate": None,
					"currency": None,
					"uom": item_uom,
					"batch_no": None,
				}
			)

			continue

		# -----------------------------------------------------
		# CUSTOM IPOS BEHAVIOR
		#
		# ERPNext v15 normally chooses ONE price/UOM.
		#
		# Your customization creates one POS card for EACH
		# valid Item Price record.
		# -----------------------------------------------------
		for price in item_prices:
			item_uom = (
				price.get("uom")
				or item.stock_uom
			)

			conversion_factor = (
				get_conversion_factor(
					item.item_code,
					item_uom,
				).get("conversion_factor")
				or 1
			)

			actual_qty = stock_actual_qty

			if item.stock_uom != item_uom:
				actual_qty = (
					stock_actual_qty // conversion_factor
				)

			result.append(
				{
					**item,
					"actual_qty": actual_qty,
					"price_list_rate": price.get(
						"price_list_rate"
					),
					"currency": price.get("currency"),
					"uom": item_uom,
					"batch_no": price.get("batch_no"),
				}
			)

	return {
		"items": result,
	}
