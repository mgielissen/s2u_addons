# -*- coding: utf-8 -*-

import datetime
import re
import io
import base64
import uuid
import xlsxwriter

from odoo.tools.misc import formatLang
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class SaleTemplate(models.Model):
    _name = "s2u.sale.template"
    _description = "Sale Template"

    @api.multi
    def render_template(self, template, entity=False, address=False, contact=False, user=False, date=False, other=False):

        MONTHS = [_('januar'), _('februar'), _('march'),
                  _('april'), _('may'), _('june'),
                  _('july'), _('august'), _('september'),
                  _('october'), _('november'), _('december')]

        self.ensure_one()

        if not template:
            return False

        if date:
            dt = datetime.datetime.strptime(date, '%Y-%m-%d')
            if template:
                return template.replace('[[date]]', '%d %s %d' % (dt.day, MONTHS[dt.month - 1], dt.year))
            else:
                return date

        if entity:
            if entity.payment_term_id:
                days = entity.payment_term_id.payment_terms
                days_txt = _('Payment within %d days with a reference to the invoice number.') % days
                template = template.replace('[[terms.days]]', str(days))
                template = template.replace('[[payment_terms]]', days_txt)
            else:
                template = template.replace('[[terms.days]]', '')
                template = template.replace('[[payment_terms]]', '')
            if entity.type == 'b2b':
                template = template.replace('[[company]]', entity.name)
            else:
                template = template.replace('[[company]]', '')
        else:
            template = template.replace('[[terms.days]]', '')
            template = template.replace('[[company]]', '')

        if contact:
            template = template.replace('[[contact]]', contact.name)
        elif entity and entity.type == 'b2c':
            template = template.replace('[[contact]]', entity.name)
        else:
            template = template.replace('[[contact]]', '')
        if contact and contact.prefix:
            template = template.replace('[[prefix]]', contact.prefix)
        else:
            template = template.replace('[[prefix]]', '')
        if contact and contact.communication:
            template = template.replace('[[communication]]', contact.communication)
        else:
            template = template.replace('[[communication]]', '')

        if user:
            template = template.replace('[[user]]', user.name)

            template = template.replace('[[user]]', user.name)
            template = template.replace('[[signature]]', user.signature if user.signature else '')

            if user.partner_id and user.partner_id.email:
                template = template.replace('[[user_mail]]', user.partner_id.email)
            else:
                template = template.replace('[[user_mail]]', '')

            if user.partner_id and user.partner_id.phone:
                template = template.replace('[[user_phone]]', user.partner_id.phone)
            else:
                template = template.replace('[[user_phone]]', '')
        else:
            template = template.replace('[[user]]', '')
            template = template.replace('[[signature]]', '')
            template = template.replace('[[user_mail]]', '')
            template = template.replace('[[user_phone]]', '')

        if other:
            template = template.replace('[[short_description]]', other.get('short_description', ''))
            if other.get('so'):
                so = other.get('so')
                if so.condition == '100':
                    template = template.replace('[[payment_condition]]',
                                                _('Volledig bij beschikbaar komen van de producten'))
                if so.condition == '50/50':
                    template = template.replace('[[payment_condition]]',
                                                _('50% bij opdracht en 50% bij oplevering na decharge'))
                if so.condition == '40/40/20':
                    template = template.replace('[[payment_condition]]',
                                                _('40 procent bij opdracht, 40% bij start werkzaamheden en 20% bij oplevering na decharge'))
        else:
            template = template.replace('[[short_description]]', '')
            template = template.replace('[[payment_condition]]', '')

        return template

    name = fields.Char(string='Template', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    date_display = fields.Char(string='Date display')
    prefix_quotation = fields.Html(string='Prefix')
    postfix_quotation = fields.Html(string='Postfix')
    prefix_confirmation = fields.Html(string='Prefix')
    postfix_confirmation = fields.Html(string='Postfix')
    prefix_delivery = fields.Html(string='Prefix')
    postfix_delivery = fields.Html(string='Postfix')
    default = fields.Boolean('Default', default=False)
    prefix_invoice = fields.Html(string='Prefix')
    postfix_invoice = fields.Html(string='Postfix')
    mail_template_id = fields.Many2one('mail.template', string='Mail template', ondelete='set null')
    prefix_rma = fields.Html(string='Prefix')
    postfix_rma = fields.Html(string='Postfix')
    prefix_quotation_po = fields.Html(string='Prefix')
    postfix_quotation_po = fields.Html(string='Postfix')
    prefix_confirmation_po = fields.Html(string='Prefix')
    postfix_confirmation_po = fields.Html(string='Postfix')


class SaleLineQty(models.Model):
    _name = "s2u.sale.line.qty"
    _description = "Sale line Qty"
    _order = 'product_qty'

    @api.multi
    def name_get(self):
        # geändert 7.1.19 M.V.
        # purchase id did not exist so with recall from Bas i changed to sale_id complete.

        result = []
        for line in self:
            if line.saleline_id.product_detail:
                name = '%s:%s %s (%s)' % (
                    line.saleline_id.sale_id.name, line.saleline_id.product_id.name,
                    line.saleline_id.product_detail, line.saleline_id.sale_id.partner_id.name)
            else:
                name = '%s:%s (%s)' % (line.saleline_id.sale_id.name, line.saleline_id.product_id.name,
                                       line.saleline_id.sale_id.partner_id.name)
            result.append((line.id, name))
        return result

    @api.one
    @api.depends('price', 'qty', 'price_per', 'price_is_net', 'saleline_id.discount')
    def _compute_amount(self):

        if self.distribution:
            self.qty_distri = '%s - (%s)' % (self.qty, self.distribution)
        else:
            self.qty_distri = self.qty

        if not self.price_per or not self.price:
            self.amount = 0.0
            self.price_after_discount = 0.0
            return

        if self.price_per == 'total':
            if self.saleline_id.discount:
                self.amount = round(self.price - (self.price * self.saleline_id.discount / 100.0), 2)
                self.price_after_discount = round(self.price - (self.price * self.saleline_id.discount / 100.0), 2)
            else:
                self.amount = self.price
                self.price_after_discount = self.price
            return

        qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)
        if not qty:
            self.amount = 0.0
            self.price_after_discount = 0.0
            return

        if self.price_per == 'item':
            if self.saleline_id.discount:
                self.amount = round((qty * self.price) - ((qty * self.price) * self.saleline_id.discount / 100.0), 2)
                self.price_after_discount = round(self.price - (self.price * self.saleline_id.discount / 100.0), 2)
            else:
                self.amount = round(qty * self.price, 2)
                self.price_after_discount = self.price
            return

        if self.price_per in ['10', '100', '1000']:
            qty = qty / float(self.price_per)
            if self.saleline_id.discount:
                self.amount = round((qty * self.price) - ((qty * self.price) * self.saleline_id.discount / 100.0), 2)
                self.price_after_discount = round(self.price - (self.price * self.saleline_id.discount / 100.0), 2)
            else:
                self.amount = round(qty * self.price, 2)
                self.price_after_discount = self.price
            return

    @api.onchange('qty')
    def _onchange_qty(self):

        if not self.saleline_id.product_id:
            return False

        product = self.env[self.saleline_id.product_id.res_model].browse(self.saleline_id.product_id.res_id)
        res = product.get_product_price(self.qty, self.saleline_id.product_detail, ctx={
            'customer_id': self.saleline_id.sale_id.partner_id.id
        })

        if res:
            self.price = res['price']
            self.price_per = res.get('price_per', 'total')
            self.price_is_net = res.get('price_is_net', True)

    saleline_id = fields.Many2one('s2u.sale.line', string='Sale line', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='saleline_id.currency_id', store=True)
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
    product_qty = fields.Float(string='Qty', required=True)
    distribution = fields.Char(string='Distribution')
    price = fields.Monetary(string='Price', currency_field='currency_id')
    price_per = fields.Selection([
        ('item', 'Item'),
        ('10', 'per 10'),
        ('100', 'per 100'),
        ('1000', 'per 1000'),
        ('total', 'Total')
    ], required=True, default='item', string='Per')
    amount = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_amount,
                             readonly=True, store=True)
    for_order = fields.Boolean('Order', default=False)
    price_is_net = fields.Boolean(string='Price is VAT exclusive', default=True)
    price_after_discount = fields.Monetary(string='Price after discount', currency_field='currency_id',
                                           compute=_compute_amount, readonly=True)

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SaleLineQty, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SaleLineQty, self).write(vals)


