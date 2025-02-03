frappe.pages["point-of-sale"].on_page_load = function (wrapper) {
    frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Point of Sale"),
        single_column: true,
    });

    frappe.require("point-of-sale.bundle.js", function () {
        erpnext.PointOfSale.Payment = class Payment extends erpnext.PointOfSale.Payment {
            constructor(pos) {
                super(pos);
                this.override_submit_order_button();

            }

            override_submit_order_button() {
                // Unbind the default event to prevent duplication
                this.$component.off("click", ".submit-order-btn");

                // Bind the custom event
                this.$component.on("click", ".submit-order-btn", () => {
                    const doc = this.events.get_frm().doc;
                    const paid_amount = doc.paid_amount;
                    const items = doc.items;
                    frappe.db.get_doc("POS Profile", cur_page.page.pos.pos_profile).then((doc) => {
                        if (doc.apply_zero_payment) {
                            if (!items.length) {
                                const message = items.length
                                    ? __("You cannot dad submit the order without payment.")
                                    : __("You cannot submit empty order.");
                                frappe.show_alert({ message, indicator: "orange" });
                                frappe.utils.play_sound("error");
                                return;
                            }
                            this.events.submit_invoice();
                        } else {
                            if (paid_amount == 0 || !items.length) {
                                const message = items.length
                                    ? __("You cannot dad submit the order without payment.")
                                    : __("You cannot submit empty order.");
                                frappe.show_alert({ message, indicator: "orange" });
                                frappe.utils.play_sound("error");
                                return;
                            
                            }
                            this.events.submit_invoice();
                        }
                    })
                    
                });

            }

            attach_cash_shortcuts(doc) {
                const grand_total = cint(frappe.sys_defaults.disable_rounded_total)
                    ? doc.grand_total
                    : doc.rounded_total;
                const currency = doc.currency;
        
                const shortcuts = this.get_cash_shortcuts(flt(grand_total));
        
                this.$payment_modes.find(".cash-shortcuts").remove();
                let shortcuts_html = shortcuts
                    .map((s) => {
                        return `<div class="shortcut" data-value="${s}">${format_currency(s, currency, 0)}</div>`;
                    })
                    .join("");
                shortcuts_html += `<div class="shortcut" data-value="${0}">${format_currency(0, currency, 0)}</div>`
                this.$payment_modes
                    .find('[data-payment-type="Cash"]')
                    .find(".mode-of-payment-control")
                    .after(`<div class="cash-shortcuts">${shortcuts_html}</div>`);
            }
            
        };
        wrapper.pos = new erpnext.PointOfSale.Controller(wrapper);
        window.cur_pos = wrapper.pos;
    });
};

