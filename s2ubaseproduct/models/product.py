# -*- coding: utf-8 -*-

import re

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class BaseProductAbstract(models.AbstractModel):
    _name = "s2u.baseproduct.abstract"
    _description = "Contains the logic of models containing product information which can be sold, purchased or saved in warehouse"

    @api.multi
    def _get_product_types(self):

        return [('stock', 'Stockable'), ('service', 'Service'), ('drop', 'Dropshipping')]

    # indirection to ease inheritance
    _product_type_selection = lambda self, *args, **kwargs: self._get_product_types(*args, **kwargs)

    name = fields.Char(string='Product', required=True, index=True)
    product_type = fields.Selection(_product_type_selection, required=True, default='stock', string='Type')
    sn_registration = fields.Boolean(string='S/N registration', default=False)

    @api.multi
    def check_product_detail(self, detail, product_name=False):

        if not detail:
            detail = ''
        return detail

    @api.multi
    def get_so_account(self):

        self.ensure_one()

        try:
            accounts = self.env['s2u.account.account'].search([('type', '=', 'income')])
            if accounts:
                return accounts[0]
        except:
            pass

        return False

    @api.multi
    def get_po_account(self, supplier=False):

        self.ensure_one()

        try:
            accounts = self.env['s2u.account.account'].search([('type', '=', 'expense')])
            if accounts:
                return accounts[0]
        except:
            pass

        return False

    @api.multi
    def get_so_vat(self):

        try:
            account = self.get_so_account()
            if account and account.vat_id:
                return account.vat_id
        except:
            pass

        return False

    @api.multi
    def get_po_vat(self, supplier=False):

        try:
            account = self.get_po_account()
            if account and account.vat_id:
                return account.vat_id
        except:
            pass

        return False

    @api.multi
    def get_product_price(self, qty, details, ctx=False):

        return False

    @api.multi
    def get_purchase_price(self, qty, details, ctx=False):

        return False

    @api.multi
    def needs_registration(self):

        self.ensure_one()

        return False

    @api.model
    def create(self, vals):

        product = super(BaseProductAbstract, self).create(vals)

        if hasattr(product, 'get_product_name'):
            name = product.get_product_name()
        else:
            name = product.name

        if hasattr(product, 'get_product_uom'):
            uom1, uomx = product.get_product_uom()
        else:
            uom1 = 'stuk'
            uomx = 'stuks'

        self.env['s2u.baseproduct.item'].create({
            'res_model': self._name,
            'res_id': product.id,
            'name': name,
            'product_uom1': uom1,
            'product_uomx': uomx,
            'product_type': product.product_type,
            'sn_registration': product.sn_registration
        })

        return product

    @api.multi
    def write(self, vals):

        res = super(BaseProductAbstract, self).write(vals)
        for product in self:

            if hasattr(product, 'get_product_name'):
                name = product.get_product_name()
            else:
                name = product.name

            if hasattr(product, 'get_product_uom'):
                uom1, uomx = product.get_product_uom()
            else:
                uom1 = 'stuk'
                uomx = 'stuks'

            product_type = vals.get('product_type', product.product_type)

            items = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                             ('res_id', '=', product.id)])
            if items:
                items.write({
                    'name': name,
                    'product_uom1': uom1,
                    'product_uomx': uomx,
                    'product_type': product_type,
                    'sn_registration': product.sn_registration
                })
            else:
                self.env['s2u.baseproduct.item'].create({
                    'res_model': self._name,
                    'res_id': product.id,
                    'name': name,
                    'product_uom1': uom1,
                    'product_uomx': uomx,
                    'product_type': product_type,
                    'sn_registration': product.sn_registration
                })

        return res

    @api.multi
    def unlink(self):

        for product in self:
            items = self.env['s2u.baseproduct.item'].search([('res_model', '=', self._name),
                                                             ('res_id', '=', product.id)])
            items.unlink()

        res = super(BaseProductAbstract, self).unlink()

        return res

    def parse_qty(self, qty):

        def time_to_float(int_part, fract_part):
            if not int_part:
                int_part = '0'

            if fract_part:
                fract_part = int(fract_part)
                if fract_part >= 60:
                    raise UserError(_('Time is given as quantity, but has an invalid value for the minutes!'))
                return float(int_part) + float(fract_part) / 60.0
            else:
                return float(int_part)

        if not qty:
            return False
        qty_integer = ''
        qty_fract = ''
        qty_type = 'integer'
        qty_part = 'integer'
        ignore_prefix = True
        for s in qty:
            if ignore_prefix and s.isalpha() or s in [' ', '-', '+', '/', '\\']:
                continue
            if s == ',':
                qty_type = 'float'
                qty_part = 'fract'
                ignore_prefix = False
                continue
            if s == ':':
                qty_type = 'time'
                qty_part = 'fract'
                ignore_prefix = False
                continue
            if s in ['.']:
                ignore_prefix = False
                continue
            if '0' <= s <= '9':
                if qty_part == 'integer':
                    qty_integer += s
                else:
                    qty_fract += s
                ignore_prefix = False
                continue
            break
        if qty_integer:
            if qty_type == 'integer':
                qty = int(qty_integer)
            if qty_type == 'float':
                qty_str = '%s.%s' % (qty_integer, qty_fract)
                qty = float(qty_str)
            if qty_type == 'time':
                qty = time_to_float(qty_integer, qty_fract)
        else:
            qty = 1

        return qty

    @api.multi
    def is_stockable(self):

        self.ensure_one()
        if self.product_type == 'stock':
            return True
        return False

    @api.multi
    def is_service(self):

        self.ensure_one()
        if self.product_type == 'service':
            return True
        return False

    @api.multi
    def is_dropshipping(self):

        self.ensure_one()
        if self.product_type == 'drop':
            return True
        return False