class SaleLineLabel(models.Model):
    _name = "s2u.sale.line.label"
    _order = 'sequence'

    @api.one
    def _compute_value(self):
        self.calc_value_quotation = self.env['s2u.sale'].calc_value(self.saleline_id, self.label_id, self.display,
                                                                    self.value, so_type='quotation')
        self.calc_value_order = self.env['s2u.sale'].calc_value(self.saleline_id, self.label_id, self.display,
                                                                self.value, so_type='order')

    saleline_id = fields.Many2one('s2u.sale.line', string="Line", ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    value = fields.Text(string='Value')
    sequence = fields.Integer(string='Sequence', default=10)
    calc_value_quotation = fields.Text(string='Value', compute=_compute_value, readonly=True)
    calc_value_order = fields.Text(string='Value', compute=_compute_value, readonly=True)
    display = fields.Selection([
        ('both', 'Quotation and Order'),
        ('quotation', 'Quotation only'),
        ('order', 'Order only')
    ], required=True, default='both', string='Display')
    on_invoice = fields.Boolean(string='On invoice')


# TODO: kan worden verwijderd
class SaleLineLabelOrder(models.Model):
    _name = "s2u.sale.line.label.order"
    _order = 'sequence'

    @api.one
    def _compute_value(self):
        self.calc_value = self.env['s2u.sale'].calc_value(self.saleline_id, self.label_id, self.value,
                                                          so_type='order')

    saleline_id = fields.Many2one('s2u.sale.line', string="Line", ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    value = fields.Text(string='Value')
    sequence = fields.Integer(string='Sequence', default=10)
    calc_value = fields.Text(string='Value', compute=_compute_value, readonly=True)


class SaleLineProduct(models.Model):
    _name = "s2u.sale.line.product"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "Sale line Product"

    saleline_id = fields.Many2one('s2u.sale.line', string='Sale line', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='saleline_id.currency_id', store=True)
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
    amount = fields.Monetary(string='# Amount', currency_field='currency_id', required=True)
    for_order = fields.Boolean('Order', default=False)
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SaleLineProduct, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SaleLineProduct, self).write(vals)


class SaleLine(models.Model):
    _name = "s2u.sale.line"
    _description = "Sale line"

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            if line.product_id and line.product_detail:
                name = '%s/%s %s' % (line.sale_id.name, line.product_id.name, line.product_detail)
            elif line.product_id:
                name = '%s/%s' % (line.sale_id.name, line.product_id.name)
            else:
                name = '%s' % line.sale_id.name

            result.append((line.id, name))
        return result

    @api.one
    @api.depends('product_id', 'product_detail')
    def compute_product_available(self):

        try:
            available = self.env['s2u.warehouse.available'].search([('product_id', '=', self.product_id.id),
                                                                    ('product_detail', '=', self.product_detail)])
            if available:
                self.product_available = available[0].qty_available
            else:
                self.product_available = 0.0
        except:
            self.product_available = 0.0

    @api.one
    @api.depends('qty_ids.qty', 'qty_ids.for_order', 'qty_ids.amount', 'qty_ids.price')
    def _compute_qty(self):

        products_amount = 0.0
        for product in self.product_ids:
            products_amount += product.amount
        if self.discount:
            products_amount = round(products_amount - (products_amount * self.discount / 100.0), 2)

        for qty in self.qty_ids:
            if qty.for_order:
                # base is the total amount without the total amount of the product_ids
                self.amount_base = qty.amount
                self.amount = qty.amount + products_amount
                self.qty = qty.qty
                self.distribution = qty.distribution
                self.product_qty = qty.product_qty
                self.price = qty.price
                self.price_per = qty.price_per
                self.for_order = True
                self.price_is_net = qty.price_is_net
                return
        if self.qty_ids:
            self.amount_base = self.qty_ids[0].amount
            self.amount = self.qty_ids[0].amount + products_amount
            self.qty = self.qty_ids[0].qty
            self.distribution = self.qty_ids[0].distribution
            self.product_qty = self.qty_ids[0].product_qty
            self.price = self.qty_ids[0].price
            self.price_per = self.qty_ids[0].price_per
            self.for_order = False
            self.price_is_net = self.qty_ids[0].price_is_net
        else:
            self.amount_base = 0.0
            self.amount = 0.0
            self.qty = ''
            self.distribution = ''
            self.product_qty = 0.0
            self.price = 0.0
            self.price_per = 'item'
            self.for_order = False
            self.price_is_net = True

    @api.onchange('product_id')
    def onchange_product_id(self):

        if self.product_id:
            if not self.qty_ids:
                vals = {
                    'qty': '1 stuks',
                }
                product = self.env[self.product_id.res_model].browse(self.product_id.res_id)
                res = product.get_product_price('1 stuks', self.product_detail, ctx={
                    'customer_id': self._context['customer_id']
                })
                if res:
                    vals['price'] = res['price']
                    vals['price_per'] = res.get('price_per', 'total')
                    vals['amount'] = res.get('total_amount', res['price'])
                    vals['price_is_net'] = res.get('price_is_net', True)
                    if res.get('discount'):
                        self.discount = res['discount']
                self.qty_ids = [(0, 0, vals)]
            else:
                for qty in self.qty_ids:
                    product = self.env[self.product_id.res_model].browse(self.product_id.res_id)
                    res = product.get_product_price(qty.qty, self.product_detail, ctx={
                        'customer_id': self._context['customer_id']
                    })
                    if res:
                        qty.price = res['price']
                        qty.price_per = res.get('price_per', 'total')
                        qty.amount = res.get('total_amount', res['price'])
                        qty.price_is_net = res.get('price_is_net', True)
                        if res.get('discount'):
                            self.discount = res['discount']
                    else:
                        qty.price = 0.0
                        qty.price_per = 'item'
                        qty.amount = 0.0
                        qty.price_is_net = True
                        self.discount = 0.0

    @api.onchange('product_detail')
    def onchange_product_detail(self):

        if not self.product_id:
            return

        try:
            detail = self.env[self.product_id.res_model].check_product_detail(self.product_detail)
        except:
            detail = ''
        self.product_detail = detail

    @api.one
    def _compute_vat(self):

        if not self.product_id:
            self.vat_id = False
            return
        try:
            product = self.env[self.product_id.res_model].search([('id', '=', self.product_id.res_id)])
        except:
            product = False

        if product:
            if self.sale_id.partner_id.vat_sell_id:
                self.vat_id = self.sale_id.partner_id.vat_sell_id
            else:
                if hasattr(product, 'get_so_vat'):
                    self.vat_id = product.get_so_vat()
                else:
                    self.vat_id = False
        else:
            self.vat_id = False

    sale_id = fields.Many2one('s2u.sale', string='Sale', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='sale_id.currency_id', store=True)
    distribution = fields.Char(string='Distribution')
    product_available = fields.Float(string='Available', readonly=True, compute='compute_product_available')
    po_line_id = fields.Many2one('s2u.purchase.line', string='Purchase', ondelete='set null')
    vat_id = fields.Many2one('s2u.account.vat', string='VAT', compute=_compute_vat, readonly=True)

    for_order = fields.Boolean('Order', compute=_compute_qty, readonly=True)
    qty_ids = fields.One2many('s2u.sale.line.qty', 'saleline_id', string='Quotation', copy=True)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True)
    product_detail = fields.Char(string='Details')
    amount = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_qty,
                             readonly=True)
    amount_base = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_qty,
                                  readonly=True)
    qty = fields.Char(string='Qty', compute=_compute_qty, readonly=True)
    distribution = fields.Char(string='Distribution', compute=_compute_qty, readonly=True)
    product_qty = fields.Float(string='Qty', compute=_compute_qty, readonly=True)
    price = fields.Monetary(string='Price', currency_field='currency_id', compute=_compute_qty, readonly=True)
    price_is_net = fields.Boolean(string='Price is netto', compute=_compute_qty, readonly=True)
    price_per = fields.Selection([
        ('item', 'Item'),
        ('10', 'per 10'),
        ('100', 'per 100'),
        ('1000', 'per 1000'),
        ('total', 'Total')
    ], string='Per', compute=_compute_qty, readonly=True)
    label_ids = fields.One2many('s2u.sale.line.label', 'saleline_id', string='Quotation', copy=True)
    project = fields.Char(string='Project')
    date_delivery = fields.Date(string='Date delivery', copy=False)
    product_ids = fields.One2many('s2u.sale.line.product', 'saleline_id', string='Quotation', copy=True)
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')
    discount = fields.Float(string='Discount', default='0.0')

    @api.model
    def create(self, vals):

        product = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
        vals['product_detail'] = self.env[product.res_model].check_product_detail(vals.get('product_detail', ''),
                                                                                  product_name=product.name)

        return super(SaleLine, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('product_id', False):
            baseproduct = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
            res_model = baseproduct.res_model
            product_name = baseproduct.name
        else:
            res_model = self.product_id.res_model
            product_name = self.product_id.name

        if 'product_detail' in vals:
            product_detail = vals['product_detail']
            vals['product_detail'] = self.env[res_model].check_product_detail(product_detail,
                                                                              product_name=product_name)

        return super(SaleLine, self).write(vals)


class SaleDetailed(models.Model):
    _name = "s2u.sale.detailed"
    _order = 'sequence'

    sale_id = fields.Many2one('s2u.sale', string='Sale', required=True, ondelete='cascade')
    detailed_label = fields.Char(string='Label', required=True)
    detailed_info = fields.Text(string='Details')
    sequence = fields.Integer(string='Sequence', default=10)


class SaleDeliveryAddress(models.Model):
    _name = "s2u.sale.delivery.address"

    @api.onchange('delivery_partner_id')
    def _onchange_delivery_partner(self):
        if self.delivery_partner_id:
            delivery = self.delivery_partner_id.prepare_delivery()
            self.delivery_address = delivery

            address = self.delivery_partner_id.get_physical()
            if address and address.country_id:
                self.delivery_country_id = address.country_id
            else:
                self.delivery_country_id = False

            if self.delivery_partner_id.tinno:
                self.delivery_tinno = self.delivery_partner_id.tinno
            else:
                self.delivery_tinno = False
            if self.delivery_partner_id.lang:
                self.delivery_lang = self.delivery_partner_id.lang
            else:
                self.delivery_lang = False

    @api.onchange('delivery_contact_id')
    def _onchange_delivery_contact(self):
        if self.delivery_contact_id:
            delivery = self.delivery_contact_id.display_company + '\n'
            if self.delivery_contact_id.prefix:
                delivery += '%s\n' % self.delivery_contact_id.prefix
            else:
                delivery += '%s\n' % self.delivery_contact_id.name
            if self.delivery_contact_id.address_id:
                if self.contact_id.address_id.address:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.address
                if self.delivery_contact_id.address_id.zip and self.delivery_contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.delivery_contact_id.address_id.zip, self.delivery_contact_id.address_id.city)
                if self.delivery_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.country_id.name
            elif self.delivery_partner_id:
                address = self.delivery_partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    @api.onchange('delivery_delivery_id')
    def _onchange_delivery_delivery(self):
        if self.delivery_delivery_id:
            self.delivery_address = self.delivery_delivery_id.delivery_address
            if self.delivery_delivery_id.delivery_country_id:
                self.delivery_country_id = self.delivery_delivery_id.delivery_country_id
            else:
                self.delivery_country_id = False
            if self.delivery_delivery_id.delivery_tinno:
                self.delivery_tinno = self.delivery_delivery_id.delivery_tinno
            else:
                self.delivery_tinno = False
            if self.delivery_delivery_id.delivery_lang:
                self.delivery_lang = self.delivery_delivery_id.delivery_lang
            else:
                self.delivery_lang = False

    @api.onchange('load_entity_id')
    def _onchange_load_entity(self):
        if self.load_entity_id:
            loading = self.load_entity_id.prepare_delivery()
            self.load_address = loading

    @api.model
    def _default_delivery_country(self):
        domain = [
            ('code', '=', 'NL'),
        ]
        return self.env['res.country'].search(domain, limit=1)

    @api.model
    def _delivery_lang_get(self):
        languages = self.env['res.lang'].search([])
        return [(language.code, language.name) for language in languages]

    sale_id = fields.Many2one('s2u.sale', string='Sale', required=True, ondelete='cascade')
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type')
    delivery_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact')
    delivery_address = fields.Text(string='Address')
    load_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type')
    load_entity_id = fields.Many2one('s2u.crm.entity', string='Loading entity')
    load_address = fields.Text(string='Loading address')
    trailer_no = fields.Char(string='Trailer-No.')
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland', default=_default_delivery_country)
    delivery_tinno = fields.Char('TIN no.')
    delivery_lang = fields.Selection(_delivery_lang_get, string='Language')
    delivery_delivery_id = fields.Many2one('s2u.crm.entity.delivery', string='Delivery')


