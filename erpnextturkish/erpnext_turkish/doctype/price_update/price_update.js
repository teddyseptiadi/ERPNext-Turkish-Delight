// Copyright (c) 2025, Logedosoft Business Solutions and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Price Update", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Price Update', {
    refresh: function(frm) {
        // 🔹 1. Şablon İndir
        frm.add_custom_button(__('Şablon İndir'), () => {
            frappe.call({
                method: "erpnextturkish.erpnext_turkish.doctype.price_update.price_update.get_price_update_template",
                callback: function(r) {
                    if (r.message) {
                        const { filename, filedata } = r.message;

                        const a = document.createElement('a');
                        a.href = filedata;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);

                        frappe.show_alert({
                            message: 'Şablon başarıyla indirildi',
                            indicator: 'green'
                        });
                    }
                }
            });
        });

        // 🔹 2. Aktarıma Başla (sol üstteki "Attach" alanından dosya bul)
        frm.add_custom_button(__('Aktarıma Başla'), () => {
            // En son eklenen dosyayı al
            frappe.db.get_list('File', {
                filters: {
                    attached_to_doctype: frm.doctype,
                    attached_to_name: frm.docname
                },
                fields: ['file_url'],
                order_by: 'creation desc',
                limit: 1
            }).then(files => {
                if (!files || files.length === 0) {
                    frappe.msgprint(__('Lütfen önce sol üstteki "Attach" alanından bir dosya ekleyin.'));
                    return;
                }

                const attachment_url = files[0].file_url;

                frappe.show_alert({
                    message: 'Fiyatlar aktarılıyor...',
                    indicator: 'blue'
                });

                frappe.call({
                    method: "erpnextturkish.erpnext_turkish.doctype.price_update.price_update.process_attachment",
                    args: {
                        docname: frm.doc.name,
                        attachment: attachment_url
                    },
                    callback: (r) => {
                        if (r.message) {
                            frappe.show_alert({
                                message: 'İşlem tamamlandı!',
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        }
                    },
                    error: (err) => {
                        frappe.msgprint({
                            title: __('Hata'),
                            message: `Dosya işlenirken hata oluştu: ${err.message}`,
                            indicator: 'red'
                        });
                    }
                });
            });
        });

        // 🔹 3. Başarı Oranı Göstergesi
        if (frm.doc.total_processed > 0) {
            const success_rate = ((frm.doc.successful_updates + frm.doc.new_prices_created) / frm.doc.total_processed * 100).toFixed(1);

            if (success_rate >= 90) {
                frm.dashboard.set_headline_alert(`<div class="alert alert-success">Başarı Oranı: ${success_rate}%</div>`);
            } else if (success_rate >= 70) {
                frm.dashboard.set_headline_alert(`<div class="alert alert-warning">Başarı Oranı: ${success_rate}%</div>`);
            } else {
                frm.dashboard.set_headline_alert(`<div class="alert alert-danger">Başarı Oranı: ${success_rate}%</div>`);
            }
        }
    },

    onload: function(frm) {
        if (frm.is_new()) {
            frm.set_value('date', frappe.datetime.get_today());
        }
    }
});