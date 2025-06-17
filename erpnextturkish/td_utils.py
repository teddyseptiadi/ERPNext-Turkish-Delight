# -*- coding: utf-8 -*-
# LOGEDOSOFT

from __future__ import unicode_literals
import frappe, json
from frappe import msgprint, _

from frappe.model.document import Document
from frappe.utils import cstr, flt, cint, nowdate, add_days, comma_and, now_datetime, ceil, today, formatdate, format_time, encode, get_time

import requests
import base64
import dateutil

from bs4 import BeautifulSoup

def sales_order_before_save(doc, method):
	#Set template item image when saving sales order. https://app.asana.com/0/1199512727558833/1208206221565431/f
	#For each row in items grid, check if item has an image. If image exist, use it or try to get the image from the template
	
	for item in doc.items:
		imgItem, template_item = frappe.db.get_value("Item", item.item_code, ["image", "variant_of"])
		if imgItem is None and template_item is not None:
			imgItem = frappe.db.get_value("Item", template_item, "image")

		if imgItem is not None:
			item.custom_ld_template_image = imgItem

		#Get size and colour attribute values https://app.asana.com/0/1199512727558833/1208206221565437/f
		if template_item is not None:
			size_attribute = frappe.db.get_value("Item", template_item, "custom_ld_size_attribute")
			if size_attribute is not None:
				docItem = frappe.get_doc("Item", item.item_code)
				for attribute in docItem.attributes:
					if attribute.attribute == size_attribute:
						item.custom_ld_variant_attribute_size = attribute.attribute_value
					else:
						item.custom_ld_variant_attribute_colour = attribute.attribute_value

def item_before_save(doc, method):
	#We need to show size chart properly in the printouts. So created a html field and we will fill it in this method.
	#Field custom_size_chart_html and custom_ld_variant_size_chart table https://app.asana.com/0/1199512727558833/1208032071430686/f
	#HTML Template:
	if len(doc.custom_ld_variant_size_chart) > 0:
		strHTML = """<table class="table table-bordered table-condensed"><thead><tr>"""
		strHTML += """<th style="width: 150px;" class="" data-fieldname="custom_ld_variant_size_chart" data-fieldtype="Table">Bedenler</th>"""

		for size in get_template_valid_attributes(doc.name)['attribute_list']:
			strHTML += """<th style="width: 80px;" class="" data-fieldname="custom_ld_variant_size_chart" data-fieldtype="Table">""" + size + """</th>"""

		strHTML += """</tr></thead><tbody>"""

		for row in doc.custom_ld_variant_size_chart:
				strHTML += """<tr>"""
				strHTML += f"""
				<td class="" data-fieldname="custom_ld_variant_size_chart" data-fieldtype="Table">
					<div class="value">{row.part}</div>
				</td>"""

				dSizeIndex = 1
				for size in get_template_valid_attributes(doc.name)['attribute_list']:
					flSize = row.get(f"attr{dSizeIndex}")
					strHTML += f"""<td class="text-right" data-fieldname="custom_ld_variant_size_chart" data-fieldtype="Table"><div class="value">{flSize}</div></td>"""
					dSizeIndex += 1

				strHTML += """</tr>"""

		strHTML += """</tbody></table>"""
			
		doc.custom_size_chart_html_editor = strHTML
		frappe.log_error("ITEM BS 10", doc.custom_size_chart_html_editor)

@frappe.whitelist()
def get_template_valid_attributes(strTemplateItemCode):
	#Will return item attribute of the given template item.
	#Algorithm: Get variant items of given template item. Loop in their attribute list.
	#If attribute name is selected in the Template Item. Size Attribute
	#Add attribute value to the result array.

	result = {
		'op_message': '',
		'op_result': True,
		'attribute_list': []
	}
	strSizeAttributeName = frappe.get_value("Item", strTemplateItemCode, "custom_ld_size_attribute")
	dctVariants = frappe.get_all("Item", filters={"variant_of": strTemplateItemCode}, fields=["name"])

	for variant in dctVariants:
		docItem = frappe.get_doc("Item", variant.name)
		for attribute in docItem.attributes:
			if attribute.attribute == strSizeAttributeName and attribute.attribute_value not in result['attribute_list']:
				result['attribute_list'].append(attribute.attribute_value)

	result['attribute_list'] = sorted(result['attribute_list'])

	return result


@frappe.whitelist()
def process_variant_json_data(strTemplateItem, jsonData):
	#We will try to find the correct item codes based on Item Template and json data
	#jsonData = [{"attribute_name":"RED","XS":0,"column_attribute_name":"Boyut","row_attribute_name":"Renk","S":0,"M":0,"L":2,"XL":0,"idx":1,"name":"row 1"},{"attribute_name":"GRE","XS":0,"column_attribute_name":"Boyut","row_attribute_name":"Renk","S":0,"M":0,"L":0,"XL":0,"idx":2,"name":"row 2"},{"attribute_name":"BLU","XS":0,"column_attribute_name":"Boyut","row_attribute_name":"Renk","S":5,"M":0,"L":0,"XL":0,"idx":3,"name":"row 3"},{"attribute_name":"BLA","XS":0,"column_attribute_name":"Boyut","row_attribute_name":"Renk","S":0,"M":0,"L":0,"XL":0,"idx":4,"name":"row 4"},{"attribute_name":"WHI","XS":0,"column_attribute_name":"Boyut","row_attribute_name":"Renk","S":0,"M":0,"L":0,"XL":0,"idx":5,"name":"row 5"}]
	#Algorithm: get attribute in info
	result = {
		'op_result': True, 'op_message': '',
		'variant_item_info': [] #{'item_code':'', 'qty':0}
	}

	item_template_info = get_item_template_attributes(strTemplateItem)

	dctVariantInfo = json.loads(jsonData)
	for variant_info in dctVariantInfo:
		docColumnAttribute = frappe.get_doc("Item Attribute", variant_info['column_attribute_name'])
		for column_attr in docColumnAttribute.item_attribute_values:
			if variant_info[column_attr.abbr] > 0:
				
				strItemCode = item_template_info['item_code_info'][0] #GOMLE
				strAttr = item_template_info['item_code_info'][1] #RENK
				if strAttr == variant_info['row_attribute_name']:
					strItemCode += "-" + variant_info['attribute_name']
				
				strItemCode += "-" + column_attr.abbr
				result['variant_item_info'].append({
					'item_code':strItemCode, 'qty':variant_info[column_attr.abbr]
				})

	return result

def get_item_code(strTemplateItem, attr1_name, attr2_name):
	#strTemplateItem = Gomlek Kodu
	 #attr1_name = BLU
	 #attr2_name = M
	  return "{}-{}-{}".format(strTemplateItem, attr1_name, attr2_name)


@frappe.whitelist()
def get_template_item_info(doc, template_data):
	#Variant selector. https://app.asana.com/0/1199512727558833/1206652223240041/f
	#We get selected values from the template data
	 #Find proper item codes
	#Return item array with item code and qty
	#The client side will process it and create new lines
	doc = frappe.get_doc(json.loads(doc))
	template_data = json.loads(template_data)
	result = False
	result_message = ""
	result_data = []

	for item in template_data:
		print(frappe.as_json(item))
		frappe.log_error("VS 0", frappe.as_json(item))

	#frappe.log_error("Hata", item)

	docTemplateItem = frappe.get_doc("Item", item["item_code"])

	return {'result': result, 'result_message': result_message, 'result_data': result_data}

def is_item_exist(attribute_info, strTemplateItem):
	blnResult = False
	print(attribute_info)
	print(strTemplateItem)
	return blnResult