class Sale(models.Model):
    _name = "s2u.sale"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Sale"
    _order = "id desc"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Sale, self)._track_subtype(init_values)

    def userdef_calc_value(self, so_line, label, keyword, display, value, po_type):

        return False

    def calc_value(self, so_line, label, display, value, so_type='quotation'):

        MONTHS = [_('januar'), _('februar'), _('march'),
                  _('april'), _('may'), _('june'),
                  _('july'), _('august'), _('september'),
                  _('october'), _('november'), _('december')]

        PRICE_PER = {
            'item': _('per Item'),
            '10': _('per 10'),
            '100': _('per 100'),
            '1000': _('per 1000'),
            'total': ''
        }

        if not value:
            return ''

        if display == 'quotation' and so_type != 'quotation':
            return ''
        if display == 'order' and so_type != 'order':
            return ''
        if display == 'invoice' and so_type != 'invoice':
            return ''

        match = re.search(r'.*\{\{(?P<value>.+)\}\}.*', value)
        if not match:
            return value

        userdef = self.userdef_calc_value(so_line, label, match.group('value'), display, value, so_type)
        if userdef:
            return userdef

        if match.group('value') == 'staffel':
            if so_line.qty_ids and len(so_line.qty_ids) > 1:
                return True
            return False

        if match.group('value') == 'order-number':
            return value.replace('{{order-number}}', so_line.sale_id.name if so_line.sale_id.name else '')

        if match.group('value') == 'reference':
            return value.replace('{{reference}}', so_line.sale_id.reference if so_line.sale_id.reference else '')

        if match.group('value') == 'customer_code':
            return value.replace('{{customer_code}}', so_line.sale_id.customer_code if so_line.sale_id.customer_code else '')

        if match.group('value') == 'distribution':
            return value.replace('{{distribution}}', so_line.distribution if so_line.distribution else '')

        if match.group('value') == 'project':
            project = ''
            if so_line.project:
                project = so_line.project
            elif so_line.sale_id.project:
                project = so_line.sale_id.project
            return value.replace('{{project}}', project)

        if match.group('value') == 'qty':
            qty_value = so_line.qty

            return value.replace('{{qty}}', qty_value)

        if match.group('value') == 'qty-dist':
            if so_line.distribution:
                qty_value = '%s - (%s)' % (so_line.qty, so_line.distribution)
            else:
                qty_value = so_line.qty

            return value.replace('{{qty-dist}}', qty_value)

        if match.group('value') == 'dist':
            dist = so_line.distribution if so_line.distribution else ''
            return value.replace('{{dist}}', dist)

        if match.group('value') == 'label-amount':
            tot_amount = 0.0
            for product in so_line.product_ids:
                if product.label_id.id == label.id:
                    tot_amount += product.amount

            return value.replace('{{label-amount}}',
                                 formatLang(self.env, tot_amount, currency_obj=so_line.currency_id))

        if match.group('value') == 'total-amount':
            if value == '{{total-amount}}':
                return '%s %s' % (formatLang(self.env, so_line.price, currency_obj=so_line.currency_id),
                                             PRICE_PER[so_line.price_per])
            else:
                return value.replace('{{total-amount}}',
                                     formatLang(self.env, so_line.price, currency_obj=so_line.currency_id))

        if match.group('value') == 'delivery':
            if hasattr(so_line.sale_id, 'delivery_address'):
                if so_line.sale_id.delivery_address:
                    return value.replace('{{delivery}}', so_line.sale_id.delivery_address)
            if hasattr(so_line.sale_id, 'dropshipping_address'):
                if so_line.sale_id.dropshipping_address:
                    return value.replace('{{delivery}}', so_line.sale_id.dropshipping_address)
            return ''

        if match.group('value') == 'payment-terms':
            if so_line.sale_id.invoice_partner_id and so_line.sale_id.invoice_partner_id.payment_term_id:
                return value.replace('{{payment-terms}}', so_line.sale_id.invoice_partner_id.payment_term_id.name)
            return ''

        if match.group('value') == 'date-delivery':
            if hasattr(so_line.sale_id, 'date_delivery') and so_line.sale_id.date_delivery:
                date_delivery = datetime.datetime.strptime(so_line.sale_id.date_delivery, "%Y-%m-%d")
                date_delivery = '%d %s %d' % (date_delivery.day, MONTHS[date_delivery.month - 1], date_delivery.year)
                return value.replace('{{date-delivery}}', date_delivery)
            else:
                return value.replace('{{date-delivery}}', '')

        if match.group('value') == 'date-artwork':
            if hasattr(so_line.sale_id, 'date_artwork') and so_line.sale_id.date_artwork:
                date_artwork = datetime.datetime.strptime(so_line.sale_id.date_artwork, "%Y-%m-%d")
                date_artwork = '%d %s %d' % (date_artwork.day, MONTHS[date_artwork.month - 1], date_artwork.year)
                return value.replace('{{date-artwork}}', date_artwork)
            else:
                return value.replace('{{date-artwork}}', '')

        return value

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for sale in self:
            if sale.type == 'b2b':
                if sale.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b customer!'))
                if sale.contact_id and sale.contact_id.entity_id != sale.partner_id:
                    raise ValueError(_('Contact does not belong to the selected customer!'))
                if sale.address_id and sale.address_id.entity_id != sale.partner_id:
                    raise ValueError(_('Address does not belong to the selected customer!'))
            else:
                if sale.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c customer!'))

    @api.model
    def _new_quotation_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.sale[quotation]')])
        if not exists:
            raise ValueError(_('Sequence for creating quotation not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.sale')])
        if not exists:
            raise ValueError(_('Sequence for creating SO not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.model
    def _default_template(self):

        return self.env['s2u.sale.template'].search([('default', '=', True)], limit=1)

    @api.model
    def _default_delivery_country(self):
        domain = [
            ('code', '=', 'NL'),
        ]
        return self.env['res.country'].search(domain, limit=1)

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.onchange('invoice_is_sale_address')
    def _onchange_invoice_is_sale_address(self):

        if self.invoice_is_sale_address:
            return
        if not self.partner_id:
            return

        self.invoice_type = self.type
        self.invoice_partner_id = self.partner_id
        address = self.partner_id.get_postal()
        if not address:
            address = self.partner_id.get_physical()
        if address:
            self.invoice_address_id = address
        else:
            self.invoice_address_id = False

    @api.onchange('delivery_is_sale_address')
    def _onchange_delivery_is_sale_address(self):

        if self.delivery_is_sale_address:
            return
        if not self.partner_id:
            return

        self.delivery_type = self.type
        self.delivery_partner_id = self.partner_id

    @api.onchange('invoice_contact_id')
    def _onchange_invoice_contact(self):
        if self.invoice_contact_id:
            if self.invoice_contact_id.address_id:
                self.invoice_address_id = self.invoice_contact_id.address_id

    @api.onchange('delivery_partner_id')
    def _onchange_delivery_partner(self):
        if self.delivery_partner_id:
            delivery = self.delivery_partner_id.prepare_delivery()
            self.delivery_address = delivery

            address = self.delivery_partner_id.get_physical()
            if address and address.country_id:
                self.delivery_country_id = address.country_id
            else:
                self.delivery_country_id = False

            if self.delivery_partner_id.tinno:
                self.delivery_tinno = self.delivery_partner_id.tinno
            else:
                self.delivery_tinno = False

    @api.onchange('delivery_contact_id')
    def _onchange_delivery_contact(self):
        if self.delivery_contact_id:
            delivery = self.delivery_contact_id.display_company + '\n'
            if self.delivery_contact_id.prefix:
                delivery += '%s\n' % self.delivery_contact_id.prefix
            else:
                delivery += '%s\n' % self.delivery_contact_id.name
            if self.delivery_contact_id.address_id:
                if self.delivery_contact_id.address_id.address:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.address
                if self.delivery_contact_id.address_id.zip and self.delivery_contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.delivery_contact_id.address_id.zip, self.delivery_contact_id.address_id.city)
                if self.delivery_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.country_id.name
            elif self.delivery_partner_id:
                address = self.delivery_partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    @api.onchange('delivery_delivery_id')
    def _onchange_delivery_delivery(self):
        if self.delivery_delivery_id:
            self.delivery_address = self.delivery_delivery_id.delivery_address
            if self.delivery_delivery_id.delivery_country_id:
                self.delivery_country_id = self.delivery_delivery_id.delivery_country_id
            else:
                self.delivery_country_id = False
            if self.delivery_delivery_id.delivery_tinno:
                self.delivery_tinno = self.delivery_delivery_id.delivery_tinno
            else:
                self.delivery_tinno = False
            if self.delivery_delivery_id.delivery_lang:
                self.delivery_lang = self.delivery_delivery_id.delivery_lang
            else:
                self.delivery_lang = False

    @api.model
    def create(self, vals):

        sale = super(Sale, self).create(vals)
        return sale

    @api.multi
    def write(self, vals):

        res = super(Sale, self).write(vals)
        return res

    @api.one
    def unlink(self):

        for order in self:
            if order.state != 'draft':
                raise ValidationError(_('You can not delete a confirmed order!'))

        res = super(Sale, self).unlink()

        return res

    @api.multi
    def copy(self, default=None):

        new_sale = super(Sale, self).copy(default=default)

        return new_sale

    @api.multi
    def action_quotation(self):
        self.ensure_one()

        wiz_form = self.env.ref('s2usale.wizard_action_so_quotation_view', False)
        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
        )
        return {
            'name': _('Make quotation'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2usale.action.so.quotation',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def do_quotation(self):
        # Use this method from other processes where you need to confirm orders

        self.ensure_one()

        invoice_vals = {}
        if self.invoice_is_sale_address:
            invoice_vals = {
                'invoice_type': self.type,
                'invoice_partner_id': self.partner_id.id,
                'invoice_contact_id': self.contact_id.id if self.contact_id else False,
                'invoice_address_id': self.address_id.id if self.address_id else False
            }

        delivery_vals = {}
        if self.delivery_is_sale_address:
            delivery = self.partner_id.prepare_delivery(address=self.address_id, contact=self.contact_id)

            delivery_vals = {
                'delivery_type': self.type,
                'delivery_partner_id': self.partner_id.id,
                'delivery_contact_id': self.contact_id.id if self.contact_id else False,
                'delivery_address': delivery,
            }

            if self.address_id:
                if self.address_id.country_id:
                    delivery_vals['delivery_country_id'] = self.address_id.country_id.id
            elif self.partner_id.country_id:
                delivery_vals['delivery_country_id'] = self.partner_id.country_id.id

            if self.partner_id.tinno:
                delivery_vals['delivery_tinno'] = self.partner_id.tinno

        if self.name == 'Concept':
            name_quot = self._new_number()
            vals = {
                'state': 'quot',
                'date_qu': fields.Date.context_today(self),
                'name': name_quot,
                'name_quot': name_quot
            }
            vals.update(invoice_vals)
            vals.update(delivery_vals)
            self.write(vals)
        else:
            vals = {
                'date_qu': fields.Date.context_today(self),
                'state': 'quot'
            }
            vals.update(invoice_vals)
            vals.update(delivery_vals)
            self.write(vals)

        return True

    @api.multi
    def overrule_action_order(self):
        self.ensure_one()
        return False

    @api.multi
    def do_order(self):
        # Use this method from other processes where you need to confirm orders

        self.ensure_one()

        order = 0
        for line in self.line_ids:
            if line.for_order:
                order += 1
        if not order:
            for line in self.line_ids:
                if line.qty_ids:
                    line.qty_ids[0].write({
                        'for_order': True
                    })
                    order += 1
            self.invalidate_cache()
        if not order and not self.overrule_action_order():
            return False

        self.write({
            'state': 'order',
            'date_so': fields.Date.context_today(self)
        })

        return True

    @api.multi
    def do_payment(self):
        # Use this method from other processes where you need to confirm orders

        self.ensure_one()

        order = 0
        for line in self.line_ids:
            if line.for_order:
                order += 1
        if not order:
            for line in self.line_ids:
                if line.qty_ids:
                    line.qty_ids[0].write({
                        'for_order': True
                    })
                    order += 1
            self.invalidate_cache()
        if not order and not self.overrule_action_order():
            return False

        self.write({
            'state': 'payment',
            'date_so': fields.Date.context_today(self)
        })

        return True

    @api.multi
    def action_order(self):
        self.ensure_one()

        wiz_form = self.env.ref('s2usale.wizard_action_so_order_view', False)
        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
        )
        return {
            'name': _('Make order'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2usale.action.so.order',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def action_confirm(self):

        self.ensure_one()

        # if button "Order" is not used, we call the do_order method
        if self.state == 'quot':
            self.do_order()

        order = 0
        for line in self.line_ids:
            if line.for_order:
                order += 1
        if not order and not self.overrule_action_order():
            raise UserError(
                _('There are no lines marked as order, please enter some lines and mark them for the order.'))

        wiz_form = self.env.ref('s2usale.wizard_action_so_confirm_view', False)
        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
        )
        return {
            'name': _('Confirm order'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2usale.action.so.confirm',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def before_confirm(self):
        # Use this method to override from other modules
        # This method is called from s2usale.do_confirm and s2usale.action.so.confirm.do_confirm

        self.ensure_one()
        return True

    @api.multi
    def do_confirm(self):
        # Use this method from other processes where you need to confirm orders

        self.ensure_one()

        order = 0
        for line in self.line_ids:
            if line.for_order:
                order += 1
        if not order and not self.overrule_action_order():
            return False

        self.before_confirm()

        if self.invoicing not in ['dropshipping']:
            if self.delivery_ids:
                for delivery in self.delivery_ids:
                    vals = {
                        'load_type': delivery.load_type,
                        'delivery_entity_id': delivery.delivery_partner_id.id,
                        'delivery_contact_id': delivery.delivery_contact_id.id if delivery.delivery_contact_id else False,
                        'delivery_address': delivery.delivery_address,
                        'delivery_country_id': delivery.delivery_partner_id.country_id.id if delivery.delivery_partner_id.country_id else False,
                        'delivery_tinno': delivery.delivery_partner_id.tinno,
                        'delivery_lang': delivery.delivery_partner_id.lang,
                        'date_delivery': self.date_delivery,
                        'project': self.project,
                        'reference': self.reference,
                        'customer_code': self.customer_code
                    }
                    if delivery.load_entity_id:
                        vals['load_entity_id'] = delivery.load_entity_id.id
                    if delivery.load_address:
                        vals['load_address'] = delivery.load_address
                    if delivery.trailer_no:
                        vals['trailer_no'] = delivery.trailer_no
                    self.create_outgoing(add_values=vals, devider=len(self.delivery_ids))
            else:
                self.create_outgoing()

        self.write({
            'state': 'run',
            'date_confirm': fields.Date.context_today(self)
        })

        # always create the invoice
        if self.invoicing == 'confirm':
            self.create_invoice()

        self.sale_is_completed()

        return True

    @api.multi
    def action_cancel(self):
        self.ensure_one()

        wiz_form = self.env.ref('s2usale.wizard_action_so_cancel_view', False)
        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
        )
        return {
            'name': _('Cancel order'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2usale.action.so.cancel',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }


    @api.multi
    def do_undo_other_stuff(self):

        self.ensure_one()

        return True

    @api.multi
    def action_undo(self):

        todo_model = self.env['s2u.warehouse.outgoing.todo']
        invline_model = self.env['s2u.account.invoice.line']

        self.ensure_one()

        todos = todo_model.search([('sale_id', '=', self.id)])
        outgoings = []
        for t in todos:
            if t.outgoing_id.state != 'draft':
                raise UserError(
                    _('Outgoing shipment [%s] already confirmed! Back to concept not possible.' % t.outgoing_id.name))
            outgoings.append(t.outgoing_id)

        invlines = invline_model.search([('sale_id', '=', self.id)])
        invoices = []
        for t in invlines:
            if t.invoice_id.state not in ['draft', 'reopen']:
                raise UserError(
                    _('Invoice [%s] already confirmed! Back to concept not possible.' % t.invoice_id.name))
            invoices.append(t.invoice_id)

        outgoings = list(set(outgoings))
        invoices = list(set(invoices))

        self.do_undo_other_stuff()

        todos.unlink()

        self.write({
            'state': 'draft',
            'date_qu': False,
            'date_so': False,
            'date_confirm': False
        })

        for o in outgoings:
            if not o.todo_ids:
                o.unlink()

        for i in invoices:
            i.unlink()

    @api.multi
    def action_view_invoice(self):
        invlines = self.env['s2u.account.invoice.line'].search([('sale_id', '=', self.id)])
        invoice_ids = [l.invoice_id.id for l in invlines]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice').read()[0]
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('s2uaccount.invoice_form').id, 'form')]
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_outgoing(self):
        todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', self.id)])
        outgoing_ids = [l.outgoing_id.id for l in todolines]
        outgoing_ids = list(set(outgoing_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_outgoing').read()[0]
        if len(outgoing_ids) > 1:
            action['domain'] = [('id', 'in', outgoing_ids)]
        elif len(outgoing_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_outgoing_form').id, 'form')]
            action['res_id'] = outgoing_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_excel(self):

        self.ensure_one()

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True
        })

        worksheet = workbook.add_worksheet()
        bold = workbook.add_format({'bold': True})

        worksheet.write('A1', 'Company', bold)
        worksheet.write('B1', 'Contact', bold)
        worksheet.write('C1', 'Address', bold)
        worksheet.write('D1', 'ZIP', bold)
        worksheet.write('E1', 'City', bold)
        worksheet.write('F1', 'Country', bold)
        worksheet.write('G1', 'Communication', bold)
        worksheet.write('H1', 'Prefix', bold)
        worksheet.write('I1', 'Image', bold)
        worksheet.write('J1', 'SO', bold)
        worksheet.write('K1', 'Descript', bold)

        if self.type == 'b2b':
            worksheet.write('A2', self.partner_id.name)
            if self.contact_id:
                if self.contact_id.prefix:
                    worksheet.write('B2', self.contact_id.prefix)
                else:
                    worksheet.write('B2', self.contact_id.name)
                if self.contact_id.communication:
                    worksheet.write('G2', self.contact_id.communication)
                if self.contact_id.prefix:
                    worksheet.write('H2', self.contact_id.prefix)
            if self.address_id:
                worksheet.write('C2', self.address_id.address)
                worksheet.write('D2', self.address_id.zip)
                worksheet.write('E2', self.address_id.city)
                worksheet.write('F2', self.address_id.country_id.name)
        else:
            if self.partner_id.prefix:
                worksheet.write('B2', self.partner_id.prefix)
            else:
                worksheet.write('B2', self.partner_id.name)
            worksheet.write('C2', self.partner_id.address)
            worksheet.write('D2', self.partner_id.zip)
            worksheet.write('E2', self.partner_id.city)
            worksheet.write('F2', self.partner_id.country_id.name)
            if self.partner_id.communication:
                worksheet.write('G2', self.partner_id.communication)
            if self.partner_id.prefix:
                worksheet.write('H2', self.partner_id.prefix)

        if self.partner_id.image and self.partner_id.image_fname:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            image_url = '%s/crm/logo/%d/%s' % (base_url, self.partner_id.id, self.partner_id.entity_code)
            worksheet.write('I2', image_url)

        worksheet.write('J2', self.name)
        worksheet.write('K2', self.reference if self.reference else '')

        workbook.close()
        xlsx_data = output.getvalue()

        values = {
            'name': "%s.xlsx" % self.name,
            'datas_fname': '%s.xlsx' % self.name,
            'res_model': 'ir.ui.view',
            'res_id': False,
            'type': 'binary',
            'public': False,
            'datas': base64.b64encode(xlsx_data)
        }

        attachment_id = self.env['ir.attachment'].sudo().create(values)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        download_url = '/web/content/' + str(attachment_id.id) + '?download=True'

        return {
            'name': 'Excel for merge',
            'type': 'ir.actions.act_url',
            "url": str(base_url) + str(download_url),
            'target': 'self',
        }

    @api.multi
    def build_detailed(self, saleline):
        detailed = []
        for label in saleline.label_ids:
            if not label.on_invoice:
                continue

            vals = {
                'saleline_id': saleline.id,
                'label_id': label.label_id.id,
                'value': label.value,
                'sequence': label.sequence
            }

            detailed.append((0, 0, vals))

        return detailed

    @api.multi
    def manage_invoice_lines(self, lines, condition):

        return True

    @api.multi
    def skip_for_invoice(self, line):
        # to be used for inheritance in other modules
        return False

    @api.multi
    def create_invoice(self):

        invoice_model = self.env['s2u.account.invoice']

        self.ensure_one()

        if self.invoicing in ['complete', 'dropshipping', 'confirm']:
            conditions = self.condition.split('/')
        else:
            conditions = ['100']
        condition_counter = 0

        for condition in conditions:
            condition_counter += 1
            lines = []
            for t in self.line_ids:
                if self.skip_for_invoice(t):
                    continue

                if not t.for_order:
                    continue

                product = self.env[t.product_id.res_model].browse(t.product_id.res_id)

                if t.project:
                    name = t.project
                else:
                    name = t.product_id.name
                    if t.product_detail:
                        name = '%s %s' % (name, t.product_detail)

                account = product.get_so_account()
                if not account:
                    raise UserError(_('No financial account is defined for product %s!' % name))

                detailed = self.build_detailed(t)

                if t.price_is_net:
                    vals = {
                        'net_amount': round(t.amount_base * float(condition) / 100.0, 2),
                        'account_id': account.id,
                        'descript': name,
                        'qty': t.qty,
                        'net_price': t.price,
                        'price_per': t.price_per,
                        'discount': t.discount,
                        'sale_id': self.id,
                        'saleline_id': t.id,
                        'saledetailed_ids': detailed
                    }

                    if self.invoice_partner_id.vat_sell_id:
                        vals['vat_id'] = self.invoice_partner_id.vat_sell_id.id
                        vals['vat_amount'] = self.invoice_partner_id.vat_sell_id.calc_vat_from_netto_amount(
                            vals['net_amount'])
                        vals['gross_amount'] = self.invoice_partner_id.vat_sell_id.calc_gross_amount(
                            vals['net_amount'], vals['vat_amount'])
                    else:
                        vat = product.get_so_vat()
                        if vat:
                            vals['vat_id'] = vat.id
                            vals['vat_amount'] = vat.calc_vat_from_netto_amount(
                                vals['net_amount'])
                            vals['gross_amount'] = vat.calc_gross_amount(
                                vals['net_amount'], vals['vat_amount'])
                        elif account.vat_id:
                            vals['vat_id'] = account.vat_id.id
                            vals['vat_amount'] = account.vat_id.calc_vat_from_netto_amount(
                                vals['net_amount'])
                            vals['gross_amount'] = account.vat_id.calc_gross_amount(
                                vals['net_amount'], vals['vat_amount'])
                        else:
                            raise UserError(_('No VAT is defined for product %s!' % name))
                else:
                    vals = {
                        'gross_amount': round(t.amount_base * float(condition) / 100.0, 2),
                        'account_id': account.id,
                        'descript': name,
                        'qty': t.qty,
                        'price_per': t.price_per,
                        'discount': t.discount,
                        'sale_id': self.id,
                        'saleline_id': t.id,
                        'saledetailed_ids': detailed
                    }

                    if self.invoice_partner_id.vat_sell_id:
                        vals['vat_id'] = self.invoice_partner_id.vat_sell_id.id
                        vals['vat_amount'] = self.invoice_partner_id.vat_sell_id.calc_vat_from_gross_amount(
                            vals['gross_amount'])
                        vals['net_amount'] = self.invoice_partner_id.vat_sell_id.calc_netto_amount(
                            vals['gross_amount'], vals['vat_amount'])
                        vat_price = self.invoice_partner_id.vat_sell_id.calc_vat_from_gross_amount(t.price)
                        vals['net_price'] = t.price - vat_price
                    else:
                        vat = product.get_so_vat()
                        if vat:
                            vals['vat_id'] = vat.id
                            vals['vat_amount'] = vat.calc_vat_from_gross_amount(
                                vals['gross_amount'])
                            vals['net_amount'] = vat.calc_netto_amount(
                                vals['gross_amount'], vals['vat_amount'])
                            vat_price = vat.calc_vat_from_gross_amount(t.price)
                            vals['net_price'] = t.price - vat_price
                        elif account.vat_id:
                            vals['vat_id'] = account.vat_id.id
                            vals['vat_amount'] = account.vat_id.calc_vat_from_gross_amount(
                                vals['gross_amount'])
                            vals['net_amount'] = account.vat_id.calc_netto_amount(
                                vals['gross_amount'], vals['vat_amount'])
                            vat_price = account.vat_id.calc_vat_from_gross_amount(t.price)
                            vals['net_price'] = t.price - vat_price
                        else:
                            raise UserError(_('No VAT is defined for product %s!' % name))

                if t.analytic_id:
                    vals['analytic_id'] = t.analytic_id.id

                lines.append((0, 0, vals))

                for p in t.product_ids:
                    product = self.env[p.product_id.res_model].browse(p.product_id.res_id)
                    find_label = self.env['s2u.sale.line.label'].search([('saleline_id', '=', t.id),
                                                                         ('label_id', '=', p.label_id.id)], limit=1)
                    if find_label and find_label.value:
                        match = re.search(r'.*\{\{(?P<value>.+)\}\}.*', find_label.value)
                        if match:
                            name = find_label.value.replace('{{%s}}' % match.group('value'), '').strip()
                        else:
                            name = find_label.value
                    else:
                        name = p.product_id.name
                        if p.product_detail:
                            name = '%s %s' % (name, p.product_detail)

                    account = product.get_so_account()
                    if not account:
                        raise UserError(_('No financial account is defined for product %s!' % name))

                    vals = {
                        'net_amount': round(p.amount * float(condition) / 100.0, 2),
                        'account_id': account.id,
                        'descript': name,
                        'qty': p.qty,
                        'net_price': p.amount,
                        'sale_id': self.id,
                        'price_per': 'total'
                    }

                    if t.analytic_id:
                        vals['analytic_id'] = t.analytic_id.id

                    if self.invoice_partner_id.vat_sell_id:
                        vals['vat_id'] = self.invoice_partner_id.vat_sell_id.id
                        vals['vat_amount'] = self.invoice_partner_id.vat_sell_id.calc_vat_from_netto_amount(
                            vals['net_amount'])
                        vals['gross_amount'] = self.invoice_partner_id.vat_sell_id.calc_gross_amount(
                            vals['net_amount'], vals['vat_amount'])
                    else:
                        vat = product.get_so_vat()
                        if vat:
                            vals['vat_id'] = vat.id
                            vals['vat_amount'] = vat.calc_vat_from_netto_amount(
                                vals['net_amount'])
                            vals['gross_amount'] = vat.calc_gross_amount(
                                vals['net_amount'], vals['vat_amount'])
                        elif account.vat_id:
                            vals['vat_id'] = account.vat_id.id
                            vals['vat_amount'] = account.vat_id.calc_vat_from_netto_amount(
                                vals['net_amount'])
                            vals['gross_amount'] = account.vat_id.calc_gross_amount(
                                vals['net_amount'], vals['vat_amount'])
                        else:
                            raise UserError(_('No VAT is defined for product %s!' % name))

                    lines.append((0, 0, vals))

            self.manage_invoice_lines(lines, condition)

            if lines:
                if self.name:
                    ref = self.name
                else:
                    ref = ''
                if self.reference:
                    if ref:
                        ref = '%s / %s' % (ref, self.reference)
                    else:
                        ref = self.reference

                if len(conditions) > 1:
                    if condition_counter == 1:
                        ref = '%s | %s%% %s' % (ref, condition, _('On confirmation'))
                    elif condition_counter == len(conditions):
                        ref = '%s | %s%% %s' % (ref, condition, _('On completion'))
                    else:
                        ref = '%s | %s%% %s' % (ref, condition, _('Part payment'))

                invdata = {
                    'reference': ref,
                    'customer_code': self.customer_code,
                    'line_ids': lines,
                    'date_invoice': fields.Date.context_today(self),
                    'date_financial': fields.Date.context_today(self),
                    'project': self.project if self.project else False
                }

                if self.currency_id:
                    invdata['currency_id'] = self.currency_id.id

                if self.invoice_is_sale_address:
                    invdata['type'] = self.type
                    invdata['partner_id'] = self.partner_id.id
                    invdata['address_id'] = self.address_id.id if self.address_id else False
                    invdata['contact_id'] = self.contact_id.id if self.contact_id else False
                else:
                    invdata['type'] = self.invoice_type
                    invdata['partner_id'] = self.invoice_partner_id.id
                    invdata['address_id'] = self.invoice_address_id.id if self.invoice_address_id else False
                    invdata['contact_id'] = self.invoice_contact_id.id if self.invoice_contact_id else False

                if not self.delivery_is_sale_address:
                    if self.delivery_country_id:
                        invdata['delivery_country_id'] = self.delivery_country_id.id
                    if self.delivery_tinno:
                        invdata['delivery_tinno'] = self.delivery_tinno
                    if self.delivery_address:
                        invdata['delivery_address'] = self.delivery_address

                if self.invoice_partner_id.payment_term_id:
                    due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                    due_date = due_date + datetime.timedelta(days=self.invoice_partner_id.payment_term_id.payment_terms)
                    invdata['date_due'] = due_date.strftime('%Y-%m-%d')

                invoice_model += invoice_model.create(invdata)

        return invoice_model

    @api.multi
    def add_outgoing_line(self, line, devider):

        if not line.product_id.is_stockable():
            return False

        if line.price_per == 'item':
            product_value = line.price
        else:
            product_value = line.amount / line.product_qty
        if devider > 1:
            # wordt gebruikt als er meerdere adressen zijn om te leveren, b.v. 2 adressen is 50/50 verdelen
            vals = {
                'sale_id': self.id,
                'saleline_id': line.id,
                'product_id': line.product_id.id,
                'product_detail': line.product_detail,
                'product_qty': round(line.product_qty / float(devider), 0),
                'product_value': product_value,
                'distribution': line.distribution
            }
        else:
            vals = {
                'sale_id': self.id,
                'saleline_id': line.id,
                'product_id': line.product_id.id,
                'product_detail': line.product_detail,
                'product_qty': line.product_qty,
                'product_value': product_value,
                'distribution': line.distribution
            }
        return vals

    @api.multi
    def create_outgoing(self, add_values=None, devider=1):

        outgoing_model = self.env['s2u.warehouse.outgoing']
        type_model = self.env['s2u.warehouse.outgoing.type']

        self.ensure_one()

        default_outgoing_type_id = type_model.search([('default', '=', True)])
        if not default_outgoing_type_id:
            raise UserError(_('Please define a default outgoing delivery type!'))
        default_outgoing_type_id = default_outgoing_type_id[0].id

        todos = []
        for line in self.line_ids:
            if not line.for_order:
                continue

            vals = self.add_outgoing_line(line, devider)

            if vals:
                if isinstance(vals, list):
                    for v in vals:
                        todos.append((0, 0, v))
                else:
                    todos.append((0, 0, vals))

        if todos:
            vals = {
                'type': self.type,
                'entity_id': self.partner_id.id,
                'contact_id': self.contact_id.id if self.contact_id else False,
                'delivery_type': self.delivery_type,
                'delivery_entity_id': self.delivery_partner_id.id,
                'delivery_contact_id': self.delivery_contact_id.id if self.delivery_contact_id else False,
                'delivery_address': self.delivery_address,
                'project': self.project,
                'reference': self.reference,
                'customer_code': self.customer_code,
                'outgoing_type_id': default_outgoing_type_id,
                'todo_ids': todos,
                'date_delivery': self.date_delivery,
                'delivery_country_id': self.delivery_country_id.id if self.delivery_country_id else False,
                'delivery_tinno': self.delivery_tinno
            }

            if add_values:
                vals.update(add_values)

            outgoing_model += outgoing_model.create(vals)

        return outgoing_model

    @api.multi
    def create_dropshippings(self):

        dropshipping_model = self.env['s2u.dropshipping']

        self.ensure_one()

        suppliers = {}
        for item in self.line_ids:
            if not item.for_order:
                continue
            if not item.product_id.is_dropshipping():
                continue
            total_to_purchase = item.product_qty
            if total_to_purchase <= 0.0:
                continue
            product = self.env[item.product_id.res_model].browse(item.product_id.res_id)
            purchase_info = product.get_purchase_price(total_to_purchase, item.product_detail)

            if not purchase_info:
                product_name = '%s %s' % (item.product_id.name, item.product_detail if item.product_detail else '')
                raise ValueError(_('No supplier found for product %s!' % product_name))

            vals = {
                'product_id': item.product_id.id,
                'product_detail': item.product_detail,
                'qty': item.qty,
                'price': purchase_info['price'],
                'price_per': purchase_info.get('price_per', 'total'),
                'amount': purchase_info.get('total_amount', purchase_info['price']),
                'date_delivery': fields.Date.context_today(self),
                'sale_id': self.id
            }
            if suppliers.get(purchase_info['supplier_id'], False):
                suppliers[purchase_info['supplier_id']]['lines'].append((0, 0, vals))
            else:
                suppliers[purchase_info['supplier_id']] = {
                    'todo': item,
                    'lines': [(0, 0, vals)]
                }
        for supplier_id, item in iter(suppliers.items()):
            vals = {
                'partner_id': supplier_id,
                'line_ids': item['lines'],
                'delivery_type': self.delivery_type,
                'delivery_partner_id': self.delivery_partner_id.id if self.delivery_partner_id else False,
                'delivery_contact_id': self.delivery_contact_id.id if self.delivery_contact_id else False,
                'delivery_address': self.delivery_address
            }
            dropshipping_model += dropshipping_model.create(vals)

        return dropshipping_model

    @api.multi
    def sale_is_completed(self):

        todo_model = self.env['s2u.warehouse.outgoing.todo']
        drops_model = self.env['s2u.dropshipping.line']

        self.ensure_one()

        if self.state != 'run':
            return False

        if self.invoicing in ['delivery', 'complete']:
            products_in_so = {}
            for line in self.line_ids:
                if not line.for_order:
                    continue
                if line.product_id.is_service():
                    continue
                key = '%d,%s' % (line.product_id.id, line.product_detail if line.product_detail else '')
                if key not in products_in_so:
                    products_in_so[key] = {
                        'product_id': line.product_id.id,
                        'product_detail': line.product_detail,
                        'so': line.product_qty,
                        'shipped': 0.0
                    }
                else:
                    products_in_so[key]['so'] += line.product_qty

            for key, data in iter(products_in_so.items()):
                todos = todo_model.search([('sale_id', '=', self.id),
                                           ('product_id', '=', data['product_id']),
                                           ('product_detail', '=', data['product_detail'])])
                for todo in todos:
                    # shipped_qty is negative value, that's why we use -=
                    products_in_so[key]['shipped'] -= todo.shipped_qty

            for key, data in iter(products_in_so.items()):
                drops = drops_model.search([('sale_id', '=', self.id),
                                            ('product_id', '=', data['product_id']),
                                            ('product_detail', '=', data['product_detail'])])
                for drop in drops:
                    if drop.dropshipping_id.state != 'transfered':
                        continue
                    products_in_so[key]['shipped'] += drop.product_qty

            for key, data in iter(products_in_so.items()):
                if data['so'] > data['shipped']:
                    return False

        if self.invoicing in ['complete', 'dropshipping']:
            self.create_invoice()

        self.write({
            'state': 'done'
        })

        return True

    @api.multi
    def action_view_purchase(self):
        purchases = []
        for line in self.line_ids:
            if line.po_line_id:
                purchases.append(line.po_line_id.purchase_id.id)
        purchases = list(set(purchases))

        action = self.env.ref('s2usale.action_purchase').read()[0]
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases)]
        elif len(purchases) == 1:
            action['views'] = [(self.env.ref('s2usale.purchase_form').id, 'form')]
            action['res_id'] = purchases[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_invoice_count(self):

        for order in self:
            invlines = self.env['s2u.account.invoice.line'].search([('sale_id', '=', order.id)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))
            order.invoice_count = len(invoice_ids)

    def _get_outgoing_count(self):

        for order in self:
            todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', order.id)])
            outgoing_ids = [l.outgoing_id.id for l in todolines]
            outgoing_ids = list(set(outgoing_ids))
            order.outgoing_count = len(outgoing_ids)

    def _get_purchase_count(self):

        for order in self:
            purchases = []
            for line in order.line_ids:
                if line.po_line_id:
                    purchases.append(line.po_line_id.purchase_id.id)
            purchases = list(set(purchases))
            order.purchase_count = len(purchases)

    @api.one
    def customized_compute_amount(self):

        return True

    @api.one
    def customized_compute_amount_quot(self):

        return True

    @api.one
    @api.depends('line_ids')
    def _compute_amount(self):

        net_amount = 0.0
        vat_amount = 0.0
        gross_amount = 0.0
        for line in self.line_ids:
            if line.price_is_net:
                net_amount += line.amount
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_netto_amount(line.amount)
                    gross = line.vat_id.calc_gross_amount(line.amount, vat)
                    vat_amount += vat
                    gross_amount += gross
                else:
                    gross_amount += line.amount
            else:
                gross_amount += line.amount
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_gross_amount(line.amount)
                    net = line.amount - vat
                    vat_amount += vat
                    net_amount += net
                else:
                    net_amount += line.amount

        self.net_amount = net_amount
        self.vat_amount = vat_amount
        self.gross_amount = gross_amount

        # call this method in case customized modules needs to something on the amounts
        self.customized_compute_amount()

    @api.one
    @api.depends('line_ids')
    def _compute_amount_quot(self):

        net_amount = 0.0
        vat_amount = 0.0
        gross_amount = 0.0
        for line in self.line_ids:
            if line.price_is_net:
                net_amount += line.amount
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_netto_amount(line.amount)
                    gross = line.vat_id.calc_gross_amount(line.amount, vat)
                    vat_amount += vat
                    gross_amount += gross
                else:
                    gross_amount += line.amount
            else:
                gross_amount += line.amount
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_gross_amount(line.amount)
                    net = line.amount - vat
                    vat_amount += vat
                    net_amount += net
                else:
                    net_amount += line.amount

        self.quot_net_amount = net_amount
        self.quot_vat_amount = vat_amount
        self.quot_gross_amount = gross_amount

        # call this method in case customized modules needs to something on the amounts
        self.customized_compute_amount_quot()

    @api.multi
    def format_templates(self):

        self.ensure_one()

        return True

    @api.one
    def _compute_template(self):
        if self.template_id:
            other = {
                'short_description': self.reference if self.reference else '',
                'so': self
            }
            self.prefix_quotation = self.template_id.render_template(self.template_id.prefix_quotation,
                                                                     entity=self.partner_id,
                                                                     contact=self.contact_id,
                                                                     address=self.address_id,
                                                                     user=self.user_id,
                                                                     other=other)
            self.postfix_quotation = self.template_id.render_template(self.template_id.postfix_quotation,
                                                                      entity=self.partner_id,
                                                                      contact=self.contact_id,
                                                                      address=self.address_id,
                                                                      user=self.user_id,
                                                                      other=other)
            self.prefix_confirmation = self.template_id.render_template(self.template_id.prefix_confirmation,
                                                                        entity=self.partner_id,
                                                                        contact=self.contact_id,
                                                                        address=self.address_id,
                                                                        user=self.user_id,
                                                                        other=other)
            self.postfix_confirmation = self.template_id.render_template(self.template_id.postfix_confirmation,
                                                                         entity=self.partner_id,
                                                                         contact=self.contact_id,
                                                                         address=self.address_id,
                                                                         user=self.user_id,
                                                                         other=other)
            self.prefix_delivery = self.template_id.render_template(self.template_id.prefix_delivery,
                                                                    entity=self.partner_id,
                                                                    contact=self.contact_id,
                                                                    address=self.address_id,
                                                                    user=self.user_id,
                                                                    other=other)
            self.postfix_delivery = self.template_id.render_template(self.template_id.postfix_delivery,
                                                                     entity=self.partner_id,
                                                                     contact=self.contact_id,
                                                                     address=self.address_id,
                                                                     user=self.user_id,
                                                                     other=other)
            self.date_display = self.template_id.render_template(self.template_id.date_display,
                                                                 date=datetime.datetime.now().strftime('%Y-%m-%d'))
        else:
            self.prefix_quotation = ''
            self.postfix_quotation = ''
            self.prefix_confirmation = ''
            self.postfix_confirmation = ''
            self.date_display = ''

        self.format_templates()

    @api.one
    def _compute_editions(self):

        editions = ''
        for line in self.line_ids:
            if not line.qty:
                continue
            if editions:
                editions = '%s, ' % editions
            editions = '%s%s' % (editions, line.qty)

        self.editions = editions

    @api.one
    def _compute_editions_ordered(self):

        editions = ''
        for line in self.line_ids:
            if not line.qty:
                continue
            if not line.for_order:
                continue
            if editions:
                editions = '%s, ' % editions
            editions = '%s%s' % (editions, line.qty)

        self.editions_ordered = editions

    def get_portal_confirmation_action(self):
        return None

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    def _compute_is_expired(self):
        now = datetime.datetime.now()
        for order in self:
            if order.date_valid and fields.Datetime.from_string(order.date_valid) < now:
                order.is_expired = True
            else:
                order.is_expired = False

    def _get_rma_count(self):

        for sale in self:
            todos = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', sale.id)])
            rmas = self.env['s2u.warehouse.rma.line'].search([('todo_id', 'in', todos.ids)])
            rma_ids = [r.rma_id.id for r in rmas]
            rma_ids = list(set(rma_ids))
            sale.rma_count = len(rma_ids)

    @api.multi
    def action_view_rma(self):
        todos = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', self.id)])
        rmas = self.env['s2u.warehouse.rma.line'].search([('todo_id', 'in', todos.ids)])
        rma_ids = [r.rma_id.id for r in rmas]
        rma_ids = list(set(rma_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rma_ids) > 1:
            action['domain'] = [('id', 'in', rmas.ids)]
        elif len(rma_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_rma_form').id, 'form')]
            action['res_id'] = rma_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_document_count(self):

        for sale in self:
            docs = self.env['s2u.document'].search([('res_model', '=', 's2u.sale'),
                                                    ('res_id', '=', sale.id)])
            sale.document_count = len(docs.ids)

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('res_model', '=', 's2u.sale'),
                            ('res_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.partner_id.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.name,
            'default_res_model': 's2u.sale',
            'default_res_id': self.id
        }
        action['context'] = str(context)
        return action

    @api.multi
    def _compute_email_address(self):

        if self.type == 'b2b':
            if self.contact_id and self.contact_id.email:
                self.use_email_address = self.contact_id.email
            elif self.address_id and self.address_id.inv_by_mail and self.address_id.email:
                self.use_email_address = self.address_id.email
            elif self.partner_id.email:
                self.use_email_address = self.partner_id.email
            else:
                self.use_email_address = False
        else:
            if self.partner_id.email:
                self.use_email_address = self.partner_id.email
            else:
                self.use_email_address = False

    @api.multi
    def action_quotation_by_email(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        if not self.use_email_address:
            raise UserError(_('There is no mail address present to use!'))

        template = self.env['mail.template'].sudo().search([('model', '=', 's2u.sale'),
                                                            ('name', '=', 'quotation')], limit=1)

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            force_email=True
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def action_order_by_email(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        if not self.use_email_address:
            raise UserError(_('There is no mail address present to use!'))

        template = self.env['mail.template'].sudo().search([('model', '=', 's2u.sale'),
                                                            ('name', '=', 'order')], limit=1)

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        ctx = dict(
            default_model='s2u.sale',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            force_email=True
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    _order_state1 = {
        'draft': [('readonly', False)],
    }

    _order_state2 = {
        'draft': [('readonly', False)],
        'quot': [('readonly', False)],
        'order': [('readonly', False)],
        'payment': [('readonly', False)],
    }

    name = fields.Char(string='SO', required=True, index=True, copy=False,
                       default='Concept')
    name_quot = fields.Char(string='Quotation', index=True, copy=False)
    reference = fields.Char(string='Short descript.', index=True, copy=False, readonly=True, states=_order_state2)
    customer_code = fields.Char(string='Your reference', index=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    line_ids = fields.One2many('s2u.sale.line', 'sale_id',
                               string='Lines', copy=True, readonly=True, states=_order_state2)
    ordered_line_ids = fields.One2many('s2u.sale.line', 'sale_id',
                                       string='Ordered lines', copy=False, readonly=True, domain=[('for_order', '=', True)])
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_order_state1)
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True,
                                 readonly=True, states=_order_state1)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                 readonly=True, states=_order_state1)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, readonly=True,
                                 states=_order_state1)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('quot', 'Quotation'),
        ('order', 'Order'),
        ('payment', 'Payment'),
        ('confirm', 'Confirmed'),
        ('run', 'Running'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', track_visibility='onchange')
    date_qu = fields.Date(string='Date (Quot)', index=True, copy=False,
                          readonly=True, states=_order_state1)
    date_valid = fields.Date(string='Valid till', index=True, copy=False,
                             readonly=True, states=_order_state2)
    date_so = fields.Date(string='Date (SO)', index=True, copy=False,
                          readonly=True, states=_order_state1)
    date_confirm = fields.Date(string='Confirmed', index=True, copy=False,
                               readonly=True, states=_order_state1)
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    outgoing_count = fields.Integer(string='# of Deliveries', compute='_get_outgoing_count', readonly=True)
    purchase_count = fields.Integer(string='# of Purchases', compute='_get_purchase_count', readonly=True)
    net_amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True, store=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True, store=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True, store=True)
    template_id = fields.Many2one('s2u.sale.template', string='Template', default=_default_template,
                                  readonly=True, states=_order_state2)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_order_state2)
    prefix_quotation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_quotation = fields.Html('Postfix', compute=_compute_template, readonly=True)
    prefix_confirmation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_confirmation = fields.Html('Postfix', compute=_compute_template, readonly=True)
    prefix_delivery = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_delivery = fields.Html('Postfix', compute=_compute_template, readonly=True)
    invoice_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], default='b2b', string='Type', index=True, readonly=True, states=_order_state1)
    invoice_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', index=True,
                                         readonly=True, states=_order_state1)
    invoice_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                         readonly=True, states=_order_state1)
    invoice_address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True,
                                         readonly=True, states=_order_state1)
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], default='b2b', string='Type', index=True, readonly=True, states=_order_state1)
    delivery_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', index=True,
                                          readonly=True, states=_order_state1)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                          readonly=True, states=_order_state1)
    delivery_address = fields.Text(string='Address', readonly=True, states=_order_state1)
    invoicing = fields.Selection([
        ('delivery', 'On delivery'),
        ('complete', 'When completed'),
        ('dropshipping', 'Dropshipping'),
        ('confirm', 'On confirmation'),
        ('manual', 'Manual')
    ], required=True, default='confirm', string='Invoicing')
    show_total_amount = fields.Boolean('Show amount', default=True, help='When active, the total amount is printed on the quotation otherwise this is skipped.')
    quot_net_amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount_quot,
                                      readonly=True)
    quot_vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount_quot,
                                      readonly=True)
    quot_gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount_quot,
                                        readonly=True)
    detailed_ids = fields.One2many('s2u.sale.detailed', 'sale_id',
                                   string='Details', copy=True, readonly=True, states=_order_state2)
    project = fields.Char(string='Project', index=True, readonly=True, states=_order_state2)
    date_display = fields.Text('Date display', compute=_compute_template, readonly=True)
    date_delivery = fields.Date(string='Date delivery', copy=False)
    editions = fields.Char('Editions', compute=_compute_editions, readonly=True)
    editions_ordered = fields.Char('Editions', compute=_compute_editions_ordered, readonly=True)
    delivery_ids = fields.One2many('s2u.sale.delivery.address', 'sale_id',
                                   string='Deliveries', readonly=True, states=_order_state2)
    delivery_delivery_id = fields.Many2one('s2u.crm.entity.delivery', string='Delivery')
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland', default=_default_delivery_country)
    delivery_tinno = fields.Char('TIN no.')
    chance = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Chance', index=True)
    confirmed_user_id = fields.Many2one('res.users', string='User', copy=False, readonly=True, states=_order_state2)
    confirmed_remark = fields.Char(string='Remark', copy=False, readonly=True, states=_order_state2)
    kickback_partner_id = fields.Many2one('s2u.crm.entity', string='Partner', index=True,
                                          readonly=True, states=_order_state2)
    kickback = fields.Float(string='Kickback (%)', default='0.0')

    # use ../../.. notation in the selection, create invoices is splitting this condition value based on '/'
    condition = fields.Selection([
        ('100', '100%'),
        ('50/50', '50/50'),
        ('40/40/20', '40/40/20')
    ], required=True, default='100', string='Condition')
    access_token = fields.Char('Security Token', copy=False, default=_get_default_access_token)
    is_expired = fields.Boolean(compute='_compute_is_expired', string="Is expired")
    invoice_is_sale_address = fields.Boolean(string='Invoice is sale address', default=True)
    delivery_is_sale_address = fields.Boolean(string='Delivery is sale address', default=True)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)
    confirmed_by = fields.Selection([
        ('mail', 'Mail'),
        ('signed', 'Signed copy'),
        ('po', 'Own PO'),
        ('shop', 'Webshop')
    ], string='Confirmed by')
    confirmed_user_id = fields.Many2one('res.users', string='Confirmed by user', copy=False)
    active = fields.Boolean('Active', default=True)
    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)
    use_email_address = fields.Char(string='Address for mail', readonly=True, compute='_compute_email_address')
    cancel_reason = fields.Char(string='Cancel Reason')


