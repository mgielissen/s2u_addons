# -*- coding: utf-8 -*-

import datetime
import re

from openerp.tools.misc import formatLang
from openerp.osv import expression
from openerp.exceptions import UserError, ValidationError
from openerp import api, fields, models, _


class CalcFixCosts(models.Model):
    _name = "s2u.intermediair.calc.fix.costs"
    _description = "Fix costs in calculation"

    @api.one
    @api.depends('fix_price', 'surcharge')
    def _compute_amount(self):

        if self.fix_price and self.surcharge:
            self.amount = self.fix_price + (self.fix_price * self.surcharge / 100.0)
        elif self.fix_price:
            self.amount = self.fix_price
        else:
            self.amount = False

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='calc_id.currency_id', store=True)
    name = fields.Char(string='Omschrijving', required=True)
    fix_price = fields.Monetary(string='Kostprijs', currency_field='currency_id', required=True)
    surcharge = fields.Float(string='Marge in %', default=10.0, required=True)
    amount = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_amount,
                             readonly=True, store=True)


class CalcDynamicCosts(models.Model):
    _name = "s2u.intermediair.calc.dynamic.costs"
    _description = "Dynamic costs in calculation"

    @api.model
    def _default_surcharge(self):

        return 10.0

    @api.one
    @api.depends('qty', 'calc_price', 'surcharge', 'calc_id.kickback')
    def _compute_amount(self):

        if self.qty:
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)

        if self.calc_id.partner_id.vat_sell_id:
            vat = self.calc_id.partner_id.vat_sell_id
        elif self.product_id:
            vat = self.product_id.get_so_vat()
        else:
            vat = False

        if self.calc_price and self.surcharge:
            self.calc_net_amount = self.calc_price + (self.calc_price * self.surcharge / 100.0)
        elif self.calc_price:
            self.calc_net_amount = self.calc_price
        else:
            self.calc_net_amount = 0.0

        if self.calc_id.kickback:
            try:
                self.calc_amount_kickback = self.calc_net_amount / (1.0 - (self.calc_id.kickback / 100.0))
            except:
                raise UserError(_('Please enter valid kickback!'))
        else:
            self.calc_amount_kickback = self.calc_net_amount

        if vat:
            self.calc_vat_amount = vat.calc_vat_from_netto_amount(self.calc_amount_kickback)
            self.calc_gross_amount = vat.calc_gross_amount(self.calc_amount_kickback, self.calc_vat_amount)
        else:
            self.calc_vat_amount = 0.0
            self.calc_gross_amount = self.calc_amount_kickback

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='calc_id.currency_id', store=True)
    name = fields.Char(string='Omschrijving', required=True)
    calc_price = fields.Monetary(string='Calculatie', currency_field='currency_id', required=True)
    after_price = fields.Monetary(string='Nacalculatie', currency_field='currency_id')
    pos = fields.Selection([
        ('pos1', 'Staffel 1.'),
        ('pos2', 'Staffel 2.'),
        ('pos3', 'Staffel 3.'),
        ('pos4', 'Staffel 4.'),
        ('pos5', 'Staffel 5.'),
        ('once', 'Detail')
    ], required=True, default='pos1', string='Pos')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict')
    product_id = fields.Many2one('s2u.sale.product', string='Eindproduct')
    product_detail = fields.Char(string='Details')
    qty = fields.Char(string='Aantal', default='1')
    calc_net_amount = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_amount,
                                      readonly=True)
    calc_amount_kickback = fields.Monetary(string='Amount (kb)', currency_field='currency_id', compute=_compute_amount,
                                           readonly=True)
    calc_vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                      readonly=True)
    calc_gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                        readonly=True)
    surcharge = fields.Float(string='Marge in %', default=_default_surcharge, required=True)


class CalcTotals(models.Model):
    _name = "s2u.intermediair.calc.totals"
    _order = 'pos'

    @api.one
    def _compute_amount(self):

        net_amount = 0.0
        for fix in self.calc_id.fixcosts_ids:
            net_amount += fix.amount

        for var in self.calc_id.calc_po_ids:
            if var.pos != self.pos:
                continue
            # inkoop niet doorberekenen aan de eindklant
            if not var.pass_on:
                continue
            net_amount += var.calc_amount

        for stock in self.calc_id.stock_ids:
            if stock.pos != self.pos:
                continue
            net_amount += stock.amount

        for var in self.calc_id.dynamic_cost_ids:
            if var.pos != self.pos:
                continue
            net_amount += var.calc_net_amount

        if self.calc_id.partner_id.vat_sell_id:
            vat = self.calc_id.partner_id.vat_sell_id
        elif self.calc_id.product_id:
            vat = self.calc_id.product_id.get_so_vat()
        else:
            vat = False

        self.net_amount = net_amount
        if self.calc_id.kickback:
            try:
                self.net_amount_kickback = net_amount / (1.0 - (self.calc_id.kickback / 100.0))
            except:
                raise UserError(_('Please enter valid kickback!'))
        else:
            self.net_amount_kickback = net_amount

        if self.price_per:
            try:
                if self.price_per in ['total']:
                    self.amount_price_per = self.net_amount_kickback
                elif self.price_per == 'item':
                    self.amount_price_per = round(self.net_amount_kickback / self.product_qty, 2)
                else:
                    self.amount_price_per = round(self.net_amount_kickback / self.product_qty * float(self.price_per), 2)
            except:
                self.amount_price_per = 0.0
        else:
            self.amount_price_per = 0.0

        if vat:
            self.vat_amount = vat.calc_vat_from_netto_amount(self.net_amount_kickback)
            self.gross_amount = vat.calc_gross_amount(net_amount, self.vat_amount)
        else:
            self.vat_amount = 0.0
            self.gross_amount = self.net_amount_kickback

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='calc_id.currency_id', store=True)
    net_amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True)
    net_amount_kickback = fields.Monetary(string='Amount (kb)', currency_field='currency_id', compute=_compute_amount,
                                          readonly=True)
    qty = fields.Char(string='Oplage', required=True)
    distribution = fields.Char(string='Distribution')
    product_qty = fields.Float(string='Oplage')
    pos = fields.Selection([
        ('pos1', 'Staffel 1.'),
        ('pos2', 'Staffel 2.'),
        ('pos3', 'Staffel 3.'),
        ('pos4', 'Staffel 4.'),
        ('pos5', 'Staffel 5.'),
    ], required=True, default='pos1', string='Pos')
    salelineqty_id = fields.Many2one('s2u.sale.line.qty', string='Sale line qty', index=True, ondelete='set null', copy=False)
    price_per = fields.Selection([
        ('item', 'Item'),
        ('10', 'per 10'),
        ('100', 'per 100'),
        ('1000', 'per 1000'),
        ('total', 'Total')
    ], required=True, default='total', string='Pricing')
    amount_price_per = fields.Monetary(string='Amount per', currency_field='currency_id', compute=_compute_amount,
                                       readonly=True)
    product_detail = fields.Char(string='Details')

    _sql_constraints = [
        ('pos_calc_uniq', 'unique (pos, calc_id)', 'Double pos used !')
    ]

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        sale = super(CalcTotals, self).create(vals)
        return sale

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        res = super(CalcTotals, self).write(vals)
        return res