@frappe.whitelist()
def get_item_template_attributes(strTemplateItemCode):
	#Variant selector. https://app.asana.com/0/1199512727558833/1206652223240041/f
	data = []#It will have arrays of attributes with attribute_name, attribute_values, attribute_abbr
	result = False
	result_message = ""
	arrItemCodeInfo = [] #Variant item code info
	
	docItem = frappe.get_doc("Item", strTemplateItemCode)
	arrItemCodeInfo.append(docItem.item_name) #Will add variant abbrv info
	for attribute in docItem.attributes:
		docItemAttribute = frappe.get_doc("Item Attribute", attribute.attribute)
		arrItemCodeInfo.append(attribute.attribute)
		attribute_info = {'attribute_name': docItemAttribute.attribute_name, 'attribute_values': [], 'attribute_abbr': []}
		data.append(attribute_info)
		for attribute_value in docItemAttribute.item_attribute_values:
			attribute_info['attribute_values'].append(attribute_value.attribute_value)
			attribute_info['attribute_abbr'].append(attribute_value.abbr)


	is_item_exist(attribute_info, strTemplateItemCode)

	#Create columns and rows list. Values with higher count should be in rows.
	if len(data) == 2:
		result = True
		if len(data[0]['attribute_values']) > len(data[1]['attribute_values']):
			columns = data[0]
			rows = data[1]
			#column_attribute_name = data[0]['attribute_name']
			#row_attribute_name = data[1]['attribute_name']
		else:
			columns = data[1]
			rows = data[0]
			#column_attribute_name = data[1]['attribute_name']
			#row_attribute_name = data[0]['attribute_name']
	else:
		result = False
		result_message = _("Template must have 2 attributes")
			
	return {
		'columns': columns, 'rows': rows, 'data': data,
		'item_code_info': arrItemCodeInfo,
		#'column_attribute_name': column_attribute_name, 'row_attribute_name': row_attribute_name,
		'op_result': result, 'op_message': result_message
	}

@frappe.whitelist()
def pp_create_wosco(docPP, strType):
	#Create WO, Subassembly WO and SCO from PP. https://app.asana.com/0/1206337061845755/1206535127766803/f
	#strType = ['Work Order', 'Subcontracting Order']
	docPP = frappe.get_doc(json.loads(docPP))

	from erpnext.manufacturing.doctype.work_order.work_order import get_default_warehouse

	wo_list, po_list = [], []
	subcontracted_po = {}
	default_warehouses = get_default_warehouse()

	if strType == "Work Order":
		docPP.make_work_order_for_finished_goods(wo_list, default_warehouses)
	if strType == "Subcontracting Order":
		docPP.make_work_order_for_subassembly_items(wo_list, subcontracted_po, default_warehouses)
		docPP.make_subcontracted_purchase_order(subcontracted_po, po_list)
	docPP.show_list_created_message("Work Order", wo_list)
	docPP.show_list_created_message("Purchase Order", po_list)

	if strType == "Work Order" and not wo_list:
		frappe.msgprint(_("No Work Orders were created!"))
	if strType == "Subcontracting Order" and not po_list:
		frappe.msgprint(_("No Subcontracting Purchase Orders were created!"))

def get_service_xml_for_uyumsoft(strType):
	strResult = ''

	if strType == 'einvoice-body':
		#<s:Header><wsse:Security s:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><wsse:UsernameToken><wsse:Username>Uyumsoft</wsse:Username><wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">Uyumsoft</wsse:Password><wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">zOBB+xvgK+JpkdzfssWwKg==</wsse:Nonce><wsu:Created>2020-02-17T21:46:40.646Z</wsu:Created></wsse:UsernameToken></wsse:Security></s:Header>
		strResult = """
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">

	<s:Header>
		<wsse:Security s:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
			<wsse:UsernameToken>
				<wsse:Username>{{docEISettings.kullaniciadi}}</wsse:Username>
				<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{{docEISettings.parola}}</wsse:Password>
			</wsse:UsernameToken>
		</wsse:Security>
	</s:Header>

	<s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
		<SaveAsDraft xmlns="http://tempuri.org/">
			<invoices>
				<InvoiceInfo LocalDocumentId="{{docSI.name}}">
					<Invoice>
						<ProfileID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TICARIFATURA</ProfileID>
						<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"/>
						<CopyIndicator xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">false</CopyIndicator>
						<IssueDate xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.posting_date_formatted}}</IssueDate>
						<IssueTime xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.posting_time_formatted}}</IssueTime>
						<InvoiceTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">SATIS</InvoiceTypeCode>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not1_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not2_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not3_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not4_formul}}</Note>
						<DocumentCurrencyCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TRY</DocumentCurrencyCode>
						<PricingCurrencyCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TRY</PricingCurrencyCode>
						<LineCountNumeric xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.line_count}}</LineCountNumeric>
						
						<AccountingSupplierParty xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<Party>
								<PartyIdentification>
									<ID schemeID="VKN" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_vergi_no if docEISettings.td_vergi_no else ''}}</ID>
								</PartyIdentification>
								<PartyIdentification>
									<ID schemeID="MERSISNO" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_mersis_no if docEISettings.td_mersis_no else ''}}</ID>
								</PartyIdentification>
								<PartyIdentification>
									<ID schemeID="TICARETSICILNO" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_ticaret_sicil_no if docEISettings.td_ticaret_sicil_no else ''}}</ID>
								</PartyIdentification>
								<PartyName>
									<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_firma_adi if docEISettings.td_firma_adi else ''}}</Name>
								</PartyName>
								<PostalAddress>
									<Room xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_kapi_no|replace("&", "&#38;") if docEISettings.td_adres_kapi_no else ''}}</Room>
									<StreetName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_sokak|replace("&", "&#38;") if docEISettings.td_adres_sokak else ''}}</StreetName>
									<BuildingNumber xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_bina_no|replace("&", "&#38;") if docEISettings.td_adres_bina_no else ''}}</BuildingNumber>
									<CitySubdivisionName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_ilce if docEISettings.td_adres_ilce else ''}}</CitySubdivisionName>
									<CityName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_il if docEISettings.td_adres_il else ''}}</CityName>
									<Country>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_ulke if docEISettings.td_adres_ulke else ''}}</Name>
									</Country>
								</PostalAddress>
								<PartyTaxScheme>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_vergi_dairesi if docEISettings.td_vergi_dairesi else ''}}</Name>
									</TaxScheme>
								</PartyTaxScheme>
							</Party>
						</AccountingSupplierParty>

						<AccountingCustomerParty xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<Party>
								<PartyIdentification>
									<ID schemeID="{{docCustomer.id_scheme}}" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.tax_id}}</ID>
								</PartyIdentification>

								<PartyName>
									<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.customer_name}}</Name>
								</PartyName>

								<PostalAddress>
									<StreetName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.address_line1|replace("&", "&#38;") if docCustomerAddress.address_line1 else ''}}</StreetName>
									<BuildingNumber xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.address_line2|replace("&", "&#38;") if docCustomerAddress.address_line2 else ''}}</BuildingNumber>
									<CitySubdivisionName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.county|replace("&", "&#38;") if docCustomerAddress.county else ''}}</CitySubdivisionName>
									<CityName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.city|replace("&", "&#38;") if docCustomerAddress.city else ''}}</CityName>
									<PostalZone xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.pincode|replace("&", "&#38;") if docCustomerAddress.pincode else ''}}</PostalZone>
									<Country>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.country or ''}}</Name>
									</Country>
								</PostalAddress>

								<PartyTaxScheme>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.tax_office or ''}}</Name>
									</TaxScheme>
								</PartyTaxScheme>

							</Party>
						</AccountingCustomerParty>

						<TaxTotal xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxAmount}}</TaxAmount>
							<TaxSubtotal>
								<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxAmount}}</TaxAmount>
								<Percent xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxPercent}}</Percent>
								<TaxCategory>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">KDV</Name>
										<TaxTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">0015</TaxTypeCode>
									</TaxScheme>
								</TaxCategory>
							</TaxSubtotal>
						</TaxTotal>

						<LegalMonetaryTotal xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<LineExtensionAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.LineExtensionAmount}}</LineExtensionAmount>
							<TaxExclusiveAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxExclusiveAmount}}</TaxExclusiveAmount>
							<TaxInclusiveAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxInclusiveAmount}}</TaxInclusiveAmount>
							<AllowanceTotalAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.AllowanceTotalAmount}}</AllowanceTotalAmount>
							<PayableAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.PayableAmount}}</PayableAmount>
						</LegalMonetaryTotal>

						{{docSI.contentLines}}

					</Invoice>
					<TargetCustomer VknTckn="{{docCustomer.tax_id}}" Alias="{{docCustomer.td_alici_alias}}" Title="{{docCustomer.customer_name}}"/>
					<EArchiveInvoiceInfo DeliveryType="Electronic"/>
					<Scenario>Automated</Scenario>
				</InvoiceInfo>
			</invoices>
		</SaveAsDraft>
	</s:Body>
</s:Envelope>
"""
	elif strType == "einvoice-line":
			strResult = """
	<InvoiceLine xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
		<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.idx}}</ID>
		<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></Note>
		
		<InvoicedQuantity unitCode="{{docCurrentLine.efatura_birimi}}" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.qty}}</InvoicedQuantity>
		<LineExtensionAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.amount}}</LineExtensionAmount>
		
		<AllowanceCharge>
			<ChargeIndicator xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">false</ChargeIndicator>
			<MultiplierFactorNumeric>0.0</MultiplierFactorNumeric>
			<Amount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.discount_amount}}</Amount>
			<PerUnitAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.qty}}</PerUnitAmount>
			<BaseAmount currencyID="TRL">{{docCurrentLine.AllowanceBaseAmount}}</BaseAmount>
		</AllowanceCharge>

		<TaxTotal>
			<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxAmount}}</TaxAmount>
			<TaxSubtotal>
				<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxAmount}}</TaxAmount>
				<Percent xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxPercent}}</Percent>
				<TaxCategory>
					<TaxScheme>
						<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">KDV</Name>
						<TaxTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">0015</TaxTypeCode>
					</TaxScheme>
				</TaxCategory>
			</TaxSubtotal>
		</TaxTotal>

		<Item>
			<Description xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></Description>
			<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docItem.item_code}} {{docItem.item_name}}</Name>
			<BrandName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></BrandName>
			<ModelName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ModelName>
			<BuyersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</BuyersItemIdentification>
			<SellersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</SellersItemIdentification>
			<ManufacturersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</ManufacturersItemIdentification>
		</Item>
		<Price>
			<PriceAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.rate}}</PriceAmount>
		</Price>
	</InvoiceLine>
		"""

	elif strType == "einvoice-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IIntegration/SaveAsDraft',
			'Connection': 'Keep-Alive'
		}
	
	elif strType == "login-test-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IIntegration/WhoAmI',
			'Connection': 'Keep-Alive'
		}
	elif strType == "login-test-body":
		strResult = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header>
	  <wsse:Security soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
		 <wsse:UsernameToken>
			<wsse:Username>{{docEISettings.kullaniciadi}}</wsse:Username>
			<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{{docEISettings.parola}}</wsse:Password>
		 </wsse:UsernameToken>
	  </wsse:Security>
   </soapenv:Header>
   <soapenv:Body>
	  <tem:WhoAmI/>
   </soapenv:Body>