class SaleKickbackInvoicing(models.Model):
    _name = "s2u.sale.kickback.invoicing"
    _description = "Kickback Invoicing"
    _order = "date_invoicing desc"

    @api.model
    def _default_invoices_till(self):

        tillm = datetime.date.today().month
        tilly = datetime.date.today().year

        return datetime.date(tilly, tillm, 1) - datetime.timedelta(days=1)

    @api.multi
    def do_invoicing(self):

        for invpartner in self.partner_ids:
            if invpartner.invoice_id:
                if invpartner.invoice_id.state == 'draft':
                    invpartner.invoice_id.unlink()
                elif invpartner.invoice_id.state == 'cancel':
                    invpartner.write({
                        'invoice_id': False
                    })

        self.invalidate_cache()

        self._cr.execute("DELETE FROM s2u_sale_kickback_invoicing_partner WHERE invoicing_id=%s and invoice_id is null", (self.id,))
        self.invalidate_cache()

        invoices = self.env['s2u.account.invoice'].search([('date_invoice', '<=', self.invoices_till),
                                                           ('state', '=', 'invoiced')])
        for inv in invoices:
            for invline in inv.line_ids:
                if not (invline.sale_id and invline.sale_id.kickback and invline.sale_id.kickback_partner_id):
                    continue
                exists = self.env['s2u.sale.kickback.invoicing.partner.invoice'].search([('invoiceline_id', '=', invline.id)])
                if exists:
                    continue

                invpartner = self.env['s2u.sale.kickback.invoicing.partner'].search([('invoicing_id', '=', self.id),
                                                                                     ('partner_id', '=', invline.sale_id.kickback_partner_id.id)], limit=1)

                if not invpartner:
                    invpartner = self.env['s2u.sale.kickback.invoicing.partner'].create({
                        'invoicing_id': self.id,
                        'partner_id': invline.sale_id.kickback_partner_id.id
                    })

                self.env['s2u.sale.kickback.invoicing.partner.invoice'].create({
                    'invpartner_id': invpartner.id,
                    'invoiceline_id': invline.id,
                    'kickback': invline.sale_id.kickback,
                    'kickback_amount': round(invline.net_amount * invline.sale_id.kickback / 100.0, 2)
                })

        self.write({
            'date_invoicing': fields.Date.context_today(self),
            'user_id': self.env.user.id
        })

        return True

    @api.multi
    def create_invoices(self):

        invoice_model = self.env['s2u.account.invoice']
        invline_model = self.env['s2u.account.invoice.line']

        self.do_invoicing()
        self.invalidate_cache()

        for invpartner in self.partner_ids:

            if invpartner.invoice_id:
                continue

            invdata = {
                'type': 'b2b',
                'partner_id': invpartner.partner_id.id,
                'invoicing_id': self.id,
                'date_invoice': fields.Date.context_today(self),
                'date_financial': fields.Date.context_today(self)
            }

            if invpartner.partner_id.payment_term_id:
                due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                due_date = due_date + datetime.timedelta(days=invpartner.partner_id.payment_term_id.payment_terms)
                invdata['date_due'] = due_date.strftime('%Y-%m-%d')

            if invpartner.invoice_ids:
                invdata['reference'] = _('Kickback till %s' % self.invoices_till)

            address = invpartner.partner_id.get_postal()
            if address:
                invdata['address_id'] = address.id

            invoice = invoice_model.create(invdata)
            invoice_model += invoice

            for line in invpartner.invoice_ids:
                invlinedata = {
                    'invoice_id': invoice.id,
                    'net_amount': line.kickback_amount * -1.0,
                    'account_id': self.account_id.id,
                    'descript': 'Kickback %s (%s): %s' % (line.invoiceline_id.invoice_id.name,
                                                          line.invoiceline_id.sale_id.name,
                                                          line.invoiceline_id.descript),
                    'qty': '1 stuks',
                    'net_price': line.kickback_amount * -1.0,
                    'sale_id': False
                }
                if invpartner.partner_id.vat_sell_id:
                    invlinedata['vat_id'] = invpartner.partner_id.vat_sell_id.id
                    invlinedata['vat_amount'] = invpartner.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        invlinedata['net_amount'])
                    invlinedata['gross_amount'] = invpartner.partner_id.vat_sell_id.calc_gross_amount(
                        invlinedata['net_amount'], invlinedata['vat_amount'])
                elif self.account_id.vat_id:
                    invlinedata['vat_id'] = self.account_id.vat_id.id
                    invlinedata['vat_amount'] = self.account_id.vat_id.calc_vat_from_netto_amount(
                        invlinedata['net_amount'])
                    invlinedata['gross_amount'] = self.account_id.vat_id.calc_gross_amount(
                        invlinedata['net_amount'], invlinedata['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for kickback account!'))

                invline_model.create(invlinedata)

            invpartner.write({
                'invoice_id': invoice.id
            })

        self.write({
            'state': 'invoiced'
        })

        return invoice_model

    @api.multi
    def done_invoices(self):

        for invpartner in self.partner_ids:

            if invpartner.invoice_id and invpartner.invoice_id.state == 'draft':
                invpartner.invoice_id.do_validate()

        self.write({
            'state': 'done'
        })


    @api.one
    @api.depends('invoices_till')
    def _compute_invoices_year(self):
        if not self.invoices_till:
            self.year_invoices = False
        else:
            invoicedat = datetime.datetime.strptime(self.invoices_till, '%Y-%m-%d')
            self.year_invoices = invoicedat.strftime("%Y")

    @api.one
    @api.depends('invoices_till')
    def _compute_invoices_month(self):
        if not self.invoices_till:
            self.month_invoices = False
        else:
            invoicesdat = datetime.datetime.strptime(self.invoices_till, '%Y-%m-%d')
            self.month_invoices = invoicesdat.strftime("%B")

    @api.one
    @api.depends('partner_ids.tot_amount')
    def _compute_amount(self):
        self.tot_amount = sum(line.tot_amount for line in self.partner_ids)

    def _get_invoice_count(self):

        for inv in self:
            invlines = self.env['s2u.sale.kickback.invoicing.partner'].search([('invoicing_id', '=', inv.id)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))
            inv.invoice_count = len(invoice_ids)

    @api.multi
    def action_view_invoice(self):
        invlines = self.env['s2u.sale.kickback.invoicing.partner'].search([('invoicing_id', '=', self.id)])
        invoice_ids = [l.invoice_id.id for l in invlines]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice').read()[0]
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('s2uaccount.invoice_form').id, 'form')]
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    _invoiced_state = {
        'draft': [('readonly', False)],
        'invoiced': [('readonly', False)],
    }

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_invoiced_state)
    date_invoicing = fields.Date(string='Date', index=True, copy=False,
                                 default=lambda self: fields.Date.context_today(self),
                                 required=True, readonly=True, states=_invoiced_state)
    invoices_till = fields.Date(string='Kickback till', index=True, copy=False,
                                default=_default_invoices_till, required=True, readonly=True, states=_invoiced_state)
    partner_ids = fields.One2many('s2u.sale.kickback.invoicing.partner', 'invoicing_id',
                                  string='Partners', copy=False, readonly=True, states=_invoiced_state)
    year_invoices = fields.Char(string='Kickback Year',
                                store=True, readonly=True, compute='_compute_invoices_year')
    month_invoices = fields.Char(string='Invoices Month',
                                 store=True, readonly=True, compute='_compute_invoices_month')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    tot_amount = fields.Monetary(string='Tot. Amount',
                                 store=True, readonly=True, compute='_compute_amount')
    state = fields.Selection([
        ('draft', 'Concept'),
        ('invoiced', 'Invoiced'),
        ('done', 'Done'),
    ], required=True, default='draft', string='State', index=True, copy=False)
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    account_id = fields.Many2one('s2u.account.account', string='Account kickback', required=True,
                                 domain=[('type', '=', 'income')])