class CalcDeliveryAddress(models.Model):
    _name = "s2u.intermediair.calc.delivery.address"

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
                if self.delivery_contact_id.address_id.address:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.address
                if self.delivery_contact_id.address_id.zip and self.delivery_contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.delivery_contact_id.address_id.zip, self.delivery_contact_id.address_id.city)
                elif self.delivery_contact_id.address_id.city:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.city
                if self.delivery_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.country_id.name
            elif self.delivery_partner_id:
                address = self.delivery_partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    elif address.city:
                        delivery += '%s\n' % address.city
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

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type')
    delivery_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact')
    delivery_delivery_id = fields.Many2one('s2u.crm.entity.delivery', string='Delivery')
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


class CalcLabelGroup(models.Model):
    _name = "s2u.intermediair.label.group"

    name = fields.Char(required=True, index=True, string='Group', translate=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)


class CalcLabel(models.Model):
    _name = "s2u.intermediair.label"
    _order = 'sequence,id'

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for label in self:
            if label.code:
                name = label.name + ' (' + label.code + ')'
            else:
                name = label.name
            result.append((label.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        labels = self.search(domain + args, limit=limit)
        return labels.name_get()

    name = fields.Char(required=True, index=True, string='Label', translate=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    code = fields.Char(index=True, string='Code')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    default_value = fields.Text(string='Default value')
    use_as_default = fields.Boolean(string='Use as default', default=False)
    show_on_so = fields.Boolean(string='Show on SO', default=True)
    show_on_po = fields.Boolean(string='Show on PO', default=False)
    show_on_invoice = fields.Boolean(string='Show on invoice', default=False)
    group_id = fields.Many2one('s2u.intermediair.label.group', string='Group')

    def calc_value(self, calc, obj, value, label):

        MONTHS = [_('januar'), _('februar'), _('march'),
                  _('april'), _('may'), _('june'),
                  _('july'), _('august'), _('september'),
                  _('october'), _('november'), _('december')]

        if not value:
            return ''

        match = re.search(r'.*\{\{(?P<value>.+)\}\}.*', value)
        if not match:
            return value

        if match.group('value') == 'order-number':
            return value.replace('{{order-number}}', obj.name if obj.name else '')

        if match.group('value') == 'reference':
            return value.replace('{{reference}}', obj.reference if obj.reference else '')

        if match.group('value') == 'customer_code':
            return value.replace('{{customer_code}}', obj.customer_code if obj.customer_code else '')

        if match.group('value') == 'project':
            return value.replace('{{project}}', obj.project if obj.project else '')

        if match.group('value') == 'qty':
            if obj.line_ids and obj.line_ids[0].qty:
                return value.replace('{{qty}}', obj.line_ids[0].qty if obj.line_ids[0].qty else '')
            return ''

        if match.group('value') == 'distribution':
            if obj.line_ids and obj.line_ids[0].distribution:
                return value.replace('{{distribution}}', obj.line_ids[0].distribution if obj.line_ids[0].distribution else '')
            return ''

        if match.group('value') == 'total-amount':
            if obj.line_ids and obj.line_ids[0].amount:
                return value.replace('{{total-amount}}', formatLang(self.env, obj.line_ids[0].amount, currency_obj=obj.currency_id))
            return 0.0

        if match.group('value') == 'delivery':
            if hasattr(obj, 'delivery_address'):
                if obj.delivery_address:
                    return value.replace('{{delivery}}', obj.delivery_address if obj.delivery_address else '')
            if hasattr(obj, 'dropshipping_address'):
                if obj.dropshipping_address:
                    return value.replace('{{delivery}}', obj.dropshipping_address if obj.dropshipping_address else '')
            return ''

        if match.group('value') == 'payment-terms':
            if obj.invoice_partner_id and obj.invoice_partner_id.payment_term_id and obj.invoice_partner_id.payment_term_id.name:
                return value.replace('{{payment-terms}}', obj.invoice_partner_id.payment_term_id.name)
            return ''

        if match.group('value') == 'detail':
            amount_detail = 0.0
            if label:
                for line in obj.line_ids:
                    if line.label_id.id == label.id:
                        amount_detail += line.amount
            return value.replace('{{detail}}', formatLang(self.env, amount_detail, currency_obj=obj.currency_id))

        if match.group('value') == 'date-delivery':
            if hasattr(obj, 'date_delivery') and obj.date_delivery:
                date_delivery = datetime.datetime.strptime(obj.date_delivery, "%Y-%m-%d")
                date_delivery = '%d %s %d' % (date_delivery.day, MONTHS[date_delivery.month - 1], date_delivery.year)
                return value.replace('{{date-delivery}}', date_delivery)
            else:
                return value.replace('{{date-delivery}}', '')

        if match.group('value') == 'date-artwork':
            if hasattr(obj, 'date_artwork') and obj.date_artwork:
                date_artwork = datetime.datetime.strptime(obj.date_artwork, "%Y-%m-%d")
                date_artwork = '%d %s %d' % (date_artwork.day, MONTHS[date_artwork.month - 1], date_artwork.year)
                return value.replace('{{date-artwork}}', date_artwork)
            else:
                return value.replace('{{date-artwork}}', '')

        return value


class CalcDetail(models.Model):
    _name = "s2u.intermediair.calc.detail"
    _order = 'sequence,id'

    @api.onchange('label_id')
    def _onchange_type(self):
        if self.label_id:
            if self.label_id.default_value:
                self.value = self.label_id.default_value
            self.display = 'both'
            self.on_invoice = False


    @api.multi
    def name_get(self):
        result = []
        for detail in self:
            name = '%s' % detail.label_id.name
            result.append((detail.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=5):
        args = args or []
        domain = []
        if name:
            domain = [('label_id.name', '=ilike', name + '%')]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        details = self.search(domain + args, limit=limit)
        return details.name_get()

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    label_id = fields.Many2one('s2u.label', string='Label', required=True)
    value = fields.Text(string='Value')
    display = fields.Selection([
        ('both', 'Quotation and Order'),
        ('quotation', 'Quotation only'),
        ('order', 'Order only')
    ], required=True, default='both', string='Display')
    on_invoice = fields.Boolean(string='On invoice')


class CalcStock(models.Model):
    _name = "s2u.intermediair.calc.stock"

    @api.one
    @api.depends('product_qty', 'product_id', 'surcharge', 'calc_id.kickback')
    def _compute_amount(self):

        self.item_price = 0.0
        if self.product_qty and self.product_id:
            self.item_price = self.product_id.product_value
            self.fix_price = round(self.product_qty * self.product_id.product_value, 2)

            if self.surcharge:
                self.amount = self.fix_price + (self.fix_price * self.surcharge / 100.0)
            else:
                self.amount = self.fix_price

            if self.calc_id.partner_id.vat_sell_id:
                vat = self.calc_id.partner_id.vat_sell_id
            elif self.calc_id.product_id.get_so_vat():
                vat = self.calc_id.product_id.get_so_vat()
            else:
                vat = False

            if self.calc_id.kickback:
                try:
                    self.net_amount_kickback = self.amount / (1.0 - (self.calc_id.kickback / 100.0))
                except:
                    raise UserError(_('Please enter valid kickback!'))
            else:
                self.net_amount_kickback = self.amount

            if vat:
                self.vat_amount = vat.calc_vat_from_netto_amount(self.net_amount_kickback)
                self.gross_amount = vat.calc_gross_amount(self.amount, self.vat_amount)
            else:
                self.vat_amount = 0.0
                self.gross_amount = self.net_amount_kickback
        else:
            self.item_price = 0.0
            self.fix_price = 0.0
            self.amount = 0.0
            self.net_amount_kickback = 0.0
            self.vat_amount = 0.0
            self.gross_amount = 0.0

    @api.one
    def _compute_used_amount(self):

        used_amount = 0.0
        if self.reservedline_id and self.reservedline_id.usedmaterials_id.state == 'done':
            used_amount = self.reservedline_id.product_qty * self.reservedline_id.product_value
        self.used_amount = used_amount

    @api.onchange('unit_id')
    def onchange_unit(self):

        if not self.unit_id:
            return {'domain': {'product_id': [('unit_id', '=', False)]}}

        return {'domain': {'product_id': [('unit_id', '=', self.unit_id.id)]}}

    @api.one
    @api.constrains('product_qty')
    def _check_qty(self):
        if self.product_qty <= 0.0:
                raise ValidationError(_('Calculation qty must have a positive value!'))

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    pos = fields.Selection([
        ('pos1', 'Staffel 1.'),
        ('pos2', 'Staffel 2.'),
        ('pos3', 'Staffel 3.'),
        ('pos4', 'Staffel 4.'),
        ('pos5', 'Staffel 5.'),
    ], required=True, default='pos1', string='Pos')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True,
                              ondelete='restrict')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', related='unit_id.location_id',
                                  readonly=True)
    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Product', required=True, index=True,
                                 ondelete='restrict')
    product_qty = fields.Float(string='Qty', required=True)
    reserve = fields.Boolean(string='Reserve', default=True)
    currency_id = fields.Many2one('res.currency', related='calc_id.currency_id', store=True)
    item_price = fields.Float(string='Per stuk', digits=(16, 5), compute=_compute_amount, readonly=True)
    fix_price = fields.Monetary(string='Kostprijs', currency_field='currency_id', compute=_compute_amount,
                                readonly=True)
    surcharge = fields.Float(string='Marge in %', default=10.0, required=True)
    amount = fields.Monetary(string='# Amount', currency_field='currency_id', compute=_compute_amount,
                             readonly=True)
    net_amount_kickback = fields.Monetary(string='Amount (kb)', currency_field='currency_id', compute=_compute_amount,
                                          readonly=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True)
    reservedline_id = fields.Many2one('s2u.warehouse.production.used.materials.line.item', string='Reserved', copy=False)
    used_amount = fields.Monetary(string='# Used', currency_field='currency_id', compute=_compute_used_amount,
                                  readonly=True)


class CalcPurchase(models.Model):
    _name = "s2u.intermediair.calc.purchase"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _order = "sequence, id"

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        res = super(CalcPurchase, self).create(vals)
        return res

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        res = super(CalcPurchase, self).write(vals)
        return res

    @api.one
    def _compute_netto(self):

        if self.calc_id.partner_id.vat_sell_id:
            vat = self.calc_id.partner_id.vat_sell_id
        elif self.calc_id.product_id.get_so_vat():
            vat = self.calc_id.product_id.get_so_vat()
        else:
            vat = False

        if self.calc_id.kickback:
            try:
                self.net_amount_kickback = self.calc_amount / (1.0 - (self.calc_id.kickback / 100.0))
            except:
                raise UserError(_('Please enter valid kickback!'))
        else:
            self.net_amount_kickback = self.calc_amount

        if vat:
            self.vat_amount = vat.calc_vat_from_netto_amount(self.net_amount_kickback)
            self.gross_amount = vat.calc_gross_amount(self.calc_amount, self.vat_amount)
        else:
            self.vat_amount = 0.0
            self.gross_amount = self.net_amount_kickback

    @api.one
    @api.depends('qty', 'product_id', 'product_detail', 'calc_id.kickback')
    def _compute_amount(self):
        if self.po_amount_fixed or self.po_amount_locked:
            lines = self.env['s2u.sale.line'].search([('intermediair_calc_id', '=', self.calc_id.id)])
            if lines:
                # SO is gemaakt, dus werken met PO bedrag waarmee de SO is berekend
                if self.surcharge:
                    self.calc_amount_base = self.po_amount_fixed
                    self.calc_amount = (self.po_amount_fixed * self.surcharge / 100.0) + self.po_amount_fixed
                else:
                    self.calc_amount_base = self.po_amount_fixed
                    self.calc_amount = self.po_amount_fixed
                self._compute_netto()
                return

        self.calc_amount_base = 0.0
        self.calc_amount = 0.0

        qtys = self.env['s2u.purchase.line.qty'].search([('intermediair_calc_id', '=', self.calc_id.id),
                                                         ('qty', '=', self.qty)])
        if qtys:
            for qty in qtys:
                if not (qty.purchaseline_id.product_id.id == self.product_id.id and qty.purchaseline_id.product_detail == self.product_detail):
                    continue
                if qty.purchaseline_id.purchase_id.state == 'cancel':
                    continue
                if not qty.amount:
                    continue
                if qty.amount < self.calc_amount or self.calc_amount == 0.0:
                    self.calc_amount = qty.amount

        if self.calc_amount:
            self.calc_amount_base = self.calc_amount
            if self.surcharge:
                self.calc_amount = (self.calc_amount * self.surcharge / 100.0) + self.calc_amount
        self._compute_netto()
        return

    @api.model
    def _default_surcharge(self):

        return 10.0

    calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='calc_id.currency_id', store=True)
    sequence = fields.Integer(string='Sequence', default=1, required=True)
    pos = fields.Selection([
        ('pos1', 'Staffel 1.'),
        ('pos2', 'Staffel 2.'),
        ('pos3', 'Staffel 3.'),
        ('pos4', 'Staffel 4.'),
        ('pos5', 'Staffel 5.'),
        ('once', 'Label')
    ], required=True, default='pos1', string='Pos')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict')
    qty = fields.Char(string='Qty', required=True)
    surcharge = fields.Float(string='Marge in %', default=_default_surcharge, required=True)
    calc_amount = fields.Monetary(string='Calc.', currency_field='currency_id', compute=_compute_amount,
                                  readonly=True)
    calc_amount_base = fields.Monetary(string='Calc.', currency_field='currency_id', compute=_compute_amount,
                                       readonly=True)
    po_amount_fixed = fields.Monetary(string='PO amount fixed', currency_field='currency_id')
    po_amount_locked = fields.Boolean(string='Locked', default=False)
    distribution = fields.Char(string='Distribution')
    net_amount_kickback = fields.Monetary(string='Amount (kb)', currency_field='currency_id', compute=_compute_amount,
                                          readonly=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True)
    purchaseline_id = fields.Many2one('s2u.purchase.line', string='Purchase', copy=False)
    pass_on = fields.Boolean(string='Pass on', default=True)
    distribution = fields.Char(default='{{distribution}}')


