frappe.ui.form.on('Delivery Note', {
    refresh: function(frm) {
        frm.add_custom_button(__('Send E-İrsaliye'), function() {
            frappe.call({
                method: 'erpnextturkish.td_utils.send_delivery_note_to_finalizer',
                args: {
                    delivery_note_name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message.status === 'success') {
                        frappe.msgprint(__('E-Waybill sent successfully.'));
                    } else {
                        frappe.msgprint(__('Error: ') + r.message.error);
                    }
                }
            });
        }, __('Actions'));
    }
});