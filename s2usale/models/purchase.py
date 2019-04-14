# -*- coding: utf-8 -*-

import re
import datetime
import io
import base64
import xlsxwriter

from odoo.tools.misc import formatLang
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class PurchaseTemplate(models.Model):
    _name = "s2u.purchase.template"
    _description = "Purchase Template"

    name = fields.Char(string='Template', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    date_display = fields.Char(string='Date display')
    prefix_quotation = fields.Html(string='Prefix')
    postfix_quotation = fields.Html(string='Postfix')
    prefix_confirmation = fields.Html(string='Prefix')
    postfix_confirmation = fields.Html(string='Postfix')
    default = fields.Boolean('Default', default=False)


class PurchaseLineQty(models.Model):
    _name = "s2u.purchase.line.qty"
    _description = "Purchase line Qty"
    _order = 'product_qty'

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            if line.purchaseline_id.product_detail:
                name = '%s:%s %s (%s)' % (
                    line.purchaseline_id.purchase_id.name, line.purchaseline_id.product_id.name,
                    line.purchaseline_id.product_detail, line.purchaseline_id.purchase_id.partner_id.name)
            else:
                name = '%s:%s (%s)' % (line.purchaseline_id.purchase_id.name, line.purchaseline_id.product_id.name,
                                       line.purchaseline_id.purchase_id.partner_id.name)
            result.append((line.id, name))
        return result

    @api.one
    @api.depends('price', 'qty', 'price_per')
    def _compute_amount(self):

        if not self.price_per or not self.price:
            self.amount = 0.0
            return

        if self.price_per == 'total':
            self.amount = self.price
            return

        qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)
        if not qty:
            self.amount = 0.0
            return

        if self.price_per == 'item':
            self.amount = round(qty * self.price, 2)
            return

        if self.price_per in ['10', '100', '1000']:
            qty = qty / float(self.price_per)
            self.amount = round(qty * self.price, 2)
            return

    @api.onchange('qty')
    def _onchange_qty(self):

        if self._context.get('supplier_id', False):
            product = self.env[self.purchaseline_id.product_id.res_model].browse(self.purchaseline_id.product_id.res_id)
            purchase_info = product.get_purchase_price(self.qty, self.purchaseline_id.product_detail, ctx={
                'supplier_id': self.purchaseline_id.purchase_id.partner_id.id
            })
            if purchase_info:
                self.price = purchase_info['price']
                self.price_per = 'total'

    @api.one
    def _compute_pdf(self):
        # nodig voor in de pdf template
        if self.distribution:
            self.qty_pdf = '%s - (%s)' % (self.qty, self.distribution)
        else:
            self.qty_pdf = self.qty

    purchaseline_id = fields.Many2one('s2u.purchase.line', string='Purchase line', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='purchaseline_id.currency_id', store=True)
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
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')
    qty_pdf = fields.Char(string='Qty/Distri', compute=_compute_pdf, readonly=True)

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(PurchaseLineQty, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(PurchaseLineQty, self).write(vals)


class PurchaseLineLabel(models.Model):
    _name = "s2u.purchase.line.label"
    _order = 'sequence'

    @api.one
    def _compute_value(self):

        self.calc_value_request = self.env['s2u.purchase'].calc_value(self.purchaseline_id, self.label_id, self.display,
                                                                      self.value, po_type='request')
        self.calc_value_order = self.env['s2u.purchase'].calc_value(self.purchaseline_id, self.label_id, self.display,
                                                                    self.value, po_type='order')

    purchaseline_id = fields.Many2one('s2u.purchase.line', string="Line", ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    value = fields.Text(string='Value')
    sequence = fields.Integer(string='Sequence', default=10)
    calc_value_request = fields.Text(string='Value', compute=_compute_value, readonly=True)
    calc_value_order = fields.Text(string='Value', compute=_compute_value, readonly=True)
    display = fields.Selection([
        ('both', 'Request and Order'),
        ('request', 'Request only'),
        ('order', 'Order only')
    ], required=True, default='both', string='Display')


# TODO: kan verwijderd worden
class PurchaseLineLabelOrder(models.Model):
    _name = "s2u.purchase.line.label.order"
    _order = 'sequence'

    @api.one
    def _compute_value(self):
        self.calc_value = self.env['s2u.purchase'].calc_value(self.purchaseline_id, self.label_id, self.value,
                                                              po_type='order')

    purchaseline_id = fields.Many2one('s2u.purchase.line', string="Line", ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    value = fields.Text(string='Value')
    sequence = fields.Integer(string='Sequence', default=10)
    calc_value = fields.Text(string='Value', compute=_compute_value, readonly=True)


class PurchaseLine(models.Model):
    _name = "s2u.purchase.line"
    _description = "Purchase line"

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            if line.product_detail:
                name = '%s:%s %s (%s)' % (line.purchase_id.name, line.product_id.name, line.product_detail, line.purchase_id.partner_id.name)
            else:
                name = '%s:%s (%s)' % (line.purchase_id.name, line.product_id.name, line.purchase_id.partner_id.name)
            result.append((line.id, name))
        return result

    @api.one
    def _compute_vat(self):

        if not self.product_id:
            self.vat_id = False
            return

        try:
            product = self.env[self.product_id.res_model].search([('id', '=', self.product_id.res_id)])
            if product:
                if self.purchase_id.partner_id.vat_buy_id:
                    self.vat_id = self.purchase_id.partner_id.vat_buy_id
                else:
                    self.vat_id = product.get_po_vat()
            else:
                self.vat_id = False
        except:
            self.vat_id = False

    @api.one
    @api.depends('qty_ids.qty', 'qty_ids.for_order', 'qty_ids.amount', 'qty_ids.price')
    def _compute_qty(self):

        for_order = 0
        for qty in self.qty_ids:
            if qty.for_order:
                for_order += 1
        if for_order:
            if for_order == 1:
                for qty in self.qty_ids:
                    if qty.for_order:
                        self.amount = qty.amount
                        self.qty = qty.qty
                        self.distribution = qty.distribution
                        self.price = qty.price
                        self.price_per = qty.price_per
                        self.for_order = True
                        return
            else:
                amount = 0.0
                qtys = 0.0
                distribution = ''
                for qty in self.qty_ids:
                    if qty.for_order:
                        amount += qty.amount
                        product_qty = self.env['s2u.baseproduct.abstract'].parse_qty(qty.qty)
                        qtys += product_qty
                        if distribution:
                            distribution = '%s + %s' % (distribution, qty.distribution)
                        else:
                            distribution = qty.distribution
                self.amount = amount
                self.qty = str(qtys) + ' stuks'
                self.distribution = distribution
                self.price = amount
                self.price_per = 'total'
                self.for_order = True
                return

        if self.qty_ids:
            self.amount = self.qty_ids[0].amount
            self.qty = self.qty_ids[0].qty
            self.price = self.qty_ids[0].price
            self.price_per = self.qty_ids[0].price_per
            self.for_order = False
            self.distribution = self.qty_ids[0].distribution
        else:
            self.amount = 0.0
            self.qty = ''
            self.price = 0.0
            self.price_per = 'item'
            self.for_order = False
            self.distribution = ''
        return

    @api.onchange('product_id')
    def onchange_product_id(self):

        if self.product_id and not self.qty_ids:
            vals = {
                'qty': '1 stuks',
            }
            product = self.env[self.product_id.res_model].browse(self.product_id.res_id)

            purchase_info = product.get_purchase_price('1 stuks', self.product_detail, ctx={
                'supplier_id': self._context['supplier_id']
            })
            if purchase_info:
                vals['price'] = purchase_info['price']
                vals['price_per'] = 'item'
                vals['amount'] = purchase_info['price']

                if purchase_info.get('code_supplier'):
                    self.code_supplier = purchase_info['code_supplier']

            self.qty_ids = [(0, 0, vals)]

    @api.onchange('product_detail')
    def onchange_product_detail(self):

        if not self.product_id:
            return

        detail = self.env[self.product_id.res_model].check_product_detail(self.product_detail)
        self.product_detail = detail

    purchase_id = fields.Many2one('s2u.purchase', string='Purchase', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='purchase_id.currency_id', store=True)
    available_id = fields.Many2one('s2u.warehouse.available', string='Available', ondelete='restrict')
    date_delivery = fields.Date(string='Delivery')
    vat_id = fields.Many2one('s2u.account.vat', string='VAT', compute=_compute_vat, readonly=True)
    for_order = fields.Boolean('Order', compute=_compute_qty, readonly=True)
    code_supplier = fields.Char(string='Code Supplier')
    qty_ids = fields.One2many('s2u.purchase.line.qty', 'purchaseline_id', string='Request', copy=True)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True)
    product_detail = fields.Char(string='Details')
    amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_qty,
                             readonly=True)
    qty = fields.Char(string='Qty', compute=_compute_qty, readonly=True)
    distribution = fields.Char(string='Distribution', compute=_compute_qty, readonly=True)
    price = fields.Monetary(string='Price', currency_field='currency_id', compute=_compute_qty, readonly=True)
    price_per = fields.Selection([
        ('item', 'Item'),
        ('10', 'per 10'),
        ('100', 'per 100'),
        ('1000', 'per 1000'),
        ('total', 'Total')
    ], string='Per', compute=_compute_qty, readonly=True)
    label_ids = fields.One2many('s2u.purchase.line.label', 'purchaseline_id', string='Request', copy=True)
    project = fields.Char(string='Project')
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')

    @api.model
    def create(self, vals):

        available_model = self.env['s2u.warehouse.available']

        product = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
        vals['product_detail'] = self.env[product.res_model].check_product_detail(vals.get('product_detail', ''),
                                                                                  product_name=product.name)
        product_id = product.id
        product_detail = vals.get('product_detail', '')

        availables = available_model.search([('product_id', '=', product_id),
                                             ('product_detail', '=', product_detail)])
        if not availables:
            available = available_model.create({
                'product_id': product_id,
                'product_detail': product_detail
            })
            available_id = available.id
        else:
            available_id = availables[0].id

        vals['available_id'] = available_id

        return super(PurchaseLine, self).create(vals)

    @api.multi
    def write(self, vals):

        available_model = self.env['s2u.warehouse.available']

        if vals.get('product_id', False):
            baseproduct = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
            res_model = baseproduct.res_model
            product_name = baseproduct.name
            product_id = vals['product_id']
        else:
            res_model = self.product_id.res_model
            product_name = self.product_id.name
            product_id = self.product_id.id

        if 'product_detail' in vals:
            product_detail = vals['product_detail']
            vals['product_detail'] = self.env[res_model].check_product_detail(product_detail,
                                                                              product_name=product_name)
        else:
            product_detail = self.product_detail

        availables = available_model.search([('product_id', '=', product_id),
                                             ('product_detail', '=', product_detail)])
        if not availables:
            available = available_model.create({
                'product_id': product_id,
                'product_detail': product_detail
            })
            available_id = available.id
        else:
            available_id = availables[0].id

        vals['available_id'] = available_id

        return super(PurchaseLine, self).write(vals)


class PurchaseDetailed(models.Model):
    _name = "s2u.purchase.detailed"
    _order = 'sequence'

    purchase_id = fields.Many2one('s2u.purchase', string='Purchase', required=True, ondelete='cascade')
    detailed_label = fields.Char(string='Label', required=True)
    detailed_info = fields.Text(string='Details')
    sequence = fields.Integer(string='Sequence', default=10)


class Purchase(models.Model):
    _name = "s2u.purchase"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Purchase"
    _order = "id desc"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Purchase, self)._track_subtype(init_values)

    def userdef_calc_value(self, po_line, label, keyword, display, value, po_type):

        return False

    def calc_value(self, po_line, label, display, value, po_type='request'):

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

        if display == 'request' and po_type != 'request':
            return ''
        if display == 'order' and po_type != 'order':
            return ''

        match = re.search(r'.*\{\{(?P<value>.+)\}\}.*', value)
        if not match:
            return value

        userdef = self.userdef_calc_value(po_line, label, match.group('value'), display, value, po_type)
        if userdef:
            return userdef

        if match.group('value') == 'order-number':
            return value.replace('{{order-number}}', po_line.purchase_id.name if po_line.purchase_id.name else '')

        if match.group('value') == 'reference':
            return value.replace('{{reference}}', po_line.purchase_id.reference if po_line.purchase_id.reference else '')

        if match.group('value') == 'project':
            project = ''
            if po_line.project:
                project = po_line.project
            elif po_line.purchase_id.project:
                project = po_line.purchase_id.project
            return value.replace('{{project}}', project)

        if match.group('value') == 'qty':
            qty_value = po_line.qty

            return value.replace('{{qty}}', qty_value)

        # old version
        if match.group('value') == 'qty':
            qty_value = ''
            if po_type == 'request':
                for qty in po_line.qty_ids:
                    if qty.distribution:
                        qty_line = '%s - (%s)' % (qty.qty, qty.distribution)
                    else:
                        qty_line = qty.qty
                    if qty_value:
                        qty_value = '%s\n%s' % (qty_value, qty_line)
                    else:
                        qty_value = qty_line
            else:
                if po_line.distribution:
                    qty_value = '%s - (%s)' % (po_line.qty, po_line.distribution)
                else:
                    qty_value = po_line.qty

            return value.replace('{{qty}}', qty_value)

        if match.group('value') == 'qty-dist':
            if po_line.distribution:
                qty_value = '%s - (%s)' % (po_line.qty, po_line.distribution)
            else:
                qty_value = po_line.qty

            return value.replace('{{qty-dist}}', qty_value)

        if match.group('value') == 'distribution':
            dist = po_line.distribution if po_line.distribution else ''
            return value.replace('{{distribution}}', dist)

        if match.group('value') == 'total-amount':
            return value.replace('{{total-amount}}',
                                 formatLang(self.env, po_line.amount, currency_obj=po_line.currency_id))

        if match.group('value') == 'item-amount':
            item_amount = '%s %s' % (formatLang(self.env, po_line.price, currency_obj=po_line.currency_id),
                                     PRICE_PER[po_line.price_per])
            return value.replace('{{item-amount}}', item_amount)

        if match.group('value') == 'delivery':
            if hasattr(po_line.purchase_id, 'delivery_address'):
                if po_line.purchase_id.delivery_address:
                    return value.replace('{{delivery}}', po_line.purchase_id.delivery_address)
            if hasattr(po_line.purchase_id, 'dropshipping_address'):
                if po_line.purchase_id.dropshipping_address:
                    return value.replace('{{delivery}}', po_line.purchase_id.dropshipping_address)
            return ''

        if match.group('value') == 'payment-terms':
            if po_line.purchase_id.invoice_partner_id and po_line.purchase_id.invoice_partner_id.payment_term_id:
                return value.replace('{{payment-terms}}', po_line.purchase_id.invoice_partner_id.payment_term_id.name)
            return ''

        if match.group('value') == 'date-delivery':
            if hasattr(po_line.purchase_id, 'date_delivery') and po_line.purchase_id.date_delivery:
                date_delivery = datetime.datetime.strptime(po_line.purchase_id.date_delivery, "%Y-%m-%d")
                date_delivery = '%d %s %d' % (date_delivery.day, MONTHS[date_delivery.month - 1], date_delivery.year)
                return value.replace('{{date-delivery}}', date_delivery)
            else:
                return value.replace('{{date-delivery}}', '')

        if match.group('value') == 'date-artwork':
            if hasattr(po_line.purchase_id, 'date_artwork') and po_line.purchase_id.date_artwork:
                date_artwork = datetime.datetime.strptime(po_line.purchase_id.date_artwork, "%Y-%m-%d")
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
                    raise ValueError(_('Please select a b2b debitor!'))
                if sale.contact_id and sale.contact_id.entity_id != sale.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if sale.address_id and sale.address_id.entity_id != sale.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if sale.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.purchase')])
        if not exists:
            raise ValueError(_('Sequence for creating PO not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.model
    def _default_template(self):

        return self.env['s2u.purchase.template'].search([('default', '=', True)], limit=1)

    @api.model
    def _default_template_so(self):

        return self.env['s2u.sale.template'].search([('default', '=', True)], limit=1)

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.onchange('dropshipping_partner_id')
    def _onchange_dropshipping_partner(self):
        if self.dropshipping_partner_id:
            delivery = self.dropshipping_partner_id.prepare_delivery()
            self.dropshipping_address = delivery

    @api.onchange('dropshipping_contact_id')
    def _onchange_dropshipping_contact(self):
        if self.dropshipping_contact_id:
            delivery = self.dropshipping_contact_id.display_company + '\n'
            if self.dropshipping_contact_id.prefix:
                delivery += '%s\n' % self.dropshipping_contact_id.prefix
            else:
                delivery += '%s\n' % self.dropshipping_contact_id.name
            if self.dropshipping_contact_id.address_id:
                if self.dropshipping_contact_id.address_id.address:
                    delivery += '%s\n' % self.dropshipping_contact_id.address_id.address
                if self.dropshipping_contact_id.address_id.zip and self.dropshipping_contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.dropshipping_contact_id.address_id.zip, self.dropshipping_contact_id.address_id.city)
                if self.dropshipping_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.dropshipping_contact_id.address_id.country_id.name
            elif self.dropshipping_partner_id:
                address = self.dropshipping_partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.dropshipping_address = delivery

    @api.onchange('dropshipping_delivery_id')
    def _onchange_dropshipping_delivery(self):
        if self.dropshipping_delivery_id:
            delivery = self.dropshipping_delivery_id.delivery_address
            self.dropshipping_address = delivery


    @api.model
    def create(self, vals):

        sale = super(Purchase, self).create(vals)
        return sale

    @api.multi
    def write(self, vals):

        res = super(Purchase, self).write(vals)
        return res

    @api.one
    def unlink(self):

        for order in self:
            if order.state != 'draft':
                raise ValidationError(_('You can not delete a confirmed order!'))

        res = super(Purchase, self).unlink()

        return res

    @api.multi
    def copy(self, default=None):

        new_sale = super(Purchase, self).copy(default=default)

        return new_sale

    @api.multi
    def action_request(self):

        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('There is nothing to purchase, please enter some lines.'))

        if self.name == 'Concept':
            self.write({
                'state': 'request',
                'date_request': fields.Date.context_today(self),
                'name': self._new_number()
            })
        else:
            self.write({
                'date_request': fields.Date.context_today(self),
                'state': 'request'
            })

    @api.multi
    def create_po_incoming(self):

        incoming_model = self.env['s2u.warehouse.incoming']

        expected = []
        for line in self.line_ids:
            if not line.for_order:
                continue
            product_qty = self.env['s2u.baseproduct.abstract'].parse_qty(line.qty)
            if line.price_per == 'item':
                product_value = line.price
            else:
                product_value = line.amount / product_qty
            vals = {
                'purchase_id': self.id,
                'product_id': line.product_id.id,
                'product_detail': line.product_detail,
                'product_qty': product_qty,
                'product_value': product_value
            }
            if line.date_delivery:
                vals['date_delivery'] = line.date_delivery
            expected.append((0, 0, vals))

        vals = {
            'entity_id': self.partner_id.id,
            'reference': self.name,
            'line_ids': expected,
            'warehouse_id': self.warehouse_id.id
        }

        if self.outgoing_id:
            vals['outgoing_id'] = self.outgoing_id.id

        incoming = incoming_model.create(vals)
        incoming.do_confirm()

        return incoming

    @api.multi
    def create_po_invoice(self):

        invoice_model = self.env['s2u.account.invoice.po']

        self.ensure_one()

        lines = []
        for t in self.line_ids:
            if not t.for_order:
                continue
            for u in t.qty_ids:
                if not u.for_order:
                    continue
                product = self.env[t.product_id.res_model].browse(t.product_id.res_id)
                name = t.product_id.name
                if t.product_detail:
                    name = '%s %s' % (name, t.product_detail)
                name = '%s %s' % (u.qty, name)
                if product.product_type == 'stock':
                    if not product.po_stock_account_id:
                        raise UserError(_('No PO stock account is defined for product %s!' % name))
                    account = product.po_stock_account_id
                else:
                    account = product.get_po_account(supplier=self.partner_id)
                    if not account:
                        raise UserError(_('No financial account is defined for product %s!' % name))
                vals = {
                    'net_amount': u.amount,
                    'account_id': account.id,
                    'descript': name,
                    'purchaseline_id': t.id
                }

                if u.analytic_id:
                    vals['analytic_id'] = u.analytic_id.id
                elif t.analytic_id:
                    vals['analytic_id'] = t.analytic_id.id

                if self.partner_id.vat_buy_id:
                    vals['vat_id'] = self.partner_id.vat_buy_id.id
                    vals['vat_amount'] = self.partner_id.vat_buy_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = self.partner_id.vat_buy_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                else:
                    vat = product.get_po_vat(supplier=self.partner_id)
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

        if lines:
            invdata = {
                'type': self.type,
                'partner_id': self.partner_id.id,
                'reference': self.name,
                'line_ids': lines
            }

            if self.currency_id:
                invdata['currency_id'] = self.currency_id.id

            if self.reference:
                invdata['reference'] = '%s (%s)' % (self.reference, self.name)

            invoice_model += invoice_model.create(invdata)

        return invoice_model

    @api.multi
    def action_confirm(self):

        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('There is nothing to purchase, please enter some lines.'))

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
        if not order:
            raise UserError(_('There is nothing to purchase, please enter some lines and mark them for ordering.'))

        if self.delivery_type == 'normal':
            self.create_po_incoming()

        # prepare invoice we expect to receive from supplier
        self.create_po_invoice()

        self.write({
            'state': 'confirm',
            'date_confirm': fields.Date.context_today(self),
        })

    @api.multi
    def action_undo(self):

        self.ensure_one()

        invlines = self.env['s2u.account.invoice.po.line'].search([('purchaseline_id', 'in', self.line_ids.ids)])
        invoice_ids = [l.invoice_id.id for l in invlines]
        invoices = self.env['s2u.account.invoice.po'].search([('id', 'in', invoice_ids)])
        invoices.unlink()

        lines = self.env['s2u.warehouse.incoming.line'].search([('purchase_id', '=', self.id)])
        incomings = []
        for t in lines:
            if t.incoming_id.state != 'draft':
                raise UserError(
                    _('Incoming shipment [%s] already confirmed! Back to concept not possible.' % t.incoming_id.name))
            incomings.append(t.incoming_id)

        lines.unlink()

        self.write({
            'state': 'draft',
            'date_request': False,
            'date_confirm': False
        })

        for i in incomings:
            if not i.line_ids and not i.pallet_ids:
                i.unlink()

    @api.multi
    def action_recreate_invoice(self):

        self.ensure_one()

        self.create_po_invoice()

    @api.multi
    def action_cancel(self):

        self.ensure_one()

        if not self.state in ['draft', 'request']:
            raise UserError(
                _('Cancel not possible!'))

        self.write({
            'state': 'cancel'
        })

    @api.multi
    def action_view_incoming(self):
        expectedlines = self.env['s2u.warehouse.incoming.line'].search([('purchase_id', '=', self.id)])
        incoming_ids = [l.incoming_id.id for l in expectedlines]
        incoming_ids = list(set(incoming_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_incoming').read()[0]
        if len(incoming_ids) > 1:
            action['domain'] = [('id', 'in', incoming_ids)]
        elif len(incoming_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_incoming_form').id, 'form')]
            action['res_id'] = incoming_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_invoice(self):
        invlines = self.env['s2u.account.invoice.po.line'].search([('purchaseline_id', 'in', self.line_ids.ids)])
        invoice_ids = [l.invoice_id.id for l in invlines]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice_po').read()[0]
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('s2uaccount.invoice_po_form').id, 'form')]
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    def _compute_template(self):

        if self.template_so_id:
            other = {
                'short_description': self.reference if self.reference else ''
            }
            self.prefix_quotation = self.template_so_id.render_template(self.template_so_id.prefix_quotation_po,
                                                                        entity=self.partner_id,
                                                                        contact=self.contact_id,
                                                                        address=self.address_id,
                                                                        other=other)
            self.postfix_quotation = self.template_so_id.render_template(self.template_so_id.postfix_quotation_po,
                                                                         entity=self.partner_id,
                                                                         contact=self.contact_id,
                                                                         address=self.address_id,
                                                                         other=other)
            self.prefix_confirmation = self.template_so_id.render_template(self.template_so_id.prefix_confirmation_po,
                                                                           entity=self.partner_id,
                                                                           contact=self.contact_id,
                                                                           address=self.address_id,
                                                                           other=other)
            self.postfix_confirmation = self.template_so_id.render_template(self.template_so_id.postfix_confirmation_po,
                                                                            entity=self.partner_id,
                                                                            contact=self.contact_id,
                                                                            address=self.address_id,
                                                                            other=other)
            self.date_display = self.template_so_id.render_template(self.template_so_id.date_display,
                                                                    date=datetime.datetime.now().strftime('%Y-%m-%d'))
        else:
            self.prefix_quotation = ''
            self.postfix_quotation = ''
            self.prefix_confirmation = ''
            self.postfix_confirmation = ''
            self.date_display = ''

    def _get_incoming_count(self):

        for purchase in self:
            expectedlines = self.env['s2u.warehouse.incoming.line'].search([('purchase_id', '=', purchase.id)])
            incoming_ids = [l.incoming_id.id for l in expectedlines]
            incoming_ids = list(set(incoming_ids))
            purchase.incoming_count = len(incoming_ids)

    def _get_invoice_count(self):

        for order in self:
            invlines = self.env['s2u.account.invoice.po.line'].search([('purchaseline_id', 'in', order.line_ids.ids)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))
            order.invoice_count = len(invoice_ids)

    @api.model
    def _default_warehouse(self):

        return self.env['s2u.warehouse'].search([('default', '=', True)])

    @api.one
    def _compute_amount(self):

        net_amount = 0.0
        gross_amount = 0.0
        for line in self.line_ids:
            net_amount += line.amount
            if line.vat_id:
                vat = line.vat_id.calc_vat_from_netto_amount(line.amount)
                gross = line.vat_id.calc_gross_amount(line.amount, vat)
                gross_amount += gross
            else:
                gross_amount += line.amount

        self.net_amount = net_amount
        self.vat_amount = gross_amount - net_amount
        self.gross_amount = gross_amount

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

    def _get_document_count(self):

        for sale in self:
            docs = self.env['s2u.document'].search([('res_model', '=', 's2u.purchase'),
                                                    ('res_id', '=', sale.id)])
            sale.document_count = len(docs.ids)

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('res_model', '=', 's2u.purchase'),
                            ('res_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.partner_id.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.name,
            'default_res_model': 's2u.purchase',
            'default_res_id': self.id
        }
        action['context'] = str(context)
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
        worksheet.write('J1', 'PO', bold)
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

        template = self.env['mail.template'].sudo().search([('model', '=', 's2u.purchase'),
                                                            ('name', '=', 'po-quotation')], limit=1)

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        ctx = dict(
            default_model='s2u.purchase',
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

        template = self.env['mail.template'].sudo().search([('model', '=', 's2u.purchase'),
                                                            ('name', '=', 'po-order')], limit=1)

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        ctx = dict(
            default_model='s2u.purchase',
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
        'request': [('readonly', False)],
    }

    name = fields.Char(string='PO', required=True, index=True, copy=False,
                       default='Concept')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    line_ids = fields.One2many('s2u.purchase.line', 'purchase_id',
                               string='Lines', copy=True, readonly=True, states=_order_state2)
    ordered_line_ids = fields.One2many('s2u.purchase.line', 'purchase_id',
                                       string='Ordered lines', copy=False, readonly=True, domain=[('for_order', '=', True)])
    type = fields.Selection([
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True)
    partner_id = fields.Many2one('s2u.crm.entity', string='Supplier', required=True, index=True,
                                 readonly=True, states=_order_state1)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                 readonly=True, states=_order_state1)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True,
                                 readonly=True, states=_order_state1)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('request', 'Request'),
        ('confirm', 'Confirmed'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', track_visibility='onchange')
    date_request = fields.Date(string='Request', index=True, copy=False,
                               readonly=True, states=_order_state1)
    date_confirm = fields.Date(string='Confirmed', index=True, copy=False,
                               readonly=True, states=_order_state1)
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Levering', index=True,
                                  ondelete='set null')
    incoming_count = fields.Integer(string='# of Deliveries', compute='_get_incoming_count', readonly=True)
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    warehouse_id = fields.Many2one('s2u.warehouse', string='Location', index=True,
                                   readonly=True, states=_order_state1, default=_default_warehouse)
    net_amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True)
    template_id = fields.Many2one('s2u.purchase.template', string='Template', default=_default_template,
                                  readonly=True, states=_order_state2)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_order_state2)
    prefix_quotation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_quotation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    prefix_confirmation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_confirmation = fields.Html('Prefix', compute=_compute_template, readonly=True)
    delivery_type = fields.Selection([
        ('normal', 'Normal'),
        ('dropshipping', 'Dropshipping'),
    ], required=True, default='normal', string='Delivery', readonly=True, states=_order_state1)
    dropshipping_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], default='b2b', string='Soort', index=True, readonly=True, states=_order_state1)
    dropshipping_partner_id = fields.Many2one('s2u.crm.entity', string='Delivery', index=True,
                                              readonly=True, states=_order_state1)
    dropshipping_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                              readonly=True, states=_order_state1)
    dropshipping_delivery_id = fields.Many2one('s2u.crm.entity.delivery', string='Delivery', index=True,
                                              readonly=True, states=_order_state1)
    dropshipping_address = fields.Text(string='Delivery address', readonly=True, states=_order_state1)
    reference = fields.Char(string='Reference', index=True, copy=False, readonly=True, states=_order_state2)
    your_reference = fields.Char(string='Your reference', index=True, copy=False)
    detailed_ids = fields.One2many('s2u.purchase.detailed', 'purchase_id',
                                   string='Details', copy=True, readonly=True, states=_order_state2)
    date_display = fields.Text('Date display', compute=_compute_template, readonly=True)
    project = fields.Char(string='Project', index=True, readonly=True, states=_order_state2)
    editions = fields.Char('Editions', compute=_compute_editions, readonly=True)
    date_delivery = fields.Date(string='Date delivery', copy=False)
    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)
    template_so_id = fields.Many2one('s2u.sale.template', string='Template', default=_default_template_so)
    use_email_address = fields.Char(string='Address for mail', readonly=True, compute='_compute_email_address')