</soapenv:Envelope>
"""

	elif strType == "query-invoice-status-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IIntegration/QueryOutboxInvoiceStatus',
			'Connection': 'Keep-Alive'
		}
	
	elif strType == "query-invoice-status-body":
		strResult = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header>
	  <wsse:Security soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
		 <wsse:UsernameToken>
			<wsse:Username>{{docEISettings.kullaniciadi}}</wsse:Username>
			<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{{docEISettings.parola}}</wsse:Password>
		 </wsse:UsernameToken>
	  </wsse:Security>
	</soapenv:Header>
   <soapenv:Body>
	  <tem:QueryOutboxInvoiceStatus>
		 <tem:invoiceIds>
			<tem:string>{{docSI.td_efatura_uuid}}</tem:string>
		 </tem:invoiceIds>
	  </tem:QueryOutboxInvoiceStatus>
   </soapenv:Body>
</soapenv:Envelope>
"""
	elif strType == "query-get-user-aliasses-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IIntegration/GetUserAliasses',
			'Connection': 'Keep-Alive'
		}

	elif strType == "query-get-user-aliasses-body":
		strResult = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header>
	  <wsse:Security soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
		 <wsse:UsernameToken>
			<wsse:Username>{{docEISettings.kullaniciadi}}</wsse:Username>
			<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{{docEISettings.parola}}</wsse:Password>
		 </wsse:UsernameToken>
	  </wsse:Security>
	</soapenv:Header>
   <soapenv:Body>
	  <tem:GetUserAliasses>
		 <tem:vknTckn>{{docCustomer.tax_id}}</tem:vknTckn>
	  </tem:GetUserAliasses>
   </soapenv:Body>
</soapenv:Envelope>
		"""

	return strResult

def get_service_xml_for_bien_teknoloji(strType):
	strResult = ''

	if strType == "inbox-invoice-list-body": 
		#<tem:StatusInList>WaitingForAprovement</tem:StatusInList>
		strResult = """
		<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
			<soapenv:Body>
				<tem:GetInboxInvoiceList>
					<tem:userInfo Username="{{docEISettings.username}}" Password="{{docEISettings.parola}}"/>
					<tem:query PageIndex="1" PageSize="100000">
						<tem:ExecutionStartDate>{{tarih1}}</tem:ExecutionStartDate>
						<tem:ExecutionEndDate>{{tarih2}}</tem:ExecutionEndDate>
						<tem:StatusNotInList>Declined</tem:StatusNotInList>
					</tem:query>
				</tem:GetInboxInvoiceList>
			</soapenv:Body>
		</soapenv:Envelope> 
			"""

	elif strType == "einvoice-tevkifat":
		strResult = """
<WithholdingTaxTotal>
	<TaxAmount currencyID="TRY">{{kdv_tevkifat1}}</TaxAmount>
	<TaxSubtotal>
		<TaxableAmount currencyID="TRY">{{kdv_tam}}</TaxableAmount>
		<TaxAmount currencyID="TRY">{{kdv_tevkifat2}}</TaxAmount>
		<Percent>50</Percent>
		<TaxCategory>
			<TaxScheme>
				<Name>604 YEMEK SERVİS HİZMETİ *GT 117-Bölüm (3.2.4)+</Name>
				<TaxTypeCode>604</TaxTypeCode>
			</TaxScheme>
		</TaxCategory>
	</TaxSubtotal>
