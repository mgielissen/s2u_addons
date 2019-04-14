# -*- coding: utf-8 -*-

import math
import base64

from odoo import api, fields, models, _
from odoo import tools, modules
from odoo.exceptions import UserError, ValidationError
from odoo.addons.website.models.website import slugify


class SaleProductPurchase(models.Model):
    _name = 's2u.sale.product.purchase'
    _description = 'Table where to purchase the products'

    product_id = fields.Many2one('s2u.sale.product', string='Product', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    entity_id = fields.Many2one('s2u.crm.entity', string='Supplier', required=True, ondelete='restrict')
    code_supplier = fields.Char(string='Code Supplier')
    po_account_id = fields.Many2one('s2u.account.account', string='PO Account',
                                    domain=[('type', 'in', ['expense'])],
                                    required=True, ondelete='restrict')
    po_vat_id = fields.Many2one('s2u.account.vat', string='PO Vat', domain=[('type', '=', 'buy')],
                                required=True, ondelete='restrict')
    po_price = fields.Monetary(string='PO Price', currency_field='currency_id', required=True)


class SaleProduct(models.Model):
    _name = 's2u.sale.product'
    _inherit = 's2u.baseproduct.abstract'
    _description = 'Sale product'
    _order = 'name'

    @api.multi
    def check_product_detail(self, detail, product_name=False):

        if detail:
            return detail.strip()
            #if product_name:
            #    raise UserError(_('Product detail not allowed for product [%s]' % product_name))
            #else:
            #    raise UserError(_('Product detail not allowed for this product'))
            return detail
        else:
            return ''

    @api.multi
    def get_so_account(self):

        self.ensure_one()
        if self.account_id:
            return self.account_id
        else:
            return super(SaleProduct, self).get_so_account()

    @api.multi
    def get_so_vat(self):

        self.ensure_one()
        if self.vat_id:
            return self.vat_id
        else:
            return super(SaleProduct, self).get_so_vat()

    @api.multi
    def get_po_account(self, supplier=False):

        self.ensure_one()
        if supplier:
            po = self.env['s2u.sale.product.purchase'].search([('entity_id', '=', supplier.id),
                                                               ('product_id', '=', self.id)], limit=1)
            if po and po.po_account_id:
                return po.po_account_id

        return super(SaleProduct, self).get_po_account(supplier=supplier)

    @api.multi
    def get_po_vat(self, supplier=False):

        self.ensure_one()
        if supplier:
            po = self.env['s2u.sale.product.purchase'].search([('entity_id', '=', supplier.id),
                                                               ('product_id', '=', self.id)], limit=1)
            if po and po.po_vat_id:
                return po.po_vat_id

        return super(SaleProduct, self).get_po_vat(supplier=supplier)

    @api.one
    def _compute_price_before_comma(self):

        def add_separator(number):
            s = '%d' % number
            groups = []
            while s and s[-1].isdigit():
                groups.append(s[-3:])
                s = s[:-3]
            return s + '.'.join(reversed(groups))

        if not self.price_gross:
            self.price_before_comma = '-'
        else:
            price_before = int(math.floor(self.price_gross))
            self.price_before_comma = add_separator(price_before)

    @api.one
    def _compute_price_after_comma(self):

        if not self.price_gross:
            self.price_after_comma = '--'
        else:
            price_after = int(round(self.price_gross - math.floor(self.price_gross), 2) * 100.0)
            self.price_after_comma = '%02d' % price_after

    @api.one
    def _compute_price_net_as_string(self):

        def add_separator(number):
            s = '%d' % number
            groups = []
            while s and s[-1].isdigit():
                groups.append(s[-3:])
                s = s[:-3]
            return s + '.'.join(reversed(groups))

        if not self.price:
            self.price_net_as_str = '-,--'
        else:
            if self.price_is_net:
                price = self.price
            else:
                price = self.price - self.vat_id.calc_vat_from_gross_amount(self.price)
            price_after = int(round(price - math.floor(price), 2) * 100.0)
            price_before = int(math.floor(price))
            self.price_net_as_str = '%s,%02d' % (add_separator(price_before), price_after)

    @api.one
    def _compute_price_as_float(self):

        if not self.price_gross:
            self.price_as_float = '0.00'
        else:
            price_before = int(math.floor(self.price_gross))
            price_after = int(round(self.price_gross - math.floor(self.price_gross), 2) * 100.0)
            self.price_as_float = '%d.%02d' % (price_before, price_after)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        if args and len(args) == 1:
            if args[0][0] == 'name' and args[0][1] == 'ilike':
                val = args[0][2]
                args = ['|', ('name', 'ilike', val),
                             ('description', 'ilike', val)]
        return super(SaleProduct, self).search(args, offset, limit, order, count=count)

    @api.one
    @api.depends('price', 'price_is_net', 'vat_id')
    def _compute_gross_amount(self):
        if self.price_is_net:
            self.price_netto = self.price
            self.price_gross = self.price + self.vat_id.calc_vat_from_netto_amount(self.price)
        else:
            if self.vat_id:
                self.price_netto = self.price - self.vat_id.calc_vat_from_gross_amount(self.price)
            else:
                self.price_netto = self.price
            self.price_gross = self.price

    @api.one
    def _compute_product_url(self):

        url = '/shop/product/%s-%s' % (slugify(self.name), self.id)

        self.product_url = url

    @api.one
    def _compute_variant_url(self):

        if self.variant_id:
            url = '/shop/variant/%s-%s' % (slugify(self.variant_id.name), self.variant_id.id)
            self.variant_url = url
        else:
            self.variant_url = False

    @api.one
    def compute_onstock_qty(self):

        self.qty_available = 0.0
        items = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                         ('res_id', '=', self.id)])
        if items:
            available = self.env['s2u.warehouse.available'].search([('product_id', '=', items[0].id)])
            for a in available:
                self.qty_available += a.qty_available

    @api.one
    def compute_onstock_reserved(self):

        self.qty_reserved = 0.0
        items = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                         ('res_id', '=', self.id)])
        if items:
            available = self.env['s2u.warehouse.available'].search([('product_id', '=', items[0].id)])
            for a in available:
                self.qty_reserved += a.qty_reserved

    @api.one
    def compute_onstock_virtual(self):

        self.qty_virtual = 0.0
        items = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                         ('res_id', '=', self.id)])
        if items:
            available = self.env['s2u.warehouse.available'].search([('product_id', '=', items[0].id)])
            for a in available:
                self.qty_virtual += a.qty_available

            outgoings = self.env['s2u.warehouse.outgoing'].search([('state', 'in', ['draft',  'ok'])])
            if outgoings:
                todos = self.env['s2u.warehouse.outgoing.todo'].search([('product_id', '=', items[0].id),
                                                                        ('outgoing_id', 'in', outgoings.ids)])
                for t in todos:
                    self.qty_virtual -= (t.product_qty + t.shipped_qty)

    def _get_discount_count(self):

        for product in self:
            discounts = self.env['s2u.crm.entity.discount.product'].search([('product_id', '=', product.id)])
            product.discount_count = len(discounts)

    @api.multi
    def action_view_discount(self):
        discounts = self.env['s2u.crm.entity.discount.product'].search([('product_id', '=', self.id)])

        action = self.env.ref('s2uproduct.action_sale_product_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_product_id': self.id
        }
        action['context'] = str(context)
        return action

    def _get_stock_count(self):

        for product in self:
            product.stock_count = 0
            item = self.env['s2u.baseproduct.item'].search([('res_model', '=', product._name),
                                                            ('res_id', '=', product.id)], limit=1)
            if item:
                available = self.env['s2u.warehouse.unit.product'].search([('product_id', '=', item.id)])
                product.stock_count = int(sum(a.product_qty for a in available))

    @api.multi
    def action_view_stock(self):
        available_ids = []
        for product in self:
            item = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                            ('res_id', '=', product.id)], limit=1)
            if item:
                available = self.env['s2u.warehouse.unit.product'].search([('product_id', '=', item.id),
                                                                           ('product_qty', '>', 0.0)])
                available_ids += available.ids

        available_ids = list(set(available_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_unit_product2').read()[0]
        action['domain'] = [('id', 'in', available_ids)]
        return action

    _onstock_qty = lambda self, *args, **kwargs: self.compute_onstock_qty(*args, **kwargs)
    _onstock_reserved = lambda self, *args, **kwargs: self.compute_onstock_reserved(*args, **kwargs)
    _onstock_virtual = lambda self, *args, **kwargs: self.compute_onstock_virtual(*args, **kwargs)

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    name = fields.Char(required=True, index=True, string='Name')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    vat_id = fields.Many2one('s2u.account.vat', string='Vat', required=True, domain=[('type', '=', 'sell')])
    image = fields.Binary("Image", attachment=True,
                          default=lambda self: self._get_default_image())
    image_medium = fields.Binary("Medium-sized image", attachment=True)
    image_small = fields.Binary("Small-sized image", attachment=True)
    price = fields.Monetary(string='Price', currency_field='currency_id', index=True)
    price_is_net = fields.Boolean(string='Price is netto', default=True)
    price_gross = fields.Monetary(string='Gross', currency_field='currency_id',
                                  store=True, readonly=True, compute='_compute_gross_amount')
    price_netto = fields.Monetary(string='Netto', currency_field='currency_id',
                                  readonly=True, compute='_compute_gross_amount')
    publish_webshop = fields.Boolean(string='Publish webshop', default=False, index=True)
    price_before_comma = fields.Char(string='Before comma',
                                     store=False, readonly=True, compute='_compute_price_before_comma')
    price_after_comma = fields.Char(string='After comma',
                                    store=False, readonly=True, compute='_compute_price_after_comma')
    price_as_float = fields.Char(string='As float',
                                 store=False, readonly=True, compute='_compute_price_as_float')
    price_net_as_str = fields.Char(string='Net as str',
                                   store=False, readonly=True, compute='_compute_price_net_as_string')
    description = fields.Text(string='Description', index=True)
    sub_ids = fields.Many2many('s2u.product.sub.category', 's2u_product_sub_cat_rel', 'product_id', 'sub_id',
                               string='Product categories')
    delivery_id = fields.Many2one('s2u.product.delivery', string='Delivery', index=True)
    hona = fields.Boolean(string='Hide when not available', default=False)
    no_delivery_id = fields.Many2one('s2u.product.delivery', string='No delivery', index=True)
    weight = fields.Float(string='Weight (kg)', digits=(16, 3))
    product_url = fields.Char(string='Product Url', store=False, readonly=True, compute='_compute_product_url')
    qty_available = fields.Float(string='Qty available', compute=_onstock_qty, readonly=True)
    qty_reserved = fields.Float(string='Qty reserved', compute=_onstock_reserved, readonly=True)
    qty_virtual = fields.Float(string='Qty virtual', compute=_onstock_virtual, readonly=True)
    purchase = fields.Boolean(string='Purchase', default=False)
    ubl_match = fields.Char(index=True, string='UBL match')
    entity_id = fields.Many2one('s2u.crm.entity', string='Supplier')
    po_account_id = fields.Many2one('s2u.account.account', string='PO Account',
                                    domain=[('type', '=', 'expense')])
    po_vat_id = fields.Many2one('s2u.account.vat', string='PO Vat', domain=[('type', '=', 'buy')])
    po_price = fields.Monetary(string='PO Price', currency_field='currency_id')
    product_registration = fields.Selection([('no', 'No registration'),
                                             ('outgoing', 'On outgoing only'),
                                             ('match', 'S/N must exists')], required=True, string='Needs registration',
                                            default='no')
    price_prefix = fields.Char(string='Price prefix')
    purchase_ids = fields.One2many('s2u.sale.product.purchase', 'product_id',
                                   string='Purchases', copy=True)
    discount_count = fields.Integer(string='# of Discounts', compute='_get_discount_count', readonly=True)
    stock_count = fields.Integer(string='# on Stock', compute='_get_stock_count', readonly=True)
    stock_account_id = fields.Many2one('s2u.account.account', string='Stock Account',
                                       domain=[('type', 'in', ['stock'])], ondelete='restrict')
    po_account_id = fields.Many2one('s2u.account.account', string='PO Default',
                                    domain=[('type', 'in', ['expense'])], ondelete='restrict')
    po_stock_account_id = fields.Many2one('s2u.account.account', string='PO Stock Account',
                                          domain=[('type', 'in', ['stock'])], ondelete='restrict')
    variant_id = fields.Many2one('s2u.product.variant', string='Variant', index=True)
    variant_url = fields.Char(string='Variant Url', store=False, readonly=True, compute='_compute_variant_url')
    stock_prefix = fields.Char(string='Stock prefix')

    @api.multi
    def get_product_name(self):
        """Inherited from base product"""
        return '%s' % self.name

    @api.multi
    def get_product_price(self, qty, details, ctx=False):
        """"Inherited from base product"""

        if not (isinstance(qty, int) or isinstance(qty, float)):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(qty)
        if not qty:
            return False

        if ctx and ctx.get('customer_id'):
            discount = self.env['s2u.crm.entity.discount.product'].search([('entity_id', '=', ctx['customer_id']),
                                                                           ('product_id', '=', self.id)], limit=1)
            if discount:
                if discount.discount_type == 'percent':
                    res = {
                        'price': self.price,
                        'price_per': 'item',
                        'total_amount': qty * self.price,
                        'price_is_net': self.price_is_net,
                        'discount': discount.discount
                    }
                    return res
                else:
                    res = {
                        'price': discount.discount,
                        'price_per': 'item',
                        'total_amount': qty * discount.discount,
                        'price_is_net': self.price_is_net,
                        'discount': 0.0
                    }
                    return res

        res = {
            'price': self.price,
            'price_per': 'item',
            'total_amount': qty * self.price,
            'price_is_net': self.price_is_net,
            'discount': 0.0
        }
        return res

    @api.multi
    def get_purchase_price(self, qty, details, ctx=False):
        """"Inherited from base product"""

        if not self.purchase_ids:
            return False

        if not (isinstance(qty, int) or isinstance(qty, float)):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(qty)
        if not qty:
            return False

        if not ctx:
            return False
        if not ctx.get('supplier_id'):
            return False

        purchase = self.env['s2u.sale.product.purchase'].search([('product_id', '=', self.id),
                                                                 ('entity_id', '=', ctx['supplier_id'])], limit=1)
        if not purchase:
            return False

        vals = {
            'supplier_id': purchase.entity_id.id,
            'code_supplier': purchase.code_supplier,
            'price': purchase.po_price,
            'price_per': 'item',
            'total_amount': qty * purchase.po_price
        }
        return vals

    @api.multi
    def get_so_vat(self):
        """"Inherited from base product"""
        if self.vat_id:
            return self.vat_id

        return False

    @api.multi
    def needs_registration(self):
        """"Inherited from base product"""
        if self.product_registration == 'no':
            return False
        else:
            return self.product_registration

    @api.model
    def _get_default_image(self):

        img_path = modules.get_module_resource('s2uproduct', 'static/src/img', 'product.png')
        with open(img_path, 'rb') as f:
            image = f.read()

        return tools.image_resize_image_big(base64.b64encode(image))

    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        result = super(SaleProduct, self).write(vals)
        return result

    @api.model
    def create(self, vals):
        tools.image_resize_images(vals)
        result = super(SaleProduct, self).create(vals)
        return result


class ProductCategory(models.Model):
    _name = 's2u.product.category'
    _description = 'Product category'
    _order = 'name'

    @api.onchange('name')
    def _onchange_name(self):
        if not self.name:
            return False
        if not self.title:
            self.title = self.name
        return False

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(required=True, index=True, string='Category')
    title = fields.Char(required=True, index=True, string='Title')
    sub_ids = fields.Many2many('s2u.product.sub.category', 's2u_cat_sub_cat_rel', 'cat_id', 'sub_id', string='Sub categories')


class ProductSubCategory(models.Model):
    _name = 's2u.product.sub.category'
    _description = 'Product sub category'
    _order = 'name'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(required=True, index=True, string='Sub category')
    cat_ids = fields.Many2many('s2u.product.category', 's2u_cat_sub_cat_rel', 'sub_id', 'cat_id', string='Categories')


class ProductDelivery(models.Model):
    _name = 's2u.product.delivery'
    _description = 'Product delivery'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(required=True, index=True, string='Deliver time')
    days = fields.Integer(string='In days')
    type = fields.Selection([('direct', 'Direct'),
                             ('not', 'Not deliverable'),
                             ('days', 'Within entered days')], required=True, default='days')


class Registration(models.Model):
    _name = "s2u.product.registration"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Product registration"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Registration, self)._track_subtype(init_values)

    def _get_rma_count(self):

        for reg in self:
            rmas = self.env['s2u.warehouse.rma.line'].search([('registration_id', '=', reg.id)])
            rma_ids = [r.rma_id.id for r in rmas]
            rma_ids = list(set(rma_ids))
            reg.rma_count = len(rma_ids)

    @api.multi
    def action_view_rma(self):
        rmas = self.env['s2u.warehouse.rma.line'].search([('registration_id', '=', self.id)])
        rma_ids = [r.rma_id.id for r in rmas]
        rma_ids = list(set(rma_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rma_ids) > 1:
            action['domain'] = [('id', 'in', rma_ids)]
        elif len(rma_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_rma_form').id, 'form')]
            action['res_id'] = rma_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    _not_registered_state = {
        'no': [('readonly', False)],
    }

    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True,
                                 readonly=True, states=_not_registered_state)
    product_detail = fields.Char(string='Details', readonly=True, states=_not_registered_state)
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Delivery', required=True, index=True, copy=False,
                                  readonly=True, states=_not_registered_state)
    name = fields.Char(string='Serialnumber', index=True, copy=False,
                       readonly=True, states=_not_registered_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    registration_date = fields.Date(string='Registration', index=True, copy=False,
                                    readonly=True, states=_not_registered_state)
    state = fields.Selection([('no', 'Not registered'),
                              ('yes', 'Registered')], required=True, default='no')
    registered_with_id = fields.Many2one('s2u.warehouse.incoming.line.sn', string='S/N', ondelete='restrict')
    todo_id = fields.Many2one('s2u.warehouse.outgoing.todo', string='Todo', index=True, copy=False,
                              readonly=True, states=_not_registered_state)
    active = fields.Boolean('Active', default=True)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)

    _sql_constraints = [
        ('sn_company_uniq', 'unique (registered_with_id, company_id)', 'Serialnumber already used!')
    ]

    @api.multi
    def do_register(self):

        self.ensure_one()

        vals = {
            'state': 'yes',
            'registration_date': fields.Date.context_today(self)
        }

        p = self.env[self.product_id.res_model].browse(self.product_id.res_id)
        if p.needs_registration() == 'match':
            exists = self.env['s2u.warehouse.incoming.line.sn'].search([('product_id', '=', self.product_id.id),
                                                                        ('name', '=', self.name),
                                                                        ('state', '=', 'yes')], limit=1)
            if not exists:
                raise UserError(_('The serialnumber [%s] does not exists.' % self.name))
            vals['registered_with_id'] = exists.id
        else:
            exists = self.env['s2u.product.registration'].search([('product_id', '=', self.product_id.id),
                                                                  ('name', '=', self.name),
                                                                  ('state', '=', 'yes'),
                                                                  ('id', '!=', self.id)], limit=1)
            if exists:
                raise UserError(_('The serialnumber [%s] is already used.' % self.name))

        self.write(vals)

    @api.multi
    def do_unregister(self):
        self.write({
            'state': 'no',
            'registration_date': False,
            'registered_with_id': False
        })

    @api.multi
    def do_rma(self):

        self.ensure_one()

        if not self.todo_id:
            return False

        lines = []

        todo = self.todo_id

        if todo.shipped_saldo_qty < 0.0:

            match = self.env['s2u.warehouse.rma.line'].search([('product_id', '=', todo.product_id.id),
                                                               ('product_detail', '=', todo.product_detail),
                                                               ('registration_id', '=', self.id)])
            if not match:
                lines.append((0, _, {
                    'product_id': todo.product_id.id,
                    'product_detail': todo.product_detail,
                    'product_value': todo.product_value,
                    'qty': '1 stuks',
                    'product_qty': 1.0,
                    'todo_id': todo.id,
                    'serial_number': self.name,
                    'registration_id': self.id
                }))

        if not lines:
            return False

        rma_vals = {
            'entity_id': todo.outgoing_id.entity_id.id,
            'reference': todo.outgoing_id.name,
            'line_ids': lines
        }
        return self.env['s2u.warehouse.rma'].create(rma_vals)


class RegistrationMultiple(models.TransientModel):
    _name = "s2u.product.registration.multiple"
    _description = "Multiple product registration"

    @api.model
    def default_get(self, fields):
        rec = super(RegistrationMultiple, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        rec['products'] = ','.join([str(id) for id in active_ids])

        return rec

    serial_numbers = fields.Text(string='Serialnumbers', required=True)
    products = fields.Char(string='Products')

    @api.multi
    def action_registration(self):

        self.ensure_one()
        product_ids = [int(s) for s in self.products.split(',')]
        lines = []
        for sn in self.serial_numbers.split('\n'):
            if not sn.strip():
                continue
            lines.append(sn)
        if len(lines) != len(product_ids):
            raise UserError(_('You have %d products selected and entered %d serial-numbers.' % (len(product_ids), len(lines))))
        idx = 0
        for product in self.env['s2u.product.registration'].browse(product_ids):
            if product.state != 'no':
                raise UserError(_('You have selected products which are already registered!'))
            product.write({
                'name': lines[idx]
            })
            product.do_register()
            idx += 1


class ProductVariant(models.Model):
    _name = 's2u.product.variant'
    _description = 'Product variant'
    _order = 'name'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(required=True, index=True, string='Variant')

    _sql_constraints = [
        ('name_company_uniq', 'unique (name, company_id)', 'The variant must be unique !')
    ]