class DropshippingLineDetailed(models.Model):
    _name = "s2u.dropshipping.line.detailed"
    _order = 'sequence'

    dropshippingline_id = fields.Many2one('s2u.dropshipping.line', string='Line', required=True, ondelete='cascade')
    detailed_label = fields.Char(string='Label', required=True)
    detailed_info = fields.Text(string='Details', required=True)
    sequence = fields.Integer(string='Sequence', default=10)


class DropshippingLine(models.Model):
    _name = "s2u.dropshipping.line"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "Dropshipping line"

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            name = '%s' % line.dropshipping_id.name
            result.append((line.id, name))
        return result

    @api.one
    @api.depends('price', 'qty', 'price_per')
    def _compute_amount(self):

        if not self.price_per or not self.price:
            self.amount = 0.0
            return

        if self.price_per == 'total':
            self.amount = self.price
            return

        qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)
        if not qty:
            self.amount = 0.0
            return

        if self.price_per == 'item':
            self.amount = round(qty * self.price, 2)
            return

        if self.price_per in ['10', '100', '1000']:
            qty = qty / float(self.price_per)
            self.amount = round(qty * self.price, 2)
            return

    @api.one
    def _compute_vat(self):

        if not self.product_id:
            self.vat_id = False
            return

        product = self.env[self.product_id.res_model].search([('id', '=', self.product_id.res_id)])
        if product:
            if self.dropshipping_id.partner_id.vat_buy_id:
                self.vat_id = self.dropshipping_id.partner_id.vat_buy_id
            else:
                self.vat_id = product.get_po_vat()
        else:
            self.vat_id = False

    dropshipping_id = fields.Many2one('s2u.dropshipping', string='Dropshipping', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='dropshipping_id.currency_id', store=True)
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
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
    date_delivery = fields.Date(string='Delivery')
    partner_id = fields.Many2one('s2u.crm.entity', string='Supplier', readonly=True,
                                 related='dropshipping_id.partner_id')
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True, domain=[('state', '=', 'confirm')],
                              ondelete='restrict')
    detailed_ids = fields.One2many('s2u.dropshipping.line.detailed', 'dropshippingline_id',
                                   string='Detailed', copy=True)
    vat_id = fields.Many2one('s2u.account.vat', string='VAT', compute=_compute_vat, readonly=True)

    @api.onchange('product_id', 'qty', 'product_detail')
    def _onchange_product(self):

        if not self.partner_id or not self.product_id or not self.product_detail or not self.qty:
            return False

        product = self.env[self.product_id.res_model].browse(self.product_id.res_id)

        purchase_info = product.get_purchase_price(self.qty, self.product_detail, ctx={
            'supplier_id': self.partner_id.id
        })
        if purchase_info:
            self.price = purchase_info['price']
            self.price_per = 'total'

        return False

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(DropshippingLine, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(DropshippingLine, self).write(vals)


class Dropshipping(models.Model):
    _name = "s2u.dropshipping"
    _description = "Dropshipping"
    _order = "name desc"

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for sale in self:
            if sale.type == 'b2b':
                if sale.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b debitor!'))
                if sale.contact_id and sale.contact_id.entity_id != sale.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if sale.address_id and sale.address_id.entity_id != sale.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if sale.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.purchase')])
        if not exists:
            raise ValueError(_('Sequence for creating PO not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.model
    def create(self, vals):

        sale = super(Dropshipping, self).create(vals)
        return sale

    @api.multi
    def write(self, vals):

        res = super(Dropshipping, self).write(vals)
        return res

    @api.one
    def unlink(self):

        for order in self:
            if order.state != 'draft' and order.state != 'cancel':
                raise ValidationError(_('You can not delete a confirmed order!'))

        res = super(Dropshipping, self).unlink()

        return res

    @api.multi
    def copy(self, default=None):

        new_sale = super(Dropshipping, self).copy(default=default)

        return new_sale

    @api.multi
    def action_request(self):

        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('There is nothing to purchase, please enter some lines.'))

        if self.name == 'Concept':
            self.write({
                'state': 'request',
                'name': self._new_number()
            })
        else:
            self.write({
                'state': 'request'
            })

    @api.multi
    def action_confirm(self):

        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('There is nothing to purchase, please enter some lines.'))

        if self.name == 'Concept':
            self.write({
                'state': 'to_transfer',
                'name': self._new_number()
            })
        else:
            self.write({
                'state': 'to_transfer'
            })

    @api.multi
    def action_transfer(self):

        self.ensure_one()

        self.write({
            'state': 'transfered'
        })

    @api.multi
    def action_done(self):

        self.ensure_one()

        sales_orders = []
        for line in self.line_ids:
            sales_orders.append(line.sale_id.id)
        sales_orders = list(set(sales_orders))

        for so in self.env['s2u.sale'].browse(sales_orders):
            so.sale_is_completed()

        self.write({
            'state': 'done'
        })

    @api.multi
    def action_cancel(self):

        self.ensure_one()

        self.write({
            'state': 'cancel'
        })

    @api.multi
    def action_undo(self):

        self.ensure_one()

        self.write({
            'state': 'draft',
        })

    @api.onchange('delivery_partner_id')
    def _onchange_delivery_partner(self):
        if self.delivery_partner_id:
            delivery = self.delivery_partner_id.prepare_delivery()
            self.delivery_address = delivery

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
            elif self.delivery_contact_id:
                address = self.delivery_contact_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    _order_state1 = {
        'draft': [('readonly', False)],
    }

    _order_state2 = {
        'draft': [('readonly', False)],
        'request': [('readonly', False)],
    }

    name = fields.Char(string='PO', required=True, index=True, copy=False,
                       default='Concept')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    line_ids = fields.One2many('s2u.dropshipping.line', 'dropshipping_id',
                               string='Lines', copy=True, readonly=True, states=_order_state2)
    type = fields.Selection([
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True)
    partner_id = fields.Many2one('s2u.crm.entity', string='Supplier', required=True, index=True,
                                 readonly=True, states=_order_state1)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                 readonly=True, states=_order_state1)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True,
                                 readonly=True, states=_order_state1)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('request', 'Request'),
        ('to_transfer', 'To transfer'),
        ('transfered', 'Transfered'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State')
    date_entry = fields.Date(string='Date', index=True, copy=False,
                             readonly=True, states=_order_state1,
                             default=lambda self: fields.Date.context_today(self))
    date_transfered = fields.Date(string='Transfered', index=True, copy=False,
                                  readonly=True, states=_order_state1)
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_order_state1)
    delivery_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True,
                                          readonly=True, states=_order_state1)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                          readonly=True, states=_order_state1)
    delivery_address = fields.Text(string='Delivery', readonly=True, states=_order_state1)