</WithholdingTaxTotal>
					"""

	elif strType == 'einvoice-body':
		#<s:Header><wsse:Security s:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"><wsse:UsernameToken><wsse:Username>Uyumsoft</wsse:Username><wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">Uyumsoft</wsse:Password><wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">zOBB+xvgK+JpkdzfssWwKg==</wsse:Nonce><wsu:Created>2020-02-17T21:46:40.646Z</wsu:Created></wsse:UsernameToken></wsse:Security></s:Header>
		strResult = """
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">

	<s:Header>
		<wsse:Security s:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd" xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
			<wsse:UsernameToken>
				<wsse:Username>{{docEISettings.kullaniciadi}}</wsse:Username>
				<wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{{docEISettings.parola}}</wsse:Password>
			</wsse:UsernameToken>
		</wsse:Security>
	</s:Header>

	<s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
		<SaveAsDraft xmlns="http://tempuri.org/">
			<invoices>
				<InvoiceInfo LocalDocumentId="{{docSI.name}}">
					<Invoice>
						<ProfileID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TICARIFATURA</ProfileID>
						<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"/>
						<CopyIndicator xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">false</CopyIndicator>
						<IssueDate xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.posting_date_formatted}}</IssueDate>
						<IssueTime xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.posting_time_formatted}}</IssueTime>
						<InvoiceTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">SATIS</InvoiceTypeCode>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not1_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not2_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not3_formul}}</Note>
						<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_not4_formul}}</Note>
						<DocumentCurrencyCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TRY</DocumentCurrencyCode>
						<PricingCurrencyCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">TRY</PricingCurrencyCode>
						<LineCountNumeric xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.line_count}}</LineCountNumeric>
						
						<AccountingSupplierParty xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<Party>
								<PartyIdentification>
									<ID schemeID="VKN" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_vergi_no if docEISettings.td_vergi_no else ''}}</ID>
								</PartyIdentification>
								<PartyIdentification>
									<ID schemeID="MERSISNO" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_mersis_no if docEISettings.td_mersis_no else ''}}</ID>
								</PartyIdentification>
								<PartyIdentification>
									<ID schemeID="TICARETSICILNO" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_ticaret_sicil_no if docEISettings.td_ticaret_sicil_no else ''}}</ID>
								</PartyIdentification>
								<PartyName>
									<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_firma_adi if docEISettings.td_firma_adi else ''}}</Name>
								</PartyName>
								<PostalAddress>
									<Room xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_kapi_no|replace("&", "&#38;") if docEISettings.td_adres_kapi_no else ''}}</Room>
									<StreetName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_sokak|replace("&", "&#38;") if docEISettings.td_adres_sokak else ''}}</StreetName>
									<BuildingNumber xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_bina_no|replace("&", "&#38;") if docEISettings.td_adres_bina_no else ''}}</BuildingNumber>
									<CitySubdivisionName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_ilce if docEISettings.td_adres_ilce else ''}}</CitySubdivisionName>
									<CityName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_il if docEISettings.td_adres_il else ''}}</CityName>
									<Country>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_adres_ulke if docEISettings.td_adres_ulke else ''}}</Name>
									</Country>
								</PostalAddress>
								<PartyTaxScheme>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docEISettings.td_vergi_dairesi if docEISettings.td_vergi_dairesi else ''}}</Name>
									</TaxScheme>
								</PartyTaxScheme>
							</Party>
						</AccountingSupplierParty>

						<AccountingCustomerParty xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<Party>
								<PartyIdentification>
									<ID schemeID="{{docCustomer.id_scheme}}" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.tax_id}}</ID>
								</PartyIdentification>

								<PartyName>
									<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.customer_name}}</Name>
								</PartyName>

								<PostalAddress>
									<StreetName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.address_line1|replace("&", "&#38;") if docCustomerAddress.address_line1 else ''}}</StreetName>
									<BuildingNumber xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.address_line2|replace("&", "&#38;") if docCustomerAddress.address_line2 else ''}}</BuildingNumber>
									<CitySubdivisionName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.county|replace("&", "&#38;") if docCustomerAddress.county else ''}}</CitySubdivisionName>
									<CityName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.city|replace("&", "&#38;") if docCustomerAddress.city else ''}}</CityName>
									<PostalZone xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.pincode|replace("&", "&#38;") if docCustomerAddress.pincode else ''}}</PostalZone>
									<Country>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomerAddress.country or ''}}</Name>
									</Country>
								</PostalAddress>

								<PartyTaxScheme>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCustomer.tax_office or ''}}</Name>
									</TaxScheme>
								</PartyTaxScheme>

							</Party>
						</AccountingCustomerParty>

						<TaxTotal xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxAmount}}</TaxAmount>
							<TaxSubtotal>
								<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxAmount}}</TaxAmount>
								<Percent xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxPercent}}</Percent>
								<TaxCategory>
									<TaxScheme>
										<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">KDV</Name>
										<TaxTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">0015</TaxTypeCode>
									</TaxScheme>
								</TaxCategory>
							</TaxSubtotal>
						</TaxTotal>

						<LegalMonetaryTotal xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
							<LineExtensionAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.LineExtensionAmount}}</LineExtensionAmount>
							<TaxExclusiveAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxExclusiveAmount}}</TaxExclusiveAmount>
							<TaxInclusiveAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.TaxInclusiveAmount}}</TaxInclusiveAmount>
							<AllowanceTotalAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.AllowanceTotalAmount}}</AllowanceTotalAmount>
							<PayableAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docSI.PayableAmount}}</PayableAmount>
						</LegalMonetaryTotal>

						{{docSI.contentLines}}

					</Invoice>
					<TargetCustomer VknTckn="{{docCustomer.tax_id}}" Alias="{{docCustomer.td_alici_alias}}" Title="{{docCustomer.customer_name}}"/>
					<EArchiveInvoiceInfo DeliveryType="Electronic"/>
					<Scenario>Automated</Scenario>
				</InvoiceInfo>
			</invoices>
		</SaveAsDraft>
	</s:Body>
</s:Envelope>
"""

	elif strType == "einvoice-line":
			strResult = """
	<InvoiceLine xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
		<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.idx}}</ID>
		<Note xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></Note>
		
		<InvoicedQuantity unitCode="{{docCurrentLine.efatura_birimi}}" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.qty}}</InvoicedQuantity>
		<LineExtensionAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.amount}}</LineExtensionAmount>
		
		<AllowanceCharge>
			<ChargeIndicator xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">false</ChargeIndicator>
			<MultiplierFactorNumeric>0.0</MultiplierFactorNumeric>
			<Amount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.discount_amount}}</Amount>
			<PerUnitAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.qty}}</PerUnitAmount>
			<BaseAmount currencyID="TRL">{{docCurrentLine.AllowanceBaseAmount}}</BaseAmount>
		</AllowanceCharge>

		<TaxTotal>
			<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxAmount}}</TaxAmount>
			<TaxSubtotal>
				<TaxAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxAmount}}</TaxAmount>
				<Percent xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.TaxPercent}}</Percent>
				<TaxCategory>
					<TaxScheme>
						<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">KDV</Name>
						<TaxTypeCode xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">0015</TaxTypeCode>
					</TaxScheme>
				</TaxCategory>
			</TaxSubtotal>
		</TaxTotal>

		<Item>
			<Description xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></Description>
			<Name xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docItem.item_code}} {{docItem.item_name}}</Name>
			<BrandName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></BrandName>
			<ModelName xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ModelName>
			<BuyersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</BuyersItemIdentification>
			<SellersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</SellersItemIdentification>
			<ManufacturersItemIdentification>
				<ID xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"></ID>
			</ManufacturersItemIdentification>
		</Item>
		<Price>
			<PriceAmount currencyID="TRY" xmlns="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">{{docCurrentLine.rate}}</PriceAmount>
		</Price>
	</InvoiceLine>
		"""

	elif strType == "einvoice-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IBasicIntegration/SaveAsDraft',
			'Connection': 'Keep-Alive'
		}
	
	elif strType == "login-test-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IBasicIntegration/WhoAmI',
			'Connection': 'Keep-Alive'
		}
	elif strType == "login-test-body":
		strResult = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
	<soapenv:Body>
		<tem:WhoAmI>
			<tem:userInfo Username="{{docEISettings.kullaniciadi}}" Password="{{docEISettings.parola}}"/>
		</tem:WhoAmI>
	</soapenv:Body>
</soapenv:Envelope>
"""

	elif strType == "query-invoice-status-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			'SOAPAction': 'http://tempuri.org/IBasicIntegration/QueryOutboxInvoiceStatus',
			'Connection': 'Keep-Alive'
		}
	
	elif strType == "query-invoice-status-body":
		strResult = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Body>
	  <tem:QueryOutboxInvoiceStatus>
		<tem:userInfo Username="{{docEISettings.kullaniciadi}}" Password="{{docEISettings.parola}}"/>
		 <tem:invoiceIds>
			<tem:string>{{docSI.td_efatura_uuid}}</tem:string>
		 </tem:invoiceIds>
	  </tem:QueryOutboxInvoiceStatus>
   </soapenv:Body>
