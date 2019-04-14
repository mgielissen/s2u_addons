# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseUnit(models.Model):
    _name = "s2u.warehouse.unit"
    _order = "name"

    @api.one
    @api.constrains('assigned_qty')
    def _check_assigned_qty(self):
        if self.assigned_qty < 0:
            raise ValidationError(_('Assigned can not have negative value!'))
        if self.assigned_qty > 1:
            raise ValidationError(_('Unit is already assigned!'))

    @api.model
    def _new_unit_id(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.warehouse.unit')])
        if not exists:
            raise UserError(_('Sequence for creating s2u.warehouse.unit not exists!'))

        sequence = exists[0]
        new_number = sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()
        return new_number

    def _on_unit(self, unit, on_unit):
        if not unit:
            return on_unit

        products_grouped = {}
        products_names = {}
        for product in unit.line_ids:
            if product.sn_registration:
                key = '%s,%s,%s' % (product.product_id.id, product.product_detail, product.serialnumber)
            else:
                key = '%s,%s' % (product.product_id.id, product.product_detail)
            if key not in products_grouped:
                products_grouped[key] = product.product_qty
                products_names[key] = product.prepare_unitproduct_name()
            else:
                products_grouped[key] += product.product_qty
        for k, v in iter(products_grouped.items()):
            name = '%s: %0.2f' % (products_names[k], v)
            if on_unit:
                on_unit = '%s\n%s' % (on_unit, name)
            else:
                on_unit = '%s' % name

        return on_unit

    @api.one
    def _compute_on_unit(self):
        on_pallet = False

        childs = self.search([('parent_id', '=', self.id)])
        boxes_on_pallet = {}
        for unit in childs:
            box_on_pallet = self._on_unit(unit, False)
            if box_on_pallet not in boxes_on_pallet:
                boxes_on_pallet[box_on_pallet] = 1
            else:
                boxes_on_pallet[box_on_pallet] += 1

        for box, qty in iter(boxes_on_pallet.items()):
            if on_pallet:
                on_pallet = '%d x doos met %s\n%s' % (qty, box, on_pallet)
            else:
                on_pallet = '%d x doos met %s' % (qty, box)
        on_pallet = self._on_unit(self, on_pallet)

        self.on_unit = on_pallet

    @api.one
    def _compute_assigned(self):

        if self.assigned_qty > 0:
            self.assigned = True
        else:
            self.assigned = False

    @api.one
    def empty_unit(self, write=False):

        product_model = self.env['s2u.warehouse.unit.product']
        units_to_mark = self.env['s2u.warehouse.unit']

        products_on_unit = product_model.search([('unit_id', '=', self.id),
                                                 ('product_qty', '>', 0.0)])
        if products_on_unit:
            if write:
                units_to_mark += self
                if self.parent_id:
                    units_to_mark += self.parent_id
                units_to_mark.write({'active': True})
            return False

        childs = self.search([('parent_id', '=', self.id)])
        if not childs:
            if write:
                units_to_mark += self
                # nu controleren of deze unit op een ander unit staat,
                # is dit het geval, de parent unit controleren of deze leeg is en zo ja ook deactiveren
                if self.parent_id:
                    products_on_unit = product_model.search([('unit_id', '=', self.parent_id.id),
                                                             ('product_qty', '>', 0.0)])
                    if not products_on_unit:
                        childs = self.search([('parent_id', '=', self.parent_id.id),
                                              ('id', '!=', self.id)])
                        products_on_unit = product_model.search([('unit_id', 'in', childs.ids),
                                                                 ('product_qty', '>', 0.0)])
                        if not products_on_unit:
                            units_to_mark += self.parent_id
                units_to_mark.write({'active': False})
            return True

        products_on_unit = product_model.search([('unit_id', 'in', childs.ids),
                                                 ('product_qty', '>', 0.0)])
        if products_on_unit:
            if write:
                units_to_mark += self
                if self.parent_id:
                    units_to_mark += self.parent_id
                units_to_mark.write({'active': True})
            return False

        if write:
            units_to_mark += self
            # nu controleren of deze unit op een ander unit staat,
            # is dit het geval, de parent unit controleren of deze leeg is en zo ja ook deactiveren
            if self.parent_id:
                products_on_unit = product_model.search([('unit_id', '=', self.parent_id.id),
                                                         ('product_qty', '>', 0.0)])
                if not products_on_unit:
                    childs = self.search([('parent_id', '=', self.parent_id.id),
                                          ('id', '!=', self.id)])
                    products_on_unit = product_model.search([('unit_id', 'in', childs.ids),
                                                             ('product_qty', '>', 0.0)])
                    if not products_on_unit:
                        units_to_mark += self.parent_id
            units_to_mark.write({'active': False})
        return True

    @api.one
    def assign_unit(self):

        for item in self.line_ids:
            item.write({
                'assigned_qty': item.assigned_qty + item.product_qty
            })
        childs = self.search([('parent_id', '=', self.id)])
        for child in childs:
            for item in child.line_ids:
                item.write({
                    'assigned_qty': item.assigned_qty + item.product_qty
                })

        self.write({
            'assigned_qty': self.assigned_qty + 1
        })
        return True

    @api.one
    def unassign_unit(self):

        for item in self.line_ids:
            if item.assigned_qty - item.product_qty >= 0.0:
                item.write({
                    'assigned_qty': item.assigned_qty - item.product_qty
                })
        childs = self.search([('parent_id', '=', self.id)])
        for child in childs:
            for item in child.line_ids:
                if item.assigned_qty - item.product_qty >= 0.0:
                    item.write({
                        'assigned_qty': item.assigned_qty - item.product_qty
                    })

        if self.assigned_qty > 0:
            self.write({
                'assigned_qty': self.assigned_qty - 1
            })
        return True

    @api.one
    @api.constrains('parent_id', 'type')
    def _check_unit(self):
        if self.parent_id:
            if self.type != 'box':
                raise ValidationError(_('Units placed on another unit can only be of type \'Box\'!'))
            if self.parent_id.parent_id:
                raise ValidationError(_('You can not put units on a unit which is also placed on another unit!'))
        else:
            childs = self.search([('parent_id', '=', self.id)])
            if childs:
                if self.type not in ['singleton', 'pallet']:
                    raise ValidationError(_('This unit contains other units on it, type \'Box \' not allowed!'))
                if self.parent_id:
                    raise ValidationError(_('This unit contains other units on it, you can not put this unit on another unit!'))

    def _get_outgoing_count(self):

        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']

        for unit in self:
            outgoing_ids = []
            assigned_units = assigned_unit_model.search([('unit_id', '=', unit.id)])
            for au in assigned_units:
                outgoing_ids.append(au.outgoing_id.id)

            outgoing_ids = list(set(outgoing_ids))
            unit.outgoing_count = len(outgoing_ids)

    def _get_incoming_count(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        for unit in self:
            incoming_ids = []
            transactions = trans_model.search([('incoming_id', '!=', False),
                                               ('unit_id', '=', unit.id)])
            for t in transactions:
                incoming_ids.append(t.incoming_id.id)

            incoming_ids = list(set(incoming_ids))
            unit.incoming_count = len(incoming_ids)

    @api.multi
    def action_view_outgoing(self):
        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']

        outgoing_ids = []

        assigned_units = assigned_unit_model.search([('unit_id', '=', self.id)])
        for au in assigned_units:
            outgoing_ids.append(au.outgoing_id.id)

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
    def action_view_incoming(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        incoming_ids = []
        transactions = trans_model.search([('incoming_id', '!=', False),
                                           ('unit_id', '=', self.id)])
        for t in transactions:
            incoming_ids.append(t.incoming_id.id)

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

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(string='Unit ID', index=True, required=True, copy=False,
                       default=_new_unit_id)
    type = fields.Selection([
        ('singleton', 'Eenheid'),
        ('pallet', 'Pallet'),
        ('box', 'Doos')
    ], required=True, default='singleton', string='Type')
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Pallet', index=True)
    pallet_factor = fields.Integer(string='Factor', default=1)
    line_ids = fields.One2many('s2u.warehouse.unit.product', 'unit_id',
                               string='Lines', copy=False)
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', required=True, index=True,
                                  ondelete='restrict')
    incoming_id = fields.Many2one('s2u.warehouse.incoming', string='Incoming', index=True, ondelete='restrict',
                                  copy=False)
    active = fields.Boolean(default=True)
    on_unit = fields.Text(string='In/on unit', compute=_compute_on_unit, readonly=True)
    parent_id = fields.Many2one('s2u.warehouse.unit', string='Parent unit')
    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced', index=True, ondelete='restrict',
                                  copy=False)
    unit_date = fields.Date(string='Date', index=True, copy=False, required=True,
                            default=lambda self: fields.Date.context_today(self))
    assigned = fields.Boolean('Assigned', compute=_compute_assigned, readonly=True)
    assigned_qty = fields.Integer(string='Assigned', default=0)
    outgoing_count = fields.Integer(string='# of Outgoings', compute='_get_outgoing_count', readonly=True)
    incoming_count = fields.Integer(string='# of Incomings', compute='_get_incoming_count', readonly=True)


class WarehouseUnitProduct(models.Model):
    _name = "s2u.warehouse.unit.product"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _order = "product_id, product_detail, sn_registration, serialnumber, product_qty"

    @api.multi
    def prepare_unitproduct_name(self):

        self.ensure_one()

        if self.product_detail:
            name = '%s - %s' % (self.product_id.name, self.product_detail)
        else:
            name = self.product_id.name
        if self.sn_registration:
            name = '%s %s' % (name, self.serialnumber if self.serialnumber else '')
        return name

    @api.multi
    def name_get(self):
        result = []
        for product in self:
            result.append((product.id, product.prepare_unitproduct_name()))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', '|', ('product_id.name', '=ilike', '%' + name + '%'),
                                     ('product_detail', operator, name),
                                     ('serialnumber', '=ilike', '%' + name + '%'),
                                     ('unit_id.name', '=ilike', '%' + name + '%')]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        products = self.search(domain + args, limit=limit)
        return products.name_get()

    @api.one
    @api.constrains('product_qty')
    def _check_product_qty(self):
        if self.product_qty < 0.0:
            raise ValidationError(_('Item qty in warehouse can not be negative!'))

    @api.one
    @api.constrains('assigned_qty')
    def _check_assigned_qty(self):
        if self.assigned_qty < 0.0:
            raise ValidationError(_('Assigned qty in warehouse can not be negative!'))
        if self.unit_id.active and (self.assigned_qty > self.product_qty):
            raise ValidationError(_('Assigned qty can not be more as item qty present in warehouse!'))

    def _get_outgoing_count(self):

        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        for unit_product in self:
            outgoing_ids = []
            assigned_products = assigned_product_model.search([('unitproduct_id', '=', unit_product.id)])
            for ap in assigned_products:
                outgoing_ids.append(ap.outgoing_id.id)
            assigned_units = assigned_unit_model.search([('unit_id', '=', unit_product.unit_id.id)])
            for au in assigned_units:
                outgoing_ids.append(au.outgoing_id.id)

            outgoing_ids = list(set(outgoing_ids))
            unit_product.outgoing_count = len(outgoing_ids)

    def _get_incoming_count(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        for unit_product in self:
            incoming_ids = []
            if unit_product.sn_registration:
                transactions = trans_model.search([('incoming_id', '!=', False),
                                                   ('rel_serialnumber', '=', unit_product.serialnumber),
                                                   ('rel_product_id', '=', unit_product.product_id.id)])
                for t in transactions:
                    incoming_ids.append(t.incoming_id.id)
            else:
                transactions = trans_model.search([('incoming_id', '!=', False),
                                                   ('rel_product_id', '=', unit_product.product_id.id)])
                for t in transactions:
                    incoming_ids.append(t.incoming_id.id)

            incoming_ids = list(set(incoming_ids))
            unit_product.incoming_count = len(incoming_ids)

    @api.multi
    def action_view_outgoing(self):
        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        outgoing_ids = []

        assigned_products = assigned_product_model.search([('unitproduct_id', '=', self.id)])
        for ap in assigned_products:
            outgoing_ids.append(ap.outgoing_id.id)
        assigned_units = assigned_unit_model.search([('unit_id', '=', self.unit_id.id)])
        for au in assigned_units:
            outgoing_ids.append(au.outgoing_id.id)

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
    def action_view_incoming(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        incoming_ids = []
        if self.sn_registration:
            transactions = trans_model.search([('incoming_id', '!=', False),
                                               ('rel_serialnumber', '=', self.serialnumber),
                                               ('rel_product_id', '=', self.product_id.id)])
            for t in transactions:
                incoming_ids.append(t.incoming_id.id)
        else:
            transactions = trans_model.search([('incoming_id', '!=', False),
                                               ('rel_product_id', '=', self.product_id.id)])
            for t in transactions:
                incoming_ids.append(t.incoming_id.id)

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

    def _get_total_value(self):

        for unit_product in self:
            unit_product.total_value = unit_product.product_value * unit_product.product_qty

    @api.multi
    def get_supplier(self):
        """This method tries to find the supplier for this product(s) based on the transactions"""
        self.ensure_one()
        transaction = self.env['s2u.warehouse.unit.product.transaction'].search([('product_id', '=', self.id),
                                                                                 ('source_model', '=', 's2u.warehouse.incoming')], order='id', limit=1)
        if transaction:
            return transaction.entity_id
        else:
            return False

    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True, ondelete='cascade')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', related='unit_id.location_id')
    transactions = fields.One2many('s2u.warehouse.unit.product.transaction', 'product_id',
                                   string='Transactions', copy=False)
    available_id = fields.Many2one('s2u.warehouse.available', string='Available', ondelete='restrict')
    assigned_qty = fields.Float(string='Assigned', default=0.0)
    company_id = fields.Many2one('res.company', string='Company', related='unit_id.company_id')
    outgoing_count = fields.Integer(string='# of Outgoings', compute='_get_outgoing_count', readonly=True)
    incoming_count = fields.Integer(string='# of Incomings', compute='_get_incoming_count', readonly=True)
    serialnumber = fields.Char(string='Serialnumber', index=True)
    sn_registration = fields.Boolean(string='S/N registration', default=False)
    total_value = fields.Float(string='Tolal/value', digits=(16, 4), compute='_get_total_value', readonly=True)

    @api.multi
    def unlink(self):

        raise ValidationError(_('You can not delete a stock product!'))

    @api.model
    def create(self, vals):

        available_model = self.env['s2u.warehouse.available']

        product_id = vals['product_id']
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
        product = super(WarehouseUnitProduct, self).create(vals)

        return product

    @api.multi
    def write(self, vals):

        available_model = self.env['s2u.warehouse.available']

        if 'product_id' in vals:
            product_id = vals['product_id']
        else:
            product_id = self.product_id.id

        if 'product_detail' in vals:
            product_detail = vals['product_detail']
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

        return super(WarehouseUnitProduct, self).write(vals)

    @api.one
    def assign_item(self, assigned_qty):

        self.write({
            'assigned_qty': self.assigned_qty + assigned_qty
        })

        return True

    @api.one
    def unassign_item(self, assigned_qty):

        if self.assigned_qty - assigned_qty >= 0.0:
            self.write({
                'assigned_qty': self.assigned_qty - assigned_qty
            })

        return True


class WarehouseUnitProductTransaction(models.Model):
    _name = "s2u.warehouse.unit.product.transaction"
    _order = "transaction_date desc, id desc"

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.multi
    def financial_stock_on_outgoing(self, unitproduct, qty, saleline=False):
        return True

    @api.multi
    def financial_stock_on_rma(self, unitproduct, qty, product_usable, rmaline):
        return True

    def _get_outgoing_count(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        for trans in self:
            outgoing_ids = []
            if trans.rel_serialnumber:
                transactions = trans_model.search([('outgoing_id', '!=', False),
                                                   ('rel_serialnumber', '=', trans.rel_serialnumber),
                                                   ('rel_product_id', '=', trans.rel_product_id.id)])
                for t in transactions:
                    outgoing_ids.append(t.incoming_id.id)
            else:
                transactions = trans_model.search([('outgoing_id', '!=', False),
                                                   ('rel_product_id', '=', trans.rel_product_id.id)])
                for t in transactions:
                    outgoing_ids.append(t.incoming_id.id)

            outgoing_ids = list(set(outgoing_ids))
            trans.outgoing_count = len(outgoing_ids)

    def _get_incoming_count(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        for trans in self:
            incoming_ids = []
            if trans.rel_serialnumber:
                transactions = trans_model.search([('incoming_id', '!=', False),
                                                   ('rel_serialnumber', '=', trans.rel_serialnumber),
                                                   ('rel_product_id', '=', trans.rel_product_id.id)])
                for t in transactions:
                    incoming_ids.append(t.incoming_id.id)
            else:
                transactions = trans_model.search([('incoming_id', '!=', False),
                                                   ('rel_product_id', '=', trans.rel_product_id.id)])
                for t in transactions:
                    incoming_ids.append(t.incoming_id.id)

            incoming_ids = list(set(incoming_ids))
            trans.incoming_count = len(incoming_ids)

    def _get_name(self):

        for trans in self:
            try:
                source = self.env[trans.source_model].browse(trans.source_id)
                trans.name = source.name
            except:
                trans.name = 'Unknown'

    @api.multi
    def action_view_outgoing(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        outgoing_ids = []
        if self.rel_serialnumber:
            transactions = trans_model.search([('outgoing_id', '!=', False),
                                               ('rel_serialnumber', '=', self.rel_serialnumber),
                                               ('rel_product_id', '=', self.rel_product_id.id)])
            for t in transactions:
                outgoing_ids.append(t.incoming_id.id)
        else:
            transactions = trans_model.search([('outgoing_id', '!=', False),
                                               ('rel_product_id', '=', self.rel_product_id.id)])
            for t in transactions:
                outgoing_ids.append(t.incoming_id.id)

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
    def action_view_incoming(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        incoming_ids = []
        if self.rel_serialnumber:
            transactions = trans_model.search([('incoming_id', '!=', False),
                                               ('rel_serialnumber', '=', self.rel_serialnumber),
                                               ('rel_product_id', '=', self.rel_product_id.id)])
            for t in transactions:
                incoming_ids.append(t.incoming_id.id)
        else:
            transactions = trans_model.search([('incoming_id', '!=', False),
                                               ('rel_product_id', '=', self.rel_product_id.id)])
            for t in transactions:
                incoming_ids.append(t.incoming_id.id)

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

    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Unit/Product', required=True, index=True, ondelete='cascade')
    parent_id = fields.Many2one('s2u.warehouse.unit', string='Parent', index=True, ondelete='cascade')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', index=True, ondelete='cascade')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', index=True, ondelete='restrict')
    rel_product_id = fields.Many2one('s2u.baseproduct.item', string='Product', related='product_id.product_id', index=True)
    rel_product_detail = fields.Char(string='Details', related='product_id.product_detail', index=True)
    rel_serialnumber = fields.Char(string='Serialnumber', related='product_id.serialnumber', index=True)
    qty = fields.Float(string='Qty', required=True)
    transaction_date = fields.Date(string='Date', index=True, copy=False, required=True,
                                   default=lambda self: fields.Date.context_today(self))
    item_picking = fields.Boolean('Item picking', default=False)
    count_unit = fields.Boolean('Count unit', default=True)
    source_model = fields.Char(string='Source model', required=True, index=True, copy=False)
    source_id = fields.Integer(string='Source rec id', required=True, index=True, copy=False)
    incoming_id = fields.Many2one('s2u.warehouse.incoming', string='Incoming', index=True, ondelete='cascade')
    rma_id = fields.Many2one('s2u.warehouse.rma', string='RMA', index=True, ondelete='cascade')
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Outgoing', index=True, ondelete='cascade')
    scrapped_id = fields.Many2one('s2u.warehouse.move.scrapped', string='Scrapped', index=True, ondelete='cascade')
    correction_id = fields.Many2one('s2u.warehouse.move.correction', string='Correction', index=True, ondelete='cascade')
    moveunit_id = fields.Many2one('s2u.warehouse.move.unit', string='Movement', index=True, ondelete='cascade')
    moveproduct_id = fields.Many2one('s2u.warehouse.move.product', string='Movement', index=True, ondelete='cascade')
    produnit_id = fields.Many2one('s2u.warehouse.production.unit', string='Production', index=True, ondelete='cascade')
    prodproduct_id = fields.Many2one('s2u.warehouse.production.product', string='Production', index=True, ondelete='cascade')
    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced', index=True,
                                  ondelete='cascade')
    usedmaterials_id = fields.Many2one('s2u.warehouse.production.used.materials', string='Used materials', index=True,
                                       ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    supplier_no = fields.Char('Supplier No.')
    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', index=True)
    incoming_line_id = fields.Many2one('s2u.warehouse.incoming.line', string='Incoming line', index=True, ondelete='cascade')
    rma_line_id = fields.Many2one('s2u.warehouse.rma.line', string='RMA line', index=True,
                                  ondelete='cascade')
    outgoing_line_id = fields.Many2one('s2u.warehouse.outgoing.todo', string='Outgoing line', index=True, ondelete='cascade')
    produced_line_id = fields.Many2one('s2u.warehouse.produced.line', string='Produced line', index=True, ondelete='cascade')
    rma_notusable_id = fields.Many2one('s2u.warehouse.rma.notusable', string='RMA not usable', index=True,
                                       ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    account_po_id = fields.Many2one('s2u.account.account', string='Account PO', domain=[('type', '=', 'expense')],
                                    index=True)
    account_stock_id = fields.Many2one('s2u.account.account', string='Account Stock', domain=[('type', '=', 'stock')],
                                       index=True)
    amount_po_stock = fields.Monetary(string='Amount PO/Stock')
    outgoing_count = fields.Integer(string='# of Outgoings', compute='_get_outgoing_count', readonly=True)
    incoming_count = fields.Integer(string='# of Incomings', compute='_get_incoming_count', readonly=True)
    name = fields.Char(string='Name', compute='_get_name', readonly=True)


class WarehouseUnitProductNewLocation(models.TransientModel):
    _name = 's2u.warehouse.unit.product.new.location'

    @api.model
    def default_get(self, fields):

        rec = super(WarehouseUnitProductNewLocation, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        product_id = context.get('active_id', False)

        # Checks on context parameters
        if not active_model or not product_id:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_id in context."))
        if active_model != 's2u.warehouse.unit.product':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.warehouse.unit.product'. The provided one is '%d'.") % active_model)

        rec.update({
            'product_id': product_id
        })
        return rec

    @api.multi
    def do_move(self):

        move_model = self.env['s2u.warehouse.move.product']
        unit_model = self.env['s2u.warehouse.unit']

        unit = unit_model.create({
            'type': 'singleton',
            'location_id': self.location_id.id
        })

        move = {
            'from_unit_id': self.product_id.unit_id.id,
            'unit_id': unit.id,
            'product_id': self.product_id.id,
            'product_qty': self.qty_move
        }

        move = move_model.create(move)
        move.do_confirm()

    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Item/product', required=True)
    qty_move = fields.Float(string='Qty move', required=True)
    location_id = fields.Many2one('s2u.warehouse.location', string='New location', required=True)


class WarehouseUnitProductToProduction(models.TransientModel):
    _name = 's2u.warehouse.unit.product.to.production'

    @api.model
    def default_get(self, fields):

        rec = super(WarehouseUnitProductToProduction, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        product_id = context.get('active_id', False)

        # Checks on context parameters
        if not active_model or not product_id:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_id in context."))
        if active_model != 's2u.warehouse.unit.product':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.warehouse.unit.product'. The provided one is '%d'.") % active_model)

        rec.update({
            'product_id': product_id
        })
        return rec

    @api.multi
    def do_production(self):

        production_model = self.env['s2u.warehouse.production.product']

        production = {
            'unit_id': self.product_id.unit_id.id,
            'product_id': self.product_id.id,
            'product_qty': self.qty_production
        }

        production = production_model.create(production)
        production.do_confirm()

    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Item/product', required=True)
    qty_production = fields.Float(string='Qty production', required=True)
