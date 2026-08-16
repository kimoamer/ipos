frappe.pages["point-of-sale"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Point of Sale"),
        single_column: true,
    });

    frappe.require("point-of-sale.bundle.js", function () {
        erpnext.PointOfSale.Payment = class Payment extends erpnext.PointOfSale.Payment {
            constructor(args) {
                super(args);

                this.override_submit_order_button();
            }

            override_submit_order_button() {
                // Remove ERPNext's default submit handler
                this.$component.off("click", ".submit-order-btn");

                this.$component.on("click", ".submit-order-btn", async () => {
                    const frm = this.events.get_frm();
                    const doc = frm.doc;

                    const items = doc.items || [];
                    const paid_amount = flt(doc.paid_amount);

                    // Keep ERPNext v15 validation
                    if (!this.validate_reqd_invoice_fields()) {
                        return;
                    }

                    // Always prevent empty invoices
                    if (!items.length) {
                        frappe.show_alert({
                            message: __("You cannot submit empty order."),
                            indicator: "orange",
                        });

                        frappe.utils.play_sound("error");
                        return;
                    }

                    const pos_profile = await frappe.db.get_doc(
                        "POS Profile",
                        doc.pos_profile
                    );

                    const apply_zero_payment = cint(
                        pos_profile.apply_zero_payment
                    );

                    // ERPNext v15 allows zero payment when invoice
                    // has a 100% additional discount.
                    const fully_discounted =
                        flt(doc.additional_discount_percentage) === 100;

                    if (
                        !apply_zero_payment &&
                        paid_amount === 0 &&
                        !fully_discounted
                    ) {
                        frappe.show_alert({
                            message: __(
                                "You cannot submit the order without payment."
                            ),
                            indicator: "orange",
                        });

                        frappe.utils.play_sound("error");
                        return;
                    }

                    this.events.submit_invoice();
                });
            }

            attach_cash_shortcuts(doc) {
                const grand_total = cint(
                    frappe.sys_defaults.disable_rounded_total
                )
                    ? doc.grand_total
                    : doc.rounded_total;

                const currency = doc.currency;

                const shortcuts = this.get_cash_shortcuts(
                    flt(grand_total)
                );

                this.$payment_modes
                    .find(".cash-shortcuts")
                    .remove();

                let shortcuts_html = shortcuts
                    .map((value) => {
                        return `
                            <div
                                class="shortcut"
                                data-value="${value}"
                            >
                                ${format_currency(
                                    value,
                                    currency,
                                    0
                                )}
                            </div>
                        `;
                    })
                    .join("");

                // IPOS customization:
                // explicitly allow setting cash payment to zero
                shortcuts_html += `
                    <div
                        class="shortcut"
                        data-value="0"
                    >
                        ${format_currency(0, currency, 0)}
                    </div>
                `;

                this.$payment_modes
                    .find('[data-payment-type="Cash"]')
                    .find(".mode-of-payment-control")
                    .after(
                        `<div class="cash-shortcuts">
                            ${shortcuts_html}
                        </div>`
                    );
            }
        };

        wrapper.pos = new erpnext.PointOfSale.Controller(wrapper);
        window.cur_pos = wrapper.pos;
    });
};