</soapenv:Envelope>
"""
	elif strType == "query-get-user-aliasses-headers":
		strResult = {
			'Accept-Encoding': 'gzip,deflate',
			'Accept': 'text/xml',
			'Content-Type': 'text/xml;charset=UTF-8',
			'Cache-Control': 'no-cache',
			'Pragma': 'no-cache',
			#'SOAPAction': 'http://tempuri.org/IIntegration/GetUserAliasses',
			'SOAPAction': 'http://tempuri.org/IBasicIntegration/GetUserAliasses',
			'Connection': 'Keep-Alive'
		}

	elif strType == "query-get-user-aliasses-body":
		strResult = """
		<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
			<soapenv:Body>
				<tem:GetUserAliasses>
					<tem:userInfo Username="{{docEISettings.kullaniciadi}}" Password="{{docEISettings.parola}}"/>
					<tem:vknTckn>{{docCustomer.tax_id}}</tem:vknTckn>
				</tem:GetUserAliasses>
			</soapenv:Body>
		</soapenv:Envelope>
		"""

	return strResult

def get_service_xml(strType, strIntegrator):
	if strIntegrator == 'Uyumsoft':
		return get_service_xml_for_uyumsoft(strType)
	elif strIntegrator == "Bien Teknoloji":
		return get_service_xml_for_bien_teknoloji(strType)

@frappe.whitelist()
def get_incoming_invoices(doc):
	#Get incoming invoices
	strResult = ""

	try:
		body = get_service_xml('inbox-invoice-list-body')

		headers = get_service_xml('inbox-invoice-list-headers')

		#e-Fatura Ayarları
		docEISettings = frappe.get_single("eInvoice Settings")
		docEISettings.username = docEISettings.kullanici_adi
		docEISettings.parola = docEISettings.get_password('parola')


		if docEISettings.test_modu:
			strServerURL = docEISettings.test_servis_adresi
		else:
			strServerURL = docEISettings.canli_servis_adresi

		body = frappe.render_template(body, context={"docEISettings": docEISettings, "tarih1": tarih1, "tarih2": tarih2}, is_path=False)
		
		#frappe.log_error(str(body), "Olusan istek")

		response = requests.post(strServerURL, headers=headers, data=body)

		#frappe.log_error("Gelen cevap", "Gelen cevap")

		bsMain = BeautifulSoup(response.text, "lxml")
		if response.status_code == 500:
			strErrorMessage = bsMain.find_all("faultstring")[0].text
			strResult = "İşlem Başarısız! Hata Kodu:500. Detay:"
			strResult += strErrorMessage
			dctEttn = ""
		elif response.status_code == 200:
			frappe.log_error("Olumlu cevap", "Olumlu cevap")
			strResult = "İşlem Başarılı."
			
			dctInvoiceId = bsMain.find_all("invoiceid")
			#frappe.log_error(dctInvoiceId, "Faturano")
			dctEttn = bsMain.find_all("documentid")
			#frappe.log_error(dctEttn, "Ettn")
			dctTitle = bsMain.find_all("targettitle")
			dctAmount = bsMain.find_all("payableamount")
			dctDate = bsMain.find_all("executiondate")
			dctType = bsMain.find_all("type")
			dctIType = bsMain.find_all("invoicetiptype")
			#dctScn = bsMain.find_all("scenario")


			#frappe.log_error(bsMain,"TEST")
			y = []
			for idx, ettn in enumerate(dctEttn):
				#print(idx, ettn.text)
				ctrl = frappe.db.get_value('Purchase Invoice', {'ettn': ettn.text}, ['name']) #daha önce kabul edilmiş mi?
				if not ctrl:
					tip = ""
					if dctType[idx].text=="ComercialInvoice":
						tip = "TICARIFATURA"
					elif dctType[idx].text=="BaseInvoice":
						tip = "TEMELFATURA"

					x = {
						'ettn': ettn.text,
						'invoiceid': dctInvoiceId[idx].text,
						'title': dctTitle[idx].text,
						'amount': dctAmount[idx].text,
						'date': dctDate[idx].text,
						'type': tip,
						'invoicetype': dctIType[idx].text, 
						#'scenario': dctScn[idx].text
					}
					y.append(x)
			print(y)
			strResult = y
			
		else:
			strResult = _("İşlem Başarısız! Hata Kodu:{0}. Detay:").format(response.status_code)
			dctEttn = ""
			strResult += response.text

	except Exception as e:
		strResult = _("Sunucudan gelen mesaj işlenirken hata oluştu! Detay:{0}").format(e)
		frappe.log_error(e, _("E-Fatura (LoginTest) sunucudan gelen mesaj işlenemedi."))

	return {'result':strResult, 'ettn': dctEttn, 'response':response.text}

@frappe.whitelist()
def send_einvoice(strSalesInvoiceName):

	strResult = ""

	try:
		docSI = frappe.get_doc("Sales Invoice", strSalesInvoiceName)
		docCustomer = frappe.get_doc("Customer", docSI.customer)
		#Ayarlari alalim
		docEISettings = frappe.get_single("EFatura Ayarlar")
		docEISettings.parola = docEISettings.get_password('parola')

		strHeaders = frappe.safe_eval(docEISettings.td_efatura_header) #get_service_xml('einvoice-headers')
		strBody = docEISettings.td_efatura_xml_genel #get_service_xml('einvoice-body')
		strLine = docEISettings.td_efatura_xml_satir #get_service_xml('einvoice-line')
		strTaxWithholding = get_service_xml('einvoice-tevkifat', docEISettings.entegrator)

		docCustomerAddress = frappe.get_doc("Address", docSI.customer_address)

		docCustomer.id_scheme = "VKN" if len(docCustomer.tax_id) == 10 else "TCKN"
		#Eger alias tanimli degil ise bulalim
		if not docCustomer.td_alici_alias:
			docCustomer.td_alici_alias = get_user_aliasses(docCustomer=docCustomer)['alias']

		#Vergi dairesi alalim
		if hasattr(docCustomer, 'tax_office'):
			docCustomer.tax_office = docCustomer.tax_office if docCustomer.tax_office is not None else ''
		else:
			raise ValueError('Müşteri kartlarında için vergi dairesi alanı (tax_office) bulunamadı. (Customize Form ile Customer için tax_office alanı eklenmeli).')

		#Satirlari olusturalim
		docSI.contentLines = ""
		flTotalLineDiscountAmount = 0 #Satirlardan gelen toplam iskonto tutari
		for docSILine in docSI.items:
			docItem = frappe.get_doc("Item", docSILine.item_code)

			#Satir KDV orani, KDV Tutari, KDV Matrahi, Iskonto uygulanan rakami bulalim.
			docSILine.TaxPercent = frappe.get_doc("Account", docSI.taxes[0].account_head).tax_rate #docSI.taxes[0].rate #Satir KDV Orani.#TODO:satira bagli item-tax-template altinda ki oranlardan almali.Suan fatura genelinde ki ilk satirdan aliyoruz
			docSILine.TaxableAmount = docSILine.amount
			docSILine.TaxAmount = round((docSILine.TaxPercent/100) * docSILine.amount, 2)
			docSILine.AllowanceBaseAmount = docSILine.rate * docSILine.qty#Iskonto uygulanan rakam #docSILine.AllowanceBaseAmount = docSILine.price_list_rate * docSILine.qty#Iskonto uygulanan rakam			

			flTotalLineDiscountAmount += docSILine.discount_amount * docSILine.qty

			#E-Fatura birimini ayarlardan bulalim
			lstUnitLine = frappe.get_all('TD EFatura Birim Eslestirme',
				fields=['td_efatura_birimi'],
				filters=[['parent', '=', 'EFatura Ayarlar'], ['td_birim', '=', docSILine.uom]])
			
			if not lstUnitLine:
				raise ValueError('{UOM} birimi için E-Fatura Birimi tanımlanmamış. EFatura Ayarlar sayfasından Birim Eşleştirmesi giriniz.'.format(UOM=docSILine.uom))
			else:
				docSILine.efatura_birimi = lstUnitLine[0]['td_efatura_birimi']

			#XML olusturalim
			str_line_xml = frappe.render_template(strLine, context={"docCurrentLine": docSILine, "docItem":docItem}, is_path=False)
			docSI.contentLines = docSI.contentLines + str_line_xml

		#Ozel alanlari hesaplayalim
		docSI.LineExtensionAmount = docSI.net_total + flTotalLineDiscountAmount #Miktar*BirimFiyat (Iskonto dusulmeden onceki hali, vergi haric)
		docSI.TaxExclusiveAmount = docSI.net_total #VergiMatrahi (Vergiler Haric, Iskonto Dahil, Vergiye tabi kisim)
		docSI.TaxInclusiveAmount = docSI.grand_total #Vergiler, iskonto dahil
		docSI.AllowanceTotalAmount = flTotalLineDiscountAmount #Iskonto tutari
		docSI.ChargeTotal = 0 #Artirim tutari.
		docSI.PayableAmount = docSI.grand_total #Toplam odenecek tutar

		docSI.TaxAmount = docSI.total_taxes_and_charges
		docSI.TaxPercent = frappe.get_doc("Account", docSI.taxes[0].account_head).tax_rate #docSI.taxes[0].rate#TODO:satira bagli item-tax-template altinda ki oranlardan almali.Suan fatura genelinde ki ilk satirdan aliyoruz

		docSI.posting_date_formatted = formatdate(docSI.posting_date, "yyyy-MM-dd")
		docSI.posting_time_formatted = get_time(docSI.posting_time).strftime("%H:%M:%S")#format_time(time_string=docSI.posting_time, format_string='HH:mm:ss')#str(dateutil.parser.parse(docSI.posting_time)).strftime("%H-%M-%S")#docSI.posting_time #"03:55:40"# formatdate(docSI.posting_time, "HH:mm")#"HH:mm:ss.SSSSSSSZ")
		docSI.line_count = len(docSI.items)

		tax_withoholding = docSI.TaxAmount / 2
		tax_total = docSI.TaxAmount

		strTaxWithholding = frappe.render_template(strTaxWithholding, context=
		{
			"kdv_tevkifat1": tax_withoholding, 
			"kdv_tevkifat2": tax_withoholding,
			"kdv_tam": tax_total
		}, is_path=False)

		#Ana dokuman dosyamizi olusturalim. Once not parametreleri dolsun sonra asil dokuman.
		strDocXML = frappe.render_template(strBody, context=
		{
			"docSI": docSI, 
			"docCustomer": docCustomer, 
			"docEISettings": docEISettings,
			"docCustomerAddress": docCustomerAddress
		}, is_path=False)
		strDocXML = frappe.render_template(strDocXML, context=
		{
			"docSI": docSI, 
			"docCustomer": docCustomer, 
			"docEISettings": docEISettings,
			"docCustomerAddress": docCustomerAddress
		}, is_path=False)

		if docEISettings.test_modu:
			strServerURL = docEISettings.test_efatura_adresi
			#Test modunda gonderdigimiz xml i  de saklayalim
			frappe.log_error(strDocXML, _("E-Fatura (send_einvoice) gönderilen paket"))
		else:
			strServerURL = docEISettings.efatura_adresi

		#webservisine gonderelim
		#response = requests.post('https://efatura-test.uyumsoft.com.tr/services/integration', headers=strHeaders, data=strDocXML.encode('utf-8'))
		#response = requests.post('https://efatura.uyumsoft.com.tr/services/integration', headers=strHeaders, data=strDocXML.encode('utf-8'))
		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect SendEInvoice Request", f"URL={strServerURL},\nHeaders={strHeaders},\nData={strDocXML}")
		
		response = requests.post(strServerURL, headers=strHeaders, data=strDocXML.encode('utf-8'))
		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect SendEInvoice Response", f"Code={response.status_code},\nResponse={response.text}")

		# You can inspect the response just like you did before. response.headers, response.text, response.content, response.status_code

		bsMain = BeautifulSoup(response.text, "lxml")#response.content.decode('utf8')
		if response.status_code == 500:
			strErrorMessage = bsMain.find_all("faultstring")[0].text
			strResult = "İşlem Başarısız! Hata Kodu:500. Detay:"
			strResult += strErrorMessage
			docSI.add_comment('Comment', text="E-Fatura: Belge gönderilemedi! Detay:" + strResult)
		elif response.status_code == 200:
			objSaveResult = bsMain.find_all("saveasdraftresult")[0]#['issucceded']#.get_attribute_list('is_succeddede')
			if objSaveResult['issucceded'] == "false":
				strResult = "Fatura gönderilemedi! Detay:" + objSaveResult['message']
				docSI.add_comment('Comment', text="E-Fatura: Belge gönderilemedi! Detay:" + objSaveResult['message'])
			else:
				strResult = "İşlem Başarılı."
				#Referanslari faturaya geri yazalim
				objSaveResultInfo = bsMain.find_all("value")[0]#['issucceded']#.get_attribute_list('is_succeddede')

				#docSI.td_efatura_senaryosu = objSaveResultInfo['invoicescenario']
				docSI.db_set('td_efatura_senaryosu', objSaveResultInfo['invoicescenario'], notify=True)
				docSI.db_set('td_efatura_uuid', objSaveResultInfo['id'], notify=True)
				docSI.db_set('td_efatura_ettn', objSaveResultInfo['number'], notify=True)

				#Ayarlarda fatura belge numarasi ayarlanmis ise ilgili alani guncelleyelim. https://app.asana.com/0/1129228181996987/1179462249309721/f
				if docEISettings.td_guncellenecek_alan:
					docSI.db_set(docEISettings.td_guncellenecek_alan, objSaveResultInfo['number'], notify=True)

				docSI.add_comment('Comment', text=_('E-Fatura: Belge gönderildi. (Ek Bilgiler:{0}, {1})'.format(objSaveResultInfo['number'], objSaveResultInfo['id'])))

				#Fatura durumunu alalim
				docSI.db_set('td_efatura_durumu', get_invoice_status(docSI)['result'], notify=True)

				docSI.notify_update()
		else:
			strResult = _("İşlem Başarısız! Hata Kodu:{0}. Detay:").format(response.status_code)
			strResult += response.text

	except Exception as e:
		strResult = _("Hata oluştu! Detay:{0}").format(e)
		frappe.log_error(frappe.get_traceback(), _("E-Fatura (send_einvoice) generated an error."))
	
	return {'result':strResult, 'response':response.text if 'response' in locals() else ''}

@frappe.whitelist()
def get_user_aliasses(strCustomerName = None, docCustomer = None):
	#Firma alias bilgilerini alir. strCustomerName = Musteri Kart ID
	strResult = ""
	strResultAlias = ""

	try:
		if docCustomer is None:
			docCustomer = frappe.get_doc("Customer", strCustomerName)

		#Ayarlari alalim
		docEISettings = frappe.get_single("EFatura Ayarlar")		
		docEISettings.kullaniciadi = docEISettings.kullaniciadi 
		docEISettings.parola = docEISettings.get_password('parola')

		body = get_service_xml('query-get-user-aliasses-body', docEISettings.entegrator)
		headers = get_service_xml('query-get-user-aliasses-headers', docEISettings.entegrator)

		body = frappe.render_template(body, context={"docEISettings": docEISettings, "docCustomer": docCustomer}, is_path=False)
		
		if docEISettings.test_modu:
			strServerURL = docEISettings.test_efatura_adresi
			frappe.log_error(body, _("E-Fatura (get_user_aliasses) gönderilen paket"))
		else:
			strServerURL = docEISettings.efatura_adresi

		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect GetUserAliasses Request", f"URL={strServerURL},\nHeaders={headers},\nBody={body}")

		response = requests.post(strServerURL, headers=headers, data=body)

		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect GetUserAliasses Response", f"Code={response.status_code},\nResponse={response.text}")

		bsMain = BeautifulSoup(response.text, "lxml")#response.content.decode('utf8')

		if response.status_code == 500:
			strErrorMessage = bsMain.find_all("faultstring")[0].text
			strResult = "İşlem Başarısız! Hata Kodu:500. Detay:"
			strResult += strErrorMessage
		elif response.status_code == 200:
			objSaveResult = bsMain.find_all("getuseraliassesresult")[0]#['issucceded']#.get_attribute_list('is_succeddede')
			if objSaveResult['issucceded'] == "false":
				strResult = "Adres alınamadı! Detay:" + objSaveResult['message']
				docCustomer.add_comment('Comment', text="E-Fatura: Adres alınamadı! Detay:" + objSaveResult['message'])
			else:
				if len(bsMain.find_all("receiverboxaliases")) == 0:
					#EArsiv kullanicisi olmali
					strResult = "E-Arşiv kullanıcısı."
					docCustomer.db_set('td_alici_alias', 'defaultpk', notify=True)
					docCustomer.add_comment('Comment', text="E-Fatura: E-Arşiv kullanıcısı (defaultpk).")
					docCustomer.notify_update()
				else:
					objReceiverboxAliases = bsMain.find_all("receiverboxaliases")[0]
					strCompanyTitle = bsMain.find_all("definition")[0]['title']
					#print(objReceiverboxAliases['alias'])
					strResultAlias = objReceiverboxAliases['alias']
					strResult = _("Adres {0} olarak güncellendi.Firma Adı:{1}").format(objReceiverboxAliases['alias'], strCompanyTitle)
					docCustomer.db_set('td_alici_alias', objReceiverboxAliases['alias'], notify=True)
					docCustomer.add_comment('Comment', text=_("E-Fatura: Adres {0} olarak güncellendi.Firma Adı:{1}").format(objReceiverboxAliases['alias'], strCompanyTitle))
					docCustomer.notify_update()
		else:
			strResult = _("İşlem Başarısız! Hata Kodu:{0}. Detay:").format(response.status_code)
			strResult += response.text

	except Exception as e:
		strResult = _("Sunucudan gelen mesaj işlenirken hata oluştu! Detay:{0}").format(e)
		frappe.log_error(frappe.get_traceback(), _("E-Fatura (GetUserAliasses) sunucudan gelen mesaj işlenemedi."))

	return {'result':strResult, 'response':response.text, 'alias': strResultAlias}

@frappe.whitelist()
def get_invoice_status(docSI = None, strSaleInvoiceName = None):
	strResult = ""

	if docSI is None:
		docSI = frappe.get_doc("Sales Invoice", strSaleInvoiceName)

	try:
		#Ayarlari alalim
		docEISettings = frappe.get_single("EFatura Ayarlar")		
		docEISettings.kullaniciadi = docEISettings.kullaniciadi 
		docEISettings.parola = docEISettings.get_password('parola')

		body = get_service_xml('query-invoice-status-body', docEISettings.entegrator)
		body = frappe.render_template(body, context={"docEISettings": docEISettings, "docSI": docSI}, is_path=False)

		headers = get_service_xml('query-invoice-status-headers', docEISettings.entegrator)

		if docEISettings.test_modu:
			strServerURL = docEISettings.test_efatura_adresi
			frappe.log_error(body, _("E-Fatura (get_invoice_status) gönderilen paket"))
		else:
			strServerURL = docEISettings.efatura_adresi

		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect GetInvoiceStatus Request", f"URL={strServerURL},\nHeaders={headers},\nBody={body}")

		response = requests.post(strServerURL, headers=headers, data=body)

		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect GetInvoiceStatus Response", f"Code={response.status_code}, Response={response.text}")

		bsMain = BeautifulSoup(response.text, "lxml")#response.content.decode('utf8')
		if response.status_code == 500:
			strErrorMessage = bsMain.find_all("faultstring")[0].text
			strResult = "İşlem Başarısız! Hata Kodu:500. Detay:"
			strResult += strErrorMessage
		elif response.status_code == 200:
			strResult = bsMain.find_all("value")[0]['status']
		else:
			strResult = _("İşlem Başarısız! Hata Kodu:{0}. Detay:").format(response.status_code)
			strResult += response.text

	except Exception as e:
		strResult = _("Sunucudan gelen mesaj işlenirken hata oluştu! Detay:{0}").format(e)
		frappe.log_error(frappe.get_traceback(), _("E-Fatura (GetInvoiceStatus) sunucudan gelen mesaj işlenemedi."))

	return {'result':strResult, 'response':response.text}

@frappe.whitelist()
def login_test(doc):
	dctResult = {'op_result': False, 'op_message': ''}

	try:
		#Ayarlari alalim
		#docEISettings = frappe.get_single("EFatura Ayarlar")
		docEISettings = frappe.get_doc(json.loads(doc))
		docEISettings.kullaniciadi = docEISettings.kullaniciadi 
		docEISettings.parola = docEISettings.get_password('parola')

		body = get_service_xml('login-test-body', docEISettings.entegrator)
		body = frappe.render_template(body, context={"docEISettings": docEISettings}, is_path=False)

		headers = get_service_xml('login-test-headers', docEISettings.entegrator)

		if docEISettings.test_modu:
			strServerURL = docEISettings.test_efatura_adresi
			frappe.log_error(body, _("E-Fatura (login_test) gönderilen paket"))
		else:
			strServerURL = docEISettings.efatura_adresi

		#response = requests.post('https://efatura-test.uyumsoft.com.tr/services/integration', headers=headers, data=body)
		#response = requests.post('https://efatura.uyumsoft.com.tr/services/integration', headers=headers, data=body)
		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect Login Request", f"URL={strServerURL}, Headers={headers}, Body={body}")
		
		response = requests.post(strServerURL, headers=headers, data=body)
		if docEISettings.detailed_log == True:
			frappe.log_error("E-Connect Login Response", f"Code={response.status_code}, Response={response.text}")

		bsMain = BeautifulSoup(response.text, "lxml")#response.content.decode('utf8')
		if response.status_code == 500:
			dctResult['op_result'] = False
			strErrorMessage = bsMain.find_all("faultstring")[0].text
			dctResult['op_message'] = "İşlem Başarısız! Hata Kodu:500. Detay:"
			dctResult['op_message'] += strErrorMessage
		elif response.status_code == 200:
			dctResult['op_result'] = True
			dctResult['op_message'] = "İşlem Başarılı."
			strCustomerName = bsMain.find_all("name")[1].text
			dctResult['op_message'] += _("Firma Adı:{0}").format(strCustomerName)
		else:
			dctResult['op_result'] = False
			dctResult['op_message'] = _("İşlem Başarısız! Hata Kodu:{0}. Detay:").format(response.status_code)
			dctResult['op_message'] += response.text

	except Exception as e:
		dctResult['op_result'] = False
		dctResult['op_message'] = _("Sunucu iletişiminde beklenmeyen hata oluştu! Detay:{0}").format(e)
		frappe.log_error(frappe.get_traceback(), _("E-Fatura (LoginTest) hatası"))

	return dctResult

### DOSYA GUNCELLEME MODULU
@frappe.whitelist()
def td_attach_all_docs_from_item(document, strURL):
	from frappe import _, throw
	from frappe.utils import flt
	from frappe.utils.file_manager import save_url, save_file, get_file_name, remove_all, remove_file
	from frappe.utils import get_site_path, get_files_path, random_string, encode
	import json
	#Dokuman icin dosya eklerini ayarlayalim
	document = json.loads(document)
	document2 = frappe._dict(document)

	current_attachments = [] #Icinde oldugumuz dokumanda ki ek dosya bilgilerini tutar
	items = [] #Dokumanda ki malzeme bilgilerini tutar
	item_attachments = [] #Malzemede ki ek dosya bilgilerini tutar
	current_attachments_file_name = [] #Dosya adini saklar
	item_attachments_file_name = [] #Dosya adi

	#Once bulundugumuz dokumanda ki butun ek dosyalari bir dizi icinde (current_attachments) saklayalaim
	for file_info in frappe.db.sql("""select file_url, file_name from `tabFile` where attached_to_doctype = %(doctype)s and attached_to_name = %(docname)s""", {'doctype': document2.doctype, 'docname': document2.name}, as_dict=True ):
			current_attachments.append(file_info.file_url)
			current_attachments_file_name.append(file_info.file_name)
			#frappe.msgprint("Found " + file_info.file_name + " file in this document", "Document Files")

	#Dokumanda ki butun malzeme kartlari icin ek dosya var mi kontrol edelim
	for item in document["items"]:
		#Malzeme kayidina ulasalim
		item_doc = frappe.get_doc('Item', item["item_code"]) #frappe.get_doc("Item",item)
		#frappe.msgprint(str(item_doc["attachments"][0]["file_url"]))
		#frappe.msgprint("Getting " + item_doc.name + " files", "Items")

		#Malzemeye bagli ek dosyalari alalim
		for file_info in frappe.db.sql("""select file_url, file_name from `tabFile` where attached_to_doctype = %(doctype)s and attached_to_name = %(docname)s""", {'doctype': item_doc.doctype, 'docname': item_doc.name}, as_dict=True ):
			item_attachments.append(file_info.file_url)
			item_attachments_file_name.append(file_info.file_name)
			#frappe.msgprint("Found " + file_info.file_name + " file in item " + item_doc.name, "Item Files")

	count = 0
	dIndex = 0
	#frappe.msgprint("Starting to add attachments")
	for attachment in item_attachments:
		# Check to see if this file is attached to the one we are looking for
		if not attachment in current_attachments:
			count = count + 1
			#frappe.msgprint(attachment)
			myFile = save_url(attachment, item_attachments_file_name[dIndex], document2.doctype, document2.name, "Home/Attachments", 0)
			myFile.file_name = item_attachments_file_name[dIndex] #attachment
			myFile.save()
			current_attachments.append(attachment)
		dIndex = dIndex + 1

	frappe.msgprint("{0} adet dosya eklendi".format(count))

import frappe
import zipfile
import io
import base64
import requests
from datetime import datetime

@frappe.whitelist()
def send_invoice_to_finalizer(invoice_name=None):
    if not invoice_name:
        return {"status": "fail", "error": "Invoice name is required"}
    try:
        settings = frappe.get_single("TD EInvoice Settings")
        if not settings.integrator:
            return {"status": "fail", "error": "Integrator not configured"}
        integrator = frappe.get_doc("TD EInvoice Integrator", settings.integrator)
        if not integrator.td_enable:
            return {"status": "fail", "error": "Integration is disabled"}

        doc_si = frappe.get_doc("Sales Invoice", invoice_name)
        xml_content = generate_invoice_xml(doc_si, settings)

        # XML → ZIP → Base64
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{doc_si.name}.xml", xml_content)
        zip_base64 = base64.b64encode(mem.getvalue()).decode()

        soap_body = create_soap_body(zip_base64, integrator, file_name=f"{doc_si.name}.zip")
        url = get_service_url(integrator)

        headers = {
            "Content-Type": 'application/soap+xml; charset=utf-8; action="http://tempuri.org/IEBelge/sendData"'
        }
        resp = requests.post(url, data=soap_body.encode("utf-8"), headers=headers, timeout=60)

        # ✅ Log XML and response
        frappe.log_error(
            f"""🧾 Sent XML:
{xml_content}

