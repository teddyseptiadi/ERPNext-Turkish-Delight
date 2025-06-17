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

frappe.ui.form.on("Sales Invoice", {
	refresh: (frm) => {
        //Get einvoice.enable settings
        var prmEInvoiceEnable = frappe.db.get_single_value("EFatura Ayarlar", "td_enable");
        Promise.all([prmEInvoiceEnable]).then(function(objResult) {
            if (objResult && objResult.length == 1 && objResult[0] === 1) {
                if (frm.doc.docstatus == 1 && !(cint(frm.doc.is_return) && frm.doc.return_against)) {
                    frm.add_custom_button(__('Gönder'),
                        function() {
                            EInvoiceProcess(frm, "Send");
                        }, __('E-Fatura'));
                    frm.add_custom_button(__('Durum Güncelle'),
                        function() {
                            EInvoiceProcess(frm, "Refresh");
                        }, __('E-Fatura'));
                    frm.page.set_inner_btn_group_as_primary(__('E-Fatura'));
                }
            }
        });
    }
});

frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Finalizer Gönder'), () => {
                frappe.call({
                    method: 'erpnextturkish.td_utils.send_invoice_to_finalizer',
                    args: { invoice_name: frm.doc.name },
                    callback(r) {
                        if (!r.exc) {
                            const msg = r.message.status === 'success'
                                ? `✅ Gönderim başarılı<br><pre>${frappe.utils.escape_html(r.message.response)}</pre>`
                                : `❌ Hata<br><pre>${frappe.utils.escape_html(r.message.error || r.message.response)}</pre>`;
                            frappe.msgprint({
                                title: __('Finalizer Yanıtı'),
                                indicator: r.message.status === 'success' ? 'green' : 'red',
                                message: msg
                            });
                        }
                    }
                });
            });
        }
    }
});