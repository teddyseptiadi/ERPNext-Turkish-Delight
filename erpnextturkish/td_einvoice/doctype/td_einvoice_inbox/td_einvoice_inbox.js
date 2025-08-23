// Copyright (c) 2025, Logedosoft Business Solutions and contributors
// For license information, please see license.txt

// frappe.ui.form.on("TD EInvoice Inbox", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("TD EInvoice Inbox", {
    refresh(frm) {
        // XML yükle ve tabloya ekle
        frm.add_custom_button(__('XML Yükle (Tabloya)'), () => {
            const $input = $('<input type="file" accept=".xml">');
            $input.on('change', () => {
                const file = $input[0].files[0];
                const reader = new FileReader();
                reader.onload = () => {
                    const xmlContent = reader.result;

                    frappe.call({
                        method: "erpnextturkish.td_utils.parse_xml_and_fill_table",
                        args: {
                            xml_string: xmlContent,
                            docname: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: "XML yükleniyor...",
                        callback: function () {
                            frappe.msgprint("XML'den tabloya veri eklendi.");
                            frm.reload_doc();
                        }
                    });
                };
                reader.readAsText(file);
            });
            $input.trigger('click');
        });

        // Seçilenlerden Purchase Invoice oluştur
        frm.add_custom_button(__('Seçilenlerden Gelen Fatura Oluştur'), () => {
            const selected = frm.doc.invoices_received.filter(row => row.custom_selected);
            if (selected.length === 0) {
                frappe.msgprint("Lütfen en az bir satır seçin.");
                return;
            }

            frappe.call({
                method: "erpnextturkish.td_utils.create_invoices_from_selected",
                args: {
                    rows: selected
                },
                freeze: true,
                freeze_message: "Faturalar oluşturuluyor...",
                callback: function (r) {
                    if (r.message && r.message.length) {
                        const links = r.message.map(name =>
                            `<a href="/app/purchase-invoice/${name}" target="_blank">${name}</a>`
                        ).join("<br>");
                        frappe.msgprint(`Faturalar oluşturuldu:<br>${links}`);
                    } else {
                        frappe.msgprint("Hiç fatura oluşturulamadı.");
                    }
                }
            });
        });
    }
});