class SaleKickbackInvoicingPartner(models.Model):
    _name = "s2u.sale.kickback.invoicing.partner"
    _description = "Kickback for Partner"
    _rec_name = "partner_id"

    @api.one
    @api.depends('invoice_ids.kickback_amount')
    def _compute_amount(self):

        self.tot_amount = sum(line.kickback_amount for line in self.invoice_ids)

    invoicing_id = fields.Many2one('s2u.sale.kickback.invoicing', string='Invoicing', required=True, ondelete='cascade')
    partner_id = fields.Many2one('s2u.crm.entity', string='Partner', required=True, index=True)
    invoice_ids = fields.One2many('s2u.sale.kickback.invoicing.partner.invoice', 'invpartner_id',
                                  string='Invoices', copy=False)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    tot_amount = fields.Monetary(string='Tot. kickback',
                                 store=True, readonly=True, compute='_compute_amount')
    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', ondelete='cascade')


class SaleKickbackInvoicingPartnerInvoice(models.Model):
    _name = "s2u.sale.kickback.invoicing.partner.invoice"
    _description = "Kickback for Partner on invoice"

    invpartner_id = fields.Many2one('s2u.sale.kickback.invoicing.partner', string='Invoicing Partner', required=True,
                                    ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  related='invpartner_id.currency_id', store=True)
    invoiceline_id = fields.Many2one('s2u.account.invoice.line', string='Kickback on invoice line', required=True, ondelete='restrict')
    kickback = fields.Float(string='Kickback (%)', default='0.0')
    kickback_amount = fields.Monetary(string='Kickback amount')