class Calc(models.Model):
    _name = "s2u.intermediair.calc"
    _description = "Calculation"
    _inherit = ['mail.thread']
    _order = "id desc"

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for calc in self:
            if calc.type == 'b2b':
                if calc.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b debitor!'))
                if calc.contact_id and calc.contact_id.entity_id != calc.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if calc.address_id and calc.address_id.entity_id != calc.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if calc.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.multi
    @api.constrains('invoice_type', 'invoice_partner_id', 'invoice_contact_id', 'invoice_address_id')
    def _check_address_invoice(self):
        for calc in self:
            if calc.invoice_is_sale_address:
                continue
            if calc.invoice_type == 'b2b':
                if calc.invoice_partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b invoice!'))
                if calc.invoice_contact_id and calc.invoice_contact_id.entity_id != calc.invoice_partner_id:
                    raise ValueError(_('Contact does not belong to the selected invoice!'))
                if calc.invoice_address_id and calc.invoice_address_id.entity_id != calc.invoice_partner_id:
                    raise ValueError(_('Address does not belong to the selected invoice!'))
            else:
                if calc.invoice_partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c invoice!'))

    @api.multi
    @api.constrains('delivery_type', 'delivery_partner_id', 'delivery_contact_id')
    def _check_address_delivery(self):
        for calc in self:
            if calc.delivery_is_sale_address:
                continue
            if calc.delivery_type == 'b2b':
                if calc.delivery_partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b delivery!'))
                if calc.delivery_contact_id and calc.delivery_contact_id.entity_id != calc.delivery_partner_id:
                    raise ValueError(_('Contact does not belong to the selected delivery!'))
            else:
                if calc.delivery_partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c delivery!'))

    @api.multi
    @api.constrains('load_type', 'load_entity_id')
    def _check_address_loading(self):
        for out in self:
            if out.load_type == 'b2b' and out.load_entity_id:
                if out.load_entity_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b loading!'))
            elif out.load_entity_id:
                if out.load_entity_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c loading!'))

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

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

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.partner_id:
            self.surcharge = 10.0
            self.kickback = 0.0
        else:
            self.surcharge = 10.0
            self.kickback = 0.0


    @api.onchange('kickback_id')
    def _onchange_kickback(self):
        if self.kickback_id:
            if self.kickback_id.intermediair_kickback:
                self.kickback = self.kickback_id.intermediair_kickback
            else:
                self.kickback = 0.0

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.onchange('invoice_contact_id')
    def _onchange_invoice_contact(self):
        if self.invoice_contact_id:
            if self.invoice_contact_id.address_id:
                self.invoice_address_id = self.invoice_contact_id.address_id

    @api.onchange('layout_id')
    def _onchange_layout(self):
        if self.layout_id:
            detail_ids = []
            for layout_label in self.layout_id.label_so_ids:
                vals = {
                    'label_id': layout_label.label_id.id,
                    'sequence': layout_label.sequence,
                    'display': layout_label.display,
                    'on_invoice': layout_label.on_invoice
                }
                if layout_label.default_value:
                    vals['value'] = layout_label.default_value
                elif layout_label.label_id.default_value:
                    vals['value'] = layout_label.label_id.default_value
                detail_ids.append((0, 0, vals))
            self.detail_ids = detail_ids

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
                elif self.delivery_contact_id.address_id.city:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.city
                if self.delivery_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.country_id.name
            elif self.delivery_partner_id:
                address = self.delivery_partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    elif address.city:
                        delivery += '%s\n' % address.city
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
    def _new_reference(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.intermediair.calc')])
        if not exists:
            raise ValueError(_('Sequence for creating calculation number (s2u.intermediair.calc) not exists!'))
        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def create(self, vals):

        vals['reference'] = self._new_reference()
        if not self.analytic_id:
            analytic = self.env['s2u.account.analytic'].create({
                'name': vals['reference']
            })
            vals['analytic_id'] = analytic.id

        return super(Calc, self).create(vals)

    @api.one
    def unlink(self):

        for calc in self:
            if not calc.state in ['draft', 'cancel']:
                raise ValidationError(_('You can not delete a confirmed calculation!'))
            if calc.analytic_id:
                calc.analytic_id.unlink()

        res = super(Calc, self).unlink()

        return res

    @api.multi
    def copy(self, default=None):

        new_calc = super(Calc, self).copy(default=default)
        if not new_calc.analytic_id:
            analytic = self.env['s2u.account.analytic'].create({
                'name': new_calc.reference
            })
            new_calc.write({
                'analytic_id': analytic.id
            })

        return new_calc

    @api.model
    def default_get(self, fields):
        res = super(Calc, self).default_get(fields)

        res['fixcosts_ids'] = []
        res['fixcosts_ids'].append((5,))
        res['fixcosts_ids'].append(
            (0, 0, {
                'name': 'Orderkosten',
                'fix_price': 25.0,
                'surcharge': 10.0,
                'amount': 25.0 * 1.1
            })
        )

        res['fixcosts_ids'].append(
            (0, 0, {
                'name': 'Administratie kosten',
                'fix_price': 15.0,
                'surcharge': 10.0,
                'amount': 15.0 * 1.1
            })
        )

        res['detail_ids'] = []
        res['detail_ids'].append((5,))
        layout = self.env['s2u.layout'].search([('use_as_default', '=', True)])
        if layout:
            for layout_label in layout.label_so_ids:
                vals = {
                    'label_id': layout_label.label_id.id,
                    'sequence': layout_label.sequence,
                    'display': layout_label.display,
                    'on_invoice': layout_label.on_invoice
                }
                if layout_label.default_value:
                    vals['value'] = layout_label.default_value
                elif layout_label.label_id.default_value:
                    vals['value'] = layout_label.label_id.default_value
                res['detail_ids'].append((0, 0, vals))

        return res

    @api.multi
    @api.constrains('kickback')
    def _check_kickback(self):
        if self.kickback:
            if self.kickback < 0.0 or self.kickback > 99.99:
                    raise ValueError(_('Please enter valid kickback!'))

    @api.one
    def _compute_amount(self):

        use_pos = []
        self.net_amount = 0.0
        self.vat_amount = 0.0
        self.net_amount_kickback = 0.0
        self.gross_amount = 0.0
        self.qty = ''
        if self.state not in ['order', 'confirm']:
            if self.totals_ids:
                self.net_amount = self.totals_ids[0].net_amount
                self.vat_amount = self.totals_ids[0].vat_amount
                self.net_amount_kickback = self.totals_ids[0].net_amount_kickback
                self.gross_amount = self.totals_ids[0].gross_amount
                self.qty = self.totals_ids[0].qty
                use_pos.append(self.totals_ids[0].pos)
        else:
            for totals in self.totals_ids:
                if totals.salelineqty_id and totals.salelineqty_id.for_order:
                    self.net_amount += totals.net_amount
                    self.vat_amount += totals.vat_amount
                    self.net_amount_kickback += totals.net_amount_kickback
                    self.gross_amount += totals.gross_amount
                    use_pos.append(totals.pos)
                    if not self.qty:
                        self.qty = totals.qty

        pre_amount = 0.0

        for var in self.calc_po_ids:
            if var.pos != 'once' and var.pos not in use_pos:
                continue
            pre_amount += var.calc_amount_base

            if var.pos == 'once' and var.pass_on:
                self.net_amount += var.calc_amount
                self.vat_amount += var.vat_amount
                self.net_amount_kickback += var.net_amount_kickback
                self.gross_amount += var.gross_amount

        for stock in self.stock_ids:
            if stock.pos not in use_pos:
                continue
            pre_amount += stock.fix_price

        for var in self.dynamic_cost_ids:
            if var.pos != 'once' and var.pos not in use_pos:
                continue
            if var.calc_price:
                pre_amount += var.calc_price

            if var.pos == 'once':
                if var.calc_price:
                    self.net_amount += var.calc_net_amount
                    self.vat_amount += var.calc_vat_amount
                    self.net_amount_kickback += var.calc_amount_kickback
                    self.gross_amount += var.calc_gross_amount

        if self.analytic_id:
            po_amount = self.analytic_id.credit
        else:
            po_amount = 0.0

        self.po_amount = po_amount
        self.pre_amount = pre_amount

        if self.po_amount and self.net_amount:
            self.po_amount_delta = self.net_amount - self.po_amount
            self.po_marge = round(self.po_amount_delta / po_amount * 100.0, 2)
        else:
            self.po_amount_delta = 0.0
            self.po_marge = False

        if self.pre_amount and self.net_amount:
            self.pre_amount_delta = self.net_amount - self.pre_amount
            self.pre_marge = round(self.pre_amount_delta / pre_amount * 100.0, 2)
        else:
            self.pre_amount_delta = 0.0
            self.pre_marge = False

    def create_quotation(self, calc, reuse_so=False, main_project=False):

        if not reuse_so:
            delivery_addresses = []
            for delivery in calc.delivery_ids:
                vals = {
                    'delivery_type': delivery.delivery_type,
                    'delivery_partner_id': delivery.delivery_partner_id.id if delivery.delivery_partner_id else False,
                    'delivery_contact_id': delivery.delivery_contact_id.id if delivery.delivery_contact_id else False,
                    'delivery_address': delivery.delivery_address,
                    'load_type': delivery.load_type,
                    'load_entity_id': delivery.load_entity_id.id if delivery.load_entity_id else False,
                    'load_address': delivery.load_address,
                    'trailer_no': delivery.trailer_no,
                    'delivery_country_id': delivery.delivery_country_id.id if delivery.delivery_country_id else False,
                    'delivery_tinno': delivery.delivery_tinno,
                    'delivery_lang': delivery.delivery_lang
                }
                delivery_addresses.append((0, 0, vals))

            vals = {
                'type': calc.type,
                'partner_id': calc.partner_id.id,
                'contact_id': calc.contact_id.id if calc.contact_id else False,
                'address_id': calc.address_id.id if calc.address_id else False,
                'invoice_is_sale_address': calc.invoice_is_sale_address,
                'invoice_type': calc.invoice_type,
                'invoice_partner_id': calc.invoice_partner_id.id,
                'invoice_contact_id': calc.invoice_contact_id.id if calc.invoice_contact_id else False,
                'invoice_address_id': calc.invoice_address_id.id if calc.invoice_address_id else False,
                'delivery_is_sale_address': calc.delivery_is_sale_address,
                'delivery_type': calc.delivery_type,
                'delivery_partner_id': calc.delivery_partner_id.id,
                'delivery_contact_id': calc.delivery_contact_id.id if calc.delivery_contact_id else False,
                'delivery_address': calc.delivery_address,
                'delivery_country_id': calc.delivery_country_id.id if calc.delivery_country_id else False,
                'delivery_tinno': calc.delivery_tinno,
                'customer_code': calc.customer_code,
                'project': main_project if main_project else calc.name,
                'invoicing': 'confirm',
                'date_delivery': calc.date_delivery,
                'delivery_ids': delivery_addresses,
                'intermediair_calc_id': calc.id
            }
            if calc.reference:
                vals['reference'] = calc.reference
            else:
                vals['reference'] = main_project if main_project else calc.name
            quotation = calc.env['s2u.sale'].create(vals)
        else:
            quotation = reuse_so

        product = calc.env['s2u.baseproduct.item'].search([('res_model', '=', 's2u.sale.product'),
                                                           ('res_id', '=', calc.product_id.id)])

        sale_line = {
            'sale_id': quotation.id,
            'product_id': product[0].id,
            'product_detail': calc.product_detail,
            'intermediair_calc_id': calc.id,
            'project': calc.name
        }
        if calc.analytic_id:
            sale_line['analytic_id'] = calc.analytic_id.id

        sale_line = calc.env['s2u.sale.line'].create(sale_line)

        for totals in calc.totals_ids:
            qty = calc.env['s2u.baseproduct.abstract'].parse_qty(totals.qty)

            if qty:
                if totals.price_per in ['total']:
                    price = totals.net_amount_kickback

                if totals.price_per == 'item':
                    price = totals.net_amount_kickback / qty

                if totals.price_per in ['10', '100', '1000']:
                    price = totals.net_amount_kickback / qty
                    price = price * float(totals.price_per)
            else:
                price = 0.0

            qty_line = {
                'saleline_id': sale_line.id,
                'qty': totals.qty,
                'distribution': totals.distribution,
                'price': price,
                'price_per': totals.price_per,
            }
            sale_line_qty = calc.env['s2u.sale.line.qty'].create(qty_line)
            totals.write({
                'salelineqty_id': sale_line_qty.id
            })

        for po in calc.calc_po_ids:
            if po.pos == 'once':
                product_line = {
                    'saleline_id': sale_line.id,
                    'product_id': po.product_id.id,
                    'product_detail': po.product_detail,
                    'qty': po.qty,
                    'amount': po.calc_amount if po.pass_on else 0.0,
                    'label_id': po.label_id.id
                }
                calc.env['s2u.sale.line.product'].create(product_line)
            # zet de inkoop waarde vast, dit om te voorkomen dat als er binnen de PO's iets verandert
            # de waarde van de calculatie mee verandert
            po.write({
                'po_amount_fixed': po.calc_amount_base
            })

        for var in self.dynamic_cost_ids:
            if var.pos == 'once' and var.product_id:
                product = self.env['s2u.baseproduct.item'].search([('res_model', '=', 's2u.sale.product'),
                                                                   ('res_id', '=', var.product_id.id)])
                product_line = {
                    'saleline_id': sale_line.id,
                    'product_id': product.id,
                    'product_detail': var.product_detail,
                    'qty': var.qty,
                    'amount': var.calc_net_amount,
                    'label_id': var.label_id.id
                }
                self.env['s2u.sale.line.product'].create(product_line)

        for label in calc.detail_ids:
            vals = {
                'saleline_id': sale_line.id,
                'label_id': label.label_id.id,
                'value': label.value,
                'sequence': label.sequence,
                'display': label.display,
                'on_invoice': label.on_invoice
            }
            calc.env['s2u.sale.line.label'].create(vals)

        return quotation

    @api.multi
    def action_quotation(self):

        self.ensure_one()

        if not self.totals_ids:
            raise UserError(_('Please enter the totals for this project!'))

        lines = self.env['s2u.sale.line'].search([('intermediair_calc_id', '=', self.id)])
        sales_ids = [l.sale_id.id for l in lines]
        sales_ids = list(set(sales_ids))
        sales = self.env['s2u.sale'].browse(sales_ids)
        sales.unlink()

        self.calc_po_ids.write({
            'po_amount_fixed': 0.0,
            'po_amount_locked': False
        })
        self.invalidate_cache()

        quotation = self.create_quotation(self)

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_sale')
        list_view_id = imd.xmlid_to_res_id('s2usale.sale_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.sale_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
            'views': [(form_view_id, 'form')],
            'res_id': quotation.id
        }

        return result

    @api.multi
    def action_stock_reservations(self):

        reservation_model = self.env['s2u.warehouse.production.used.materials']
        line_model = self.env['s2u.warehouse.production.used.materials.line.item']

        self.ensure_one()

        if not self.stock_ids:
            raise UserError(_('You have no products selected from stock!'))

        reserved = 0
        for stock in self.stock_ids:
            if stock.reserve:
                reserved += 1

        if not reserved:
            raise UserError(_('Please mark which stock products to reserve!'))

        reservations = reservation_model.search([('intermediair_calc_id', '=', self.id)])
        for r in reservations:
            r.undo_confirm()
        reservations.unlink()

        vals = {
            'intermediair_calc_id': self.id,
            'reference': self.reference,
            'project': self.name,
        }
        reservation = reservation_model.create(vals)

        for stock in self.stock_ids:
            if not stock.reserve:
                continue
            vals = {
                'usedmaterials_id': reservation.id,
                'product_id': stock.product_id.id,
                'product_qty': stock.product_qty,
                'product_value': stock.item_price,
            }
            line = line_model.create(vals)
            stock.write({
                'reservedline_id': line.id
            })
        reservation.do_reserved()

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uwarehouse.action_warehouse_production_used_materials')
        list_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_production_used_materials_tree')
        form_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_production_used_materials_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
            'views': [(form_view_id, 'form')],
            'res_id': reservation.id
        }

        return result

    @api.multi
    def action_add_purchase(self):
        self.ensure_one()

        if not self.totals_ids:
            raise UserError(_('Please enter the totals for this project!'))

        add_form = self.env.ref('s2uintermediair.wizard_add_purchase_view', False)
        ctx = dict(
            default_model='s2u.intermediair.calc',
            default_res_id=self.id,
        )
        return {
            'name': _('Add purchase'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.intermediair.add.purchase',
            'views': [(add_form.id, 'form')],
            'view_id': add_form.id,
            'target': 'new',
            'context': ctx,
        }

    def _get_po_count(self):

        for calc in self:
            lines = self.env['s2u.purchase.line'].search([('intermediair_calc_id', '=', calc.id)])
            purchase_ids1 = [l.purchase_id.id for l in lines]

            lines = self.env['s2u.purchase.line.qty'].search([('intermediair_calc_id', '=', calc.id)])
            purchase_ids2 = [l.purchaseline_id.purchase_id.id for l in lines]

            purchase_ids = list(set(purchase_ids1 + purchase_ids2))
            calc.po_count = len(purchase_ids)

    def _get_so_count(self):

        for calc in self:
            lines = self.env['s2u.sale.line'].search([('intermediair_calc_id', '=', calc.id)])
            sales_ids = [l.sale_id.id for l in lines]
            sales_ids = list(set(sales_ids))
            calc.so_count = len(sales_ids)

    def _get_outgoing_count(self):

        for calc in self:
            outgoings = self.env['s2u.warehouse.outgoing'].search([('intermediair_calc_id', '=', calc.id)])
            outgoing_ids = outgoings.ids
            calc.outgoing_count = len(outgoing_ids)

    @api.multi
    def action_cancel(self):

        self.ensure_one()

        self.write({
            'state': 'cancel'
        })

    _calc_state = {
        'draft': [('readonly', False)],
        'order': [('readonly', False)],
        'confirm': [('readonly', False)],
        'rejected': [('readonly', False)],
    }

    name = fields.Char(string='Project', required=True, index=True, copy=True)
    reference = fields.Char(string='Our reference', index=True, copy=False,
                            readonly=True)
    customer_code = fields.Char(string='Your reference', index=True, copy=False,
                                readonly=True, states=_calc_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_calc_state)
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True,
                                 readonly=True, states=_calc_state)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                 readonly=True, states=_calc_state)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True,
                                 readonly=True, states=_calc_state)
    state = fields.Selection([
        ('draft', 'New'),
        ('order', 'Order'),
        ('confirm', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State')
    net_amount = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount,
                                 readonly=True)
    gross_amount = fields.Monetary(string='Gross amount', currency_field='currency_id', compute=_compute_amount,
                                   readonly=True)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_calc_state)
    invoice_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_calc_state)
    invoice_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', index=True,
                                         readonly=True, states=_calc_state)
    invoice_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                         readonly=True, states=_calc_state)
    invoice_address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True,
                                         readonly=True, states=_calc_state)
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_calc_state)
    delivery_partner_id = fields.Many2one('s2u.crm.entity', string='Customer', index=True,
                                          readonly=True, states=_calc_state)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                          readonly=True, states=_calc_state)
    delivery_address = fields.Text(string='Address', readonly=True, states=_calc_state)
    product_id = fields.Many2one('s2u.sale.product', string='Einproduct', required=True,
                                 readonly=True, states=_calc_state)
    details = fields.Char(string='Omschrijving',
                          readonly=True, states=_calc_state)
    modellen = fields.Char(string='Modellen', readonly=True, states=_calc_state)
    planning = fields.Char(string='Planning', readonly=True, states=_calc_state)
    overigen = fields.Text(string='Diversen', readonly=True, states=_calc_state)
    fixcosts_ids = fields.One2many('s2u.intermediair.calc.fix.costs', 'calc_id',
                                   string='Fix costs', copy=True)
    dynamic_cost_ids = fields.One2many('s2u.intermediair.calc.dynamic.costs', 'calc_id',
                                       string='Var. costs', copy=True)
    po_count = fields.Integer(string='# of Purchases', compute='_get_po_count', readonly=True)
    so_count = fields.Integer(string='# of Sales', compute='_get_so_count', readonly=True)
    po_amount = fields.Monetary(string='Nacalc.', currency_field='currency_id', compute=_compute_amount,
                                readonly=True)
    po_amount_delta = fields.Monetary(string='# Delta', currency_field='currency_id', compute=_compute_amount,
                                      readonly=True)
    po_marge = fields.Float(string='Marge in %', compute=_compute_amount, readonly=True)
    kickback = fields.Float(string='Kickback in %', default=0.0, required=True)
    kickback_id = fields.Many2one('s2u.crm.entity.kickback', string='Kickback', index=True,
                                  readonly=True, states=_calc_state)
    net_amount_kickback = fields.Monetary(string='Amount (kb)', currency_field='currency_id', compute=_compute_amount,
                                          readonly=True)
    totals_ids = fields.One2many('s2u.intermediair.calc.totals', 'calc_id',
                                 string='Editions', copy=True)
    date_calc = fields.Date(string='Date', index=True, copy=False,
                            default=lambda self: fields.Date.context_today(self),
                            readonly=True, states=_calc_state)
    qty = fields.Char(string='Oplage', compute=_compute_amount, readonly=True)
    active = fields.Boolean('Active', default=True, help='When set to not active, this project is not visible anymore.')
    outgoing_count = fields.Integer(string='# of Outgoings', compute='_get_outgoing_count', readonly=True)
    load_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_calc_state)
    load_entity_id = fields.Many2one('s2u.crm.entity', string='Loading entity', index=True,
                                     readonly=True, states=_calc_state)
    load_address = fields.Text(string='Loading address', readonly=True, states=_calc_state)
    trailer_no = fields.Char(string='Trailer-No.', index=True, readonly=True, states=_calc_state)
    date_planning = fields.Date(string='Planning', index=True, copy=False,
                                default=lambda self: fields.Date.context_today(self))
    pre_amount = fields.Monetary(string='Voorcalc.', currency_field='currency_id', compute=_compute_amount,
                                readonly=True)
    pre_amount_delta = fields.Monetary(string='# Delta', currency_field='currency_id', compute=_compute_amount,
                                      readonly=True)
    pre_marge = fields.Float(string='Marge in %', compute=_compute_amount, readonly=True)
    artwork = fields.Text(string='Artwork',
                          readonly=True, states=_calc_state)
    prices = fields.Text(string='Prijzen',
                         readonly=True, states=_calc_state)
    condition = fields.Text(string='Conditie',
                            readonly=True, states=_calc_state)
    condition_delivery = fields.Char(string='Leveringsconditie',
                                     readonly=True, states=_calc_state)
    payment = fields.Char(string='Betaling',
                          readonly=True, states=_calc_state)
    date_delivery = fields.Date(string='Date delivery', copy=False, readonly=True, states=_calc_state)
    date_artwork = fields.Date(string='Date artwork', copy=False, readonly=True, states=_calc_state)
    date_submission = fields.Date(string='Date submission', copy=False, readonly=True, states=_calc_state)
    delivery_ids = fields.One2many('s2u.intermediair.calc.delivery.address', 'calc_id',
                                   string='Deliveries', readonly=True, states=_calc_state)
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland', default=_default_delivery_country)
    delivery_tinno = fields.Char('TIN no.')
    delivery_lang = fields.Selection(_delivery_lang_get, string='Language')
    delivery_delivery_id = fields.Many2one('s2u.crm.entity.delivery', string='Delivery')
    detail_ids = fields.One2many('s2u.intermediair.calc.detail', 'calc_id',
                                 string='Details', readonly=True, states=_calc_state, copy=True)
    stock_ids = fields.One2many('s2u.intermediair.calc.stock', 'calc_id',
                                string='EV', copy=False)
    calc_po_ids = fields.One2many('s2u.intermediair.calc.purchase', 'calc_id',
                                  string='Purchases', copy=True)
    layout_id = fields.Many2one('s2u.layout', string='Layout',
                                readonly=True, states=_calc_state)
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', index=True, copy=False,
                                  ondelete='set null')
    product_detail = fields.Char(string='Details')
    invoice_is_sale_address = fields.Boolean(string='Invoice is sale address', default=True)
    delivery_is_sale_address = fields.Boolean(string='Delivery is sale address', default=True)

    @api.multi
    def action_view_po(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_purchase')
        list_view_id = imd.xmlid_to_res_id('s2usale.purchase_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.purchase_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        lines = self.env['s2u.purchase.line'].search([('intermediair_calc_id', '=', self.id)])
        purchase_ids1 = [l.purchase_id.id for l in lines]

        lines = self.env['s2u.purchase.line.qty'].search([('intermediair_calc_id', '=', self.id)])
        purchase_ids2 = [l.purchaseline_id.purchase_id.id for l in lines]

        purchase_ids = list(set(purchase_ids1 + purchase_ids2))

        if len(purchase_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % purchase_ids
        elif len(purchase_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = purchase_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    @api.multi
    def action_view_so(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_sale')
        list_view_id = imd.xmlid_to_res_id('s2usale.sale_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.sale_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        lines = self.env['s2u.sale.line'].search([('intermediair_calc_id', '=', self.id)])
        sales_ids = [l.sale_id.id for l in lines]
        sales_ids = list(set(sales_ids))

        if len(sales_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % sales_ids
        elif len(sales_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = sales_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    @api.multi
    def action_view_outgoing(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uwarehouse.action_warehouse_outgoing')
        list_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_outgoing_tree')
        form_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_outgoing_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        outgoings = self.env['s2u.warehouse.outgoing'].search([('intermediair_calc_id', '=', self.id)])
        outgoing_ids = outgoings.ids

        if len(outgoing_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % outgoing_ids
        elif len(outgoing_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = outgoing_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result


class CreateQuotation(models.TransientModel):
    _name = 's2u.intermediair.create.quotation'

    @api.model
    def default_get(self, fields):

        rec = super(CreateQuotation, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        project = self.env['s2u.intermediair.calc'].browse(active_ids[0])
        rec['project'] = project.reference

        lines = []
        sequence = 10
        active_ids.sort()
        for calc_id in active_ids:
            lines.append((0, 0, {
                'intermediair_calc_id': calc_id,
                'sequence': sequence
            }))
            sequence += 10
        rec['line_ids'] = lines

        return rec

    project = fields.Char(string='Project', required=True)
    line_ids = fields.One2many('s2u.intermediair.create.quotation.line', 'create_id', string='Projects')

    @api.multi
    def action_quotation(self):

        self.ensure_one()

        for cq in self.line_ids:
            if not cq.intermediair_calc_id.totals_ids:
                raise UserError(_('Please enter the totals for project [%s]!') % cq.intermediair_calc_id.name)
            cq.intermediair_calc_id.calc_po_ids.write({
                'po_amount_fixed': 0.0,
                'po_amount_locked': False
            })
        self.invalidate_cache()

        quotation = False
        for cq in self.line_ids:
            quotation = self.env['s2u.intermediair.calc'].create_quotation(cq.intermediair_calc_id,
                                                                           reuse_so=quotation,
                                                                           main_project=self.project)

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_sale')
        list_view_id = imd.xmlid_to_res_id('s2usale.sale_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.sale_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
            'views': [(form_view_id, 'form')],
            'res_id': quotation.id
        }

        return result


class CreateQuotationLine(models.TransientModel):
    _name = 's2u.intermediair.create.quotation.line'
    _order = 'sequence'

    create_id = fields.Many2one('s2u.intermediair.create.quotation', string='Create', ondelete='set null')
    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='set null')
    sequence = fields.Integer(string='Sequence', default=10)
