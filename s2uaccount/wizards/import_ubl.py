# -*- coding: utf-8 -*-

import base64
from datetime import datetime
from lxml import etree

from ..helpers import ubl

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ImportUBL(models.TransientModel):
    _name = "wizard.import.ubl"
    _description = "Import UBL"

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    ubl_data = fields.Binary(string='Content', required=True)
    ubl_fname = fields.Char(string='Filename')


    def get_ublcontent_from_invoice(self):

        attachments = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.account.invoice.po'),
                                                               ('res_id', '=', self.id)])
        ublobj = ubl.UBLParser()
        for a in attachments:
            data = base64.b64decode(a.datas)
            if ublobj.is_ubl(data, input_type='xml'):
                return data
        return False

    def ubl_get_kvk(self, data):
        if data['PartyIdentification']:
            idtype = data['PartyIdentification'].get('ID.schemeAgencyName', '')
            c_of_c = data['PartyIdentification'].get('ID', '')
            if c_of_c and idtype == 'KVK':
                return c_of_c
        return False

    def ubl_get_name(self, data, block='all'):
        if block in ['all', 'PartyName']:
            if data['PartyName']:
                company_name = data['PartyName'].get('Name', False)
                if company_name:
                    return company_name
        if block in ['all', 'PartyLegalEntity']:
            if data['PartyLegalEntity']:
                company_name = data['PartyLegalEntity'].get('RegistrationName', False)
                if company_name:
                    return company_name

        return False

    def ubl_get_code(self, data):
        if data['PartyLegalEntity']:
            code = data['PartyLegalEntity'].get('CompanyID', False)
            if code:
                return code

        return False

    def ubl_match_supplier(self, company_id, supplier):

        if not isinstance(supplier, dict):
            False

        entity_model = self.env['s2u.crm.entity']

        exists = False

        if supplier.get('vat'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('tinno', '=', supplier.get('vat')),
                                          ('type', '=', 'b2b')])

        if not exists and supplier.get('website'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('website', '=', supplier.get('website')),
                                          ('type', '=', 'b2b')])

        if not exists and supplier.get('email'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('email', '=', supplier.get('email')),
                                          ('type', '=', 'b2b')])

        if not exists and supplier.get('phone'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('phone', '=', supplier.get('phone')),
                                          ('type', '=', 'b2b')])

        if not exists and supplier.get('fax'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('fax', '=', supplier.get('fax')),
                                          ('type', '=', 'b2b')])

        if not exists and supplier.get('name'):
            exists = entity_model.search([('company_id', '=', company_id),
                                          ('name', '=', supplier.get('name')),
                                          ('type', '=', 'b2b')])

        return exists

    def ubl_supplier_to_entity(self, company_id, supplier):

        entity_model = self.env['s2u.crm.entity']
        address_model = self.env['s2u.crm.entity.address']
        country_model = self.env['res.country']

        vals = {'name': supplier['name'],
                'type': 'b2b',
                'tinno': supplier['vat'],
                'entity_code': supplier['ref'],
                'phone': supplier['phone'],
                'fax': supplier['fax'],
                'email': supplier['email'],
                'website': supplier['website']}
        new_supplier = entity_model.create(vals)

        if supplier.get('street'):
            vals = {'entity_id': new_supplier.id,
                    'address': supplier.get('street'),
                    'zip': supplier.get('zip'),
                    'city': supplier.get('city'),
                    'type': 'def',
                    'name': supplier.get('city') if supplier.get('city') else 'standaard'}
            if supplier.get('country_code'):
                country = country_model.search([('code', '=', supplier.get('country_code'))])
                if country:
                    vals['country_id'] = country.id
            address_model.create(vals)
        return new_supplier

    def ubl_parse_address(self, address_node, ns):
        country_code_xpath = address_node.xpath(
            'cac:Country/cbc:IdentificationCode',
            namespaces=ns)
        country_code = country_code_xpath and country_code_xpath[0].text \
                       or False
        state_code_xpath = address_node.xpath(
            'cbc:CountrySubentityCode', namespaces=ns)
        state_code = state_code_xpath and state_code_xpath[0].text or False
        zip_xpath = address_node.xpath('cbc:PostalZone', namespaces=ns)
        zip = zip_xpath and zip_xpath[0].text and \
              zip_xpath[0].text.replace(' ', '') or False
        street_xpath = address_node.xpath(
            'cbc:StreetName', namespaces=ns)
        street = street_xpath and street_xpath[0].text or False
        city_xpath = address_node.xpath(
            'cbc:CityName', namespaces=ns)
        city = city_xpath and city_xpath[0].text or False
        address_dict = {
            'zip': zip,
            'state_code': state_code,
            'country_code': country_code,
            'street': street,
            'city': city
        }
        return address_dict

    def ubl_parse_party(self, party_node, ns):
        partner_name_xpath = party_node.xpath(
            'cac:PartyName/cbc:Name', namespaces=ns)
        vat_xpath = party_node.xpath(
            'cac:PartyTaxScheme/cbc:CompanyID', namespaces=ns)
        email_xpath = party_node.xpath(
            'cac:Contact/cbc:ElectronicMail', namespaces=ns)
        phone_xpath = party_node.xpath(
            'cac:Contact/cbc:Telephone', namespaces=ns)
        fax_xpath = party_node.xpath(
            'cac:Contact/cbc:Telefax', namespaces=ns)
        website_xpath = party_node.xpath(
            'cbc:WebsiteURI', namespaces=ns)
        partner_dict = {
            'vat': vat_xpath and vat_xpath[0].text or False,
            'name': partner_name_xpath[0].text,
            'email': email_xpath and email_xpath[0].text or False,
            'website': website_xpath and website_xpath[0].text or False,
            'phone': phone_xpath and phone_xpath[0].text or False,
            'fax': fax_xpath and fax_xpath[0].text or False,
        }
        address_xpath = party_node.xpath('cac:PostalAddress', namespaces=ns)
        if address_xpath:
            address_dict = self.ubl_parse_address(address_xpath[0], ns)
            partner_dict.update(address_dict)
        return partner_dict

    def ubl_parse_supplier_party(self, customer_party_node, ns):
        ref_xpath = customer_party_node.xpath(
            'cac:CustomerAssignedAccountID', namespaces=ns)
        party_node = customer_party_node.xpath('cac:Party', namespaces=ns)[0]
        partner_dict = self.ubl_parse_party(party_node, ns)
        partner_dict['ref'] = ref_xpath and ref_xpath[0].text or False
        return partner_dict

    def ubl_parse_product(self, line_node, ns):
        ean13_xpath = line_node.xpath(
            "cac:Item/cac:StandardItemIdentification/cbc:ID[@schemeID='GTIN']",
            namespaces=ns)
        code_xpath = line_node.xpath(
            "cac:Item/cac:SellersItemIdentification/cbc:ID", namespaces=ns)
        product_dict = {
            'ean13': ean13_xpath and ean13_xpath[0].text or False,
            'code': code_xpath and code_xpath[0].text or False,
        }
        return product_dict

    def parse_ubl_invoice_line(self, iline, sign, total_line_lines, namespaces):
        price_unit_xpath = iline.xpath(
            "cac:Price/cbc:PriceAmount", namespaces=namespaces)
        qty_xpath = iline.xpath(
            "cbc:InvoicedQuantity", namespaces=namespaces)
        # Some UBL invoices don't have any InvoicedQuantity tag
        # So we have a fallback on quantity = 1
        qty = 1
        uom = {}
        if qty_xpath:
            if float(qty_xpath[0].text):
                qty = float(qty_xpath[0].text)
            if qty_xpath[0].attrib and qty_xpath[0].attrib.get('unitCode'):
                unece_uom = qty_xpath[0].attrib['unitCode']
                if unece_uom == 'ZZ':
                    unece_uom = 'C62'
                uom = {'unece_code': unece_uom}
        product_dict = self.ubl_parse_product(iline, namespaces)
        name_xpath = iline.xpath(
            "cac:Item/cbc:Description", namespaces=namespaces)
        name = name_xpath and name_xpath[0].text or '-'
        price_subtotal_xpath = iline.xpath(
            "cbc:LineExtensionAmount", namespaces=namespaces)
        price_subtotal = float(price_subtotal_xpath[0].text)
        if not price_subtotal:
            return False
        if price_unit_xpath:
            price_unit = float(price_unit_xpath[0].text)
        else:
            price_unit = price_subtotal / qty
        total_line_lines += price_subtotal
        taxes_xpath = iline.xpath(
            "cac:Item/cac:ClassifiedTaxCategory", namespaces=namespaces)
        if not taxes_xpath:
            taxes_xpath = iline.xpath(
                "cac:TaxTotal/cac:TaxSubtotal/cac:TaxCategory",
                namespaces=namespaces)
        taxes = []
        for tax in taxes_xpath:
            type_code_xpath = tax.xpath(
                "cac:TaxScheme/cbc:ID[@schemeAgencyID='6']",
                namespaces=namespaces)
            type_code = type_code_xpath and type_code_xpath[0].text or 'VAT'
            categ_code_xpath = tax.xpath(
                "cbc:ID", namespaces=namespaces)
            # TODO: Understand why sometimes they use H
            categ_code = categ_code_xpath and categ_code_xpath[0].text or False
            if categ_code == 'H':
                categ_code = 'S'
            percent_xpath = tax.xpath(
                "cbc:Percent", namespaces=namespaces)
            if not percent_xpath:
                percent_xpath = tax.xpath(
                    "../cbc:Percent", namespaces=namespaces)
            if percent_xpath:
                percentage = percent_xpath[0].text and\
                    float(percent_xpath[0].text)
            else:
                percentage = 0.0
            tax_dict = {
                'type': 'percent',
                'amount': percentage,
                'unece_type_code': type_code,
                'unece_categ_code': categ_code,
                }
            taxes.append(tax_dict)

        taxes_xpath = iline.xpath("cac:TaxTotal", namespaces=namespaces)
        total_vat = 0.0
        for tax in taxes_xpath:
            tax_amount_xpath = tax.xpath("cbc:TaxAmount", namespaces=namespaces)
            total_vat += float(tax_amount_xpath[0].text)

        vals = {
            'product': product_dict,
            'qty': qty * sign,
            'uom': uom,
            'price_unit': price_unit,
            'name': name,
            'taxes': taxes,
            'sub_total': price_subtotal,
            'total_vat': total_vat,
            }
        return vals

    @api.multi
    def ubl_match_account(self, company_id, supplier, ubl_match):

        account_model = self.env['s2u.account.account']

        accounts = account_model.search([('company_id', '=', company_id),
                                         ('type', '=', 'expense'),
                                         ('vat_id', '!=', False)])
        if accounts:
            return {'account_id': accounts[0].id,
                    'vat_id': accounts[0].vat_id.id}
        else:
            return False

    @api.multi
    def do_import_ubl(self):
        self.ensure_one()

        invoice_model = self.env['s2u.account.invoice.po']

        file_data = base64.b64decode(self.ubl_data)
        try:
            xml_root = etree.fromstring(file_data)
        except:
            raise ValueError(_("This XML file is not XML-compliant"))

        if xml_root.tag and xml_root.tag.startswith('{urn:oasis:names:specification:ubl:schema:xsd:Invoice'):
            pass

        namespaces = xml_root.nsmap
        inv_xmlns = namespaces.pop(None)
        namespaces['inv'] = inv_xmlns
        doc_type_xpath = xml_root.xpath("/inv:Invoice/cbc:InvoiceTypeCode", namespaces=namespaces)

        sign = 1
        if doc_type_xpath:
            inv_type_code = doc_type_xpath[0].text
            if inv_type_code not in ['380', '381']:
                raise ValueError(_(
                    "This UBL XML file is not an invoice/refund file "
                    "(InvoiceTypeCode is %s") % inv_type_code)
            if inv_type_code == '381':
                sign = -1

        try:
            inv_number_xpath = xml_root.xpath('//cbc:ID', namespaces=namespaces)
            supplier_xpath = xml_root.xpath(
                '/inv:Invoice/cac:AccountingSupplierParty',
                namespaces=namespaces)
            supplier_dict = self.ubl_parse_supplier_party(
                supplier_xpath[0], namespaces)

            date_xpath = xml_root.xpath(
                '/inv:Invoice/cbc:IssueDate', namespaces=namespaces)
            date_dt = datetime.strptime(date_xpath[0].text, '%Y-%m-%d')

            date_due_xpath = xml_root.xpath(
                "//cbc:PaymentDueDate", namespaces=namespaces)
            date_due_str = False
            if date_due_xpath:
                date_due_dt = datetime.strptime(date_due_xpath[0].text, '%Y-%m-%d')
                date_due_str = fields.Date.to_string(date_due_dt)

            currency_iso_xpath = xml_root.xpath(
                "/inv:Invoice/cbc:DocumentCurrencyCode", namespaces=namespaces)

            total_untaxed_xpath = xml_root.xpath(
                "/inv:Invoice/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                namespaces=namespaces)
            amount_untaxed = float(total_untaxed_xpath[0].text)

            total_line_xpath = xml_root.xpath(
                "/inv:Invoice/cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
                namespaces=namespaces)
            if total_line_xpath:
                total_line = float(total_line_xpath[0].text)
            else:
                total_line = amount_untaxed

            amount_total_xpath = xml_root.xpath(
                "/inv:Invoice/cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
                namespaces=namespaces)
            if amount_total_xpath:
                amount_total = float(amount_total_xpath[0].text)
            else:
                payable_total = xml_root.xpath(
                    "/inv:Invoice/cac:LegalMonetaryTotal/cbc:PayableAmount",
                    namespaces=namespaces)
                amount_total = float(payable_total[0].text)

            payment_type_code = xml_root.xpath(
                "/inv:Invoice/cac:PaymentMeans/"
                "cbc:PaymentMeansCode[@listAgencyID='6']",
                namespaces=namespaces)
            iban_xpath = bic_xpath = False
            if payment_type_code and payment_type_code[0].text == '31':
                iban_xpath = xml_root.xpath(
                    "//cac:PayeeFinancialAccount/cbc:ID[@schemeID='IBAN']",
                    namespaces=namespaces)
                bic_xpath = xml_root.xpath(
                    "//cac:PayeeFinancialAccount"
                    "/cac:FinancialInstitutionBranch"
                    "/cac:FinancialInstitution"
                    "/cbc:ID[@schemeID='BIC']",
                    namespaces=namespaces)
        except:
            raise ValueError(_("This UBL XML file is not an invoice/refund file."))

        res_lines = []
        total_line_lines = 0.0
        inv_line_xpath = xml_root.xpath(
            "/inv:Invoice/cac:InvoiceLine", namespaces=namespaces)
        for iline in inv_line_xpath:
            try:
                line_vals = self.parse_ubl_invoice_line(iline, sign, total_line_lines, namespaces)
            except:
                raise ValueError(_("This UBL XML file is not an invoice/refund file."))
            if line_vals is False:
                continue
            res_lines.append(line_vals)

        supplier = self.ubl_match_supplier(self.company_id.id, supplier_dict)
        if not supplier:
            supplier = self.ubl_supplier_to_entity(self.company_id.id, supplier_dict)

        invlines = []
        for rl in res_lines:
            account = self.ubl_match_account(self.company_id.id, supplier, rl.get('name'))
            if not account:
                raise ValueError(_(
                    "Problem to find a correct financial account for line %s." % rl.get('name')))

            vals = {'account_id': account['account_id'],
                    'vat_id': account['vat_id'],
                    'descript': rl.get('name'),
                    'net_amount': rl.get('sub_total') * sign,
                    'vat_amount': rl.get('total_vat') * sign,
                    'gross_amount': (rl.get('sub_total') + rl.get('total_vat')) * sign}
            invlines.append((0, 0, vals))
        invoice = {'name': inv_number_xpath[0].text,
                   'company_id': self.company_id.id,
                   'partner_id': supplier.id,
                   'entry': 'net',
                   'date_invoice': date_dt,
                   'line_ids': invlines}
        return invoice_model.create(invoice)
