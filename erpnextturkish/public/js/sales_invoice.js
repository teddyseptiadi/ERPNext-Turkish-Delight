//strOperation = Send (EFatura Gonderimi), Refresh (E-Faturanin son durumunu alir)
function EInvoiceProcess(frm, strOperation) {
    let strMethod = "";
    let objArgs = {}
    
    if (strOperation == "Send") {
        strMethod = "erpnextturkish.td_utils.send_einvoice";
        objArgs = { strSalesInvoiceName: frm.docname }
    } else if (strOperation == "Refresh") {
        strMethod = "erpnextturkish.td_utils.get_invoice_status";
        objArgs = { strSaleInvoiceName: frm.docname }
    }

    frappe.call({
        method: strMethod,
        async: true,
        args: objArgs
    })
    .then((objResponse) => {
        console.log(objResponse);
        frm.reload_doc();
        if (strOperation == "Send") {
            frappe.msgprint(objResponse.message.result);
        } else if (strOperation == "Refresh") {
            frm.scroll_to_field("td_efatura_durumu");
        }
    });
}

frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (!frm.is_new()) {
            frappe.db.get_single_value('TD EInvoice Settings', 'integrator')
                .then(integrator_name => {
                    if (integrator_name) {
                        return frappe.db.get_value('TD EInvoice Integrator', integrator_name, 'td_enable');
                    }
                    return null;
                })
                .then(result => {
                    if (result?.message?.td_enable) {
                        frm.add_custom_button(__('E-Invoice'), null, __('Actions'));

                        // ⬇ Send
                        frm.add_custom_button(__('Send'), () => {
                            frappe.call({
                                method: 'erpnextturkish.td_utils.send_invoice_to_finalizer',
                                args: { invoice_name: frm.doc.name },
                                callback(r) {
                                    if (!r.exc) {
                                        const result = r.message;
                                        frappe.msgprint({
                                            title: result.status === 'success' ? __('Success') : __('Send Error'),
                                            indicator: result.status === 'success' ? 'green' : 'red',
                                            message: result.status === 'success'
                                                ? '✅ Invoice sent successfully'
                                                : `❌ ${result.error || 'Send failed'}`
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }, __('E-Invoice'));

                        // ⬇ Update Status
                        frm.add_custom_button(__('Update Status'), () => {
                            frappe.call({
                                method: 'erpnextturkish.td_utils.update_invoice_status',
                                args: { invoice_name: frm.doc.name },
                                callback(r) {
                                    if (!r.exc) {
                                        frappe.msgprint({
                                            title: __('Status Update'),
                                            indicator: 'blue',
                                            message: r.message.message || 'Status updated.'
                                        });
                                    }
                                }
                            });
                        }, __('E-Invoice'));
                    }
                });
        }
    }
});