📤 Finalizer Response:
HTTP {resp.status_code}
{resp.text}
""",
            f"Finalizer SOAP Result - {invoice_name}"
        )

        return {
            "status": "success" if resp.status_code == 200 else "fail",
            "http_status": resp.status_code,
            "response": resp.text
        }

    except Exception as e:
        frappe.log_error(str(e), f"Finalizer Send Error - {invoice_name}")
        return {"status": "fail", "error": str(e)}

def generate_invoice_xml(doc_si, settings):
    company = frappe.get_doc("Company", settings.company) if settings.company else None
    customer = frappe.get_doc("Customer", doc_si.customer) if doc_si.customer else None

    invoice_lines = ""
    for idx, item in enumerate(doc_si.items, 1):
        uom_code = get_uom_code(item.uom, settings)
        invoice_lines += f"""  <cac:InvoiceLine>
    <cbc:ID>{idx}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="{uom_code}">{item.qty}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{doc_si.currency or 'TRY'}">{item.amount}</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>{item.item_name or item.item_code}</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="{doc_si.currency or 'TRY'}">{item.rate}</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns:ubltr="urn:oasis:names:specification:ubl:schema:xsd:TurkishCustomizationExtensionComponents"
         xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
         xmlns:xades="http://uri.etsi.org/01903/v1.3.2#"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xsi:schemaLocation="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2 UBL-Invoice-2.1.xsd">
  <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
  <cbc:CustomizationID>TR1.2</cbc:CustomizationID>
  <cbc:ProfileID>{doc_si.custom_scenario_type}</cbc:ProfileID>
  <cbc:ID>{doc_si.name}</cbc:ID>
  <cbc:IssueDate>{doc_si.posting_date}</cbc:IssueDate>
  <cbc:IssueTime>{doc_si.posting_time or '12:00:00'}</cbc:IssueTime>
  <cbc:InvoiceTypeCode>{doc_si.custom_invoice_type or 'SATIS'}</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{doc_si.currency or 'TRY'}</cbc:DocumentCurrencyCode>
  <cbc:LineCountNumeric>{len(doc_si.items)}</cbc:LineCountNumeric>

  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyIdentification><cbc:ID>{company.tax_id}</cbc:ID></cac:PartyIdentification>
    <cac:PartyName><cbc:Name>{company.company_name}</cbc:Name></cac:PartyName>
  </cac:Party></cac:AccountingSupplierParty>

  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyIdentification><cbc:ID>{customer.tax_id}</cbc:ID></cac:PartyIdentification>
    <cac:PartyName><cbc:Name>{doc_si.customer_name}</cbc:Name></cac:PartyName>
  </cac:Party></cac:AccountingCustomerParty>

