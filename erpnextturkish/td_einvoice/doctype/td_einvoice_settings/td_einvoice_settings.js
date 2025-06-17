// Copyright (c) 2025, Logedosoft Business Solutions and contributors
// For license information, please see license.txt

// frappe.ui.form.on("TD EInvoice Settings", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('TD EInvoice Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Send XML to Finalizer'), function () {
            if (!frm.doc.finalizer_test_xml) {
                frappe.msgprint(__('Please enter XML before sending.'));
                return;
            }

            frappe.call({
                method: 'erpnextturkish.td_utils.send_custom_xml_to_finalizer',
                args: {
                    xml_string: frm.doc.finalizer_test_xml
                },
                callback: function (r) {
                    if (r.message) {
                        let result = r.message.response || r.message.error || "No response.";
                        frm.set_value('finalizer_response', result);
                        frm.refresh_field('finalizer_response');
                        frappe.msgprint("Yanıt alındı ve alana yazıldı.");
                    }
                }
            });
        });
    }
});