class BaseProductTransactionAbstract(models.AbstractModel):
    _name = "s2u.baseproduct.transaction.abstract"
    _description = "Contains the logic shared between models which allows to book product related transactions"

    @api.onchange('product_detail')
    def onchange_product_detail(self):

        if not self.product_id:
            return

        detail = self.env[self.product_id.res_model].check_product_detail(self.product_detail)
        self.product_detail = detail

    @api.model
    def create(self, vals):

        product = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
        vals['product_detail'] = self.env[product.res_model].check_product_detail(vals.get('product_detail', ''),
                                                                                  product_name=product.name)

        trans = super(BaseProductTransactionAbstract, self).create(vals)

        return trans

    @api.multi
    def write(self, vals):

        for product in self:
            if vals.get('product_id', False):
                baseproduct = self.env['s2u.baseproduct.item'].browse(vals['product_id'])
                res_model = baseproduct.res_model
                product_name = baseproduct.name
            else:
                res_model = product.product_id.res_model
                product_name = product.product_id.name
            if 'product_detail' in vals:
                product_detail = vals['product_detail']
                vals['product_detail'] = self.env[res_model].check_product_detail(product_detail, product_name=product_name)

        res = super(BaseProductTransactionAbstract, self).write(vals)
        return res

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True)
    product_qty = fields.Float(string='Qty', required=True)
    product_detail = fields.Char(string='Details')
    product_value = fields.Float(string='Price/value', digits=(16, 4))


class BaseProductItem(models.Model):
    _name = "s2u.baseproduct.item"
    _order = "name"

    @api.multi
    def _get_product_types(self):
        return [('stock', 'Stockable'), ('service', 'Service'), ('drop', 'Dropshipping')]

    @api.multi
    def fetch_object(self):
        self.ensure_one()
        return self.env[self.res_model].sudo().search([('id', '=', self.res_id)], limit=1)

    # indirection to ease inheritance
    _product_type_selection = lambda self, *args, **kwargs: self._get_product_types(*args, **kwargs)

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(string='Product', required=True, index=True)
    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Id.', required=True, index=True)
    product_uom1 = fields.Char(string='uom')
    product_uomx = fields.Char(string='uom')
    product_type = fields.Selection(_product_type_selection, required=True, default='stock', string='Type')
    sn_registration = fields.Boolean(string='S/N registration', default=False)

    @api.multi
    def is_stockable(self):

        self.ensure_one()
        if self.product_type == 'stock':
            return True
        return False

    @api.multi
    def is_service(self):

        self.ensure_one()
        if self.product_type == 'service':
            return True
        return False

    @api.multi
    def is_dropshipping(self):

        self.ensure_one()
        if self.product_type == 'drop':
            return True
        return False

    @api.multi
    def needs_registration(self):
        self.ensure_one()
        product = self.env[self.res_model].sudo().search([('id', '=', self.res_id)], limit=1)
        if product:
            return product.needs_registration()
        else:
            return False