{invoice_lines}
</Invoice>
"""
    return xml

def get_uom_code(uom, settings):
    if not uom or not settings.unit_mapping:
        return "NIU"
    for m in settings.unit_mapping:
        if m.einvoice_unit == uom:
            return m.einvoice_unit or "NIU"
    return "NIU"

def create_soap_body(zip_base64, integrator, file_name="invoice.zip"):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body><sendData xmlns="http://tempuri.org/">
      <document>
        <UserID>{integrator.username}</UserID>
        <UserPassword>{integrator.password}</UserPassword>
        <ReceiverID>22222222222</ReceiverID>
        <DocumentVariable>efaturaozel</DocumentVariable>
        <fileName>{file_name}</fileName>
        <binaryData>
          <FileByte>{zip_base64}</FileByte>
          <FileName>{file_name}</FileName>
        </binaryData>
      </document>
    </sendData></soap12:Body>
</soap12:Envelope>"""

def get_service_url(integrator):
    return integrator.td_test and (integrator.test_efatura_url or integrator.efatura_url) or (integrator.efatura_url or "")


@frappe.whitelist()
def send_custom_xml_to_finalizer(xml_string):
    import io, zipfile, base64, requests

    # XML'yi ZIP'e çevir
    memory_zip = io.BytesIO()
    with zipfile.ZipFile(memory_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("invoice.xml", xml_string)
    zip_bytes = memory_zip.getvalue()
    zip_base64 = base64.b64encode(zip_bytes).decode("utf-8")

    # SOAP Body hazırla
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                 xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <sendData xmlns="http://tempuri.org/">
      <document>
        <UserID>24</UserID>
        <UserPassword>kFaQ7yww45jVr7NnTHmGaA==</UserPassword>
        <ReceiverID>22222222222</ReceiverID>
        <DocumentVariable>efaturaozel</DocumentVariable>
        <fileName>invoice.zip</fileName>
        <binaryData>
          <FileByte>{zip_base64}</FileByte>
          <FileName>invoice.zip</FileName>
        </binaryData>
      </document>
    </sendData>
  </soap12:Body>
</soap12:Envelope>"""

    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8; action=\"http://tempuri.org/IEBelge/sendData\""
    }

    url = "https://app.finalizer.com.tr/services/EBelge.svc"

    try:
        response = requests.post(url, data=soap_body.encode("utf-8"), headers=headers)
        response_text = response.text.strip()

        # ✅ XML ve yanıt logla
        frappe.log_error(
            f"""🧾 Sent XML:
{xml_string}

📤 Finalizer Response:
HTTP {response.status_code}
{response_text}
""",
            "Custom Finalizer XML Send Log"
        )

        return {
            "status": "success" if response.status_code == 200 else "fail",
            "http_status": response.status_code,
            "response": response_text
        }

    except Exception as e:
        frappe.log_error(str(e), "Custom Finalizer XML Send Error")
        return {"status": "fail", "error": str(e)}