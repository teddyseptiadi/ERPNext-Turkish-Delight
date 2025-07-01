// Copyright (c) 2025, Logedosoft Business Solutions and contributors
// For license information, please see license.txt

// frappe.ui.form.on("TD EInvoice Inbox", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('TD EInvoice Inbox', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button('Fatura Çek', () => {
                frappe.call({
                    method: 'erpnextturkish.td_utils.fetch_einvoices',
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint(__('İşlem tamamlandı: ') + r.message);
                        }
                    }
                });
            });
        }
    }
});
