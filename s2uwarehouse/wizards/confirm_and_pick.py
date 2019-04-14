# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import _, api, fields, models


class ConfirmAndPick(models.TransientModel):
    """
    """
    _name = 's2u.warehouse.confirm.pick'
    _description = 'Confirm and Pick wizard'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Outgoing', ondelete='cascade')
    picking_method = fields.Selection([
        ('exact', 'Exact quantity'),
        ('sn', 'By serialnumber'),
        ('over', 'Below/above qty allowed'),
        ('below', 'Below quantity allowed')
    ], string='Picking method', required=True, default='exact')
    serialnumbers = fields.Text(string='Serialnumbers')
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', ondelete='set null')
    product_detail = fields.Char(string='Details')

    @api.model
    def default_get(self, fields):

        model_name = self._context.get('active_model')
        res_id = self._context.get('active_id')

        work_model = self.env[model_name]
        res = work_model.browse(res_id)

        result = {
            'outgoing_id': res.id,
            'picking_method': 'exact'
        }

        return result

    def product_allowed(self, product, units_used):

        if product.unit_id.id in units_used:
            return False
        if product.unit_id.parent_id and product.unit_id.parent_id.id in units_used:
            return False

        return True

    @api.multi
    def do_picking_exact(self):

        self.ensure_one()

        unit_product_model = self.env['s2u.warehouse.unit.product']
        assign_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        todos_cache = {}
        units_used = []
        for todo in self.outgoing_id.todo_ids:
            qty_to_assign = round(todo.product_qty + todo.shipped_qty + todos_cache.get(todo.id, 0.0), 2)
            if qty_to_assign > 0.0:
                products = unit_product_model.search([('product_id', '=', todo.product_id.id),
                                                      ('product_detail', '=', todo.product_detail)],
                                                     order='product_qty desc')
                for product in products:
                    if self.product_allowed(product, units_used):
                        if product.product_qty >= qty_to_assign:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= qty_to_assign
                            else:
                                todos_cache[todo.id] = qty_to_assign * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': qty_to_assign
                            })
                            break
                        else:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= product.product_qty
                            else:
                                todos_cache[todo.id] = product.product_qty * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': product.product_qty
                            })
                            qty_to_assign -= product.product_qty
        return True

    @api.multi
    def do_picking_over_below(self):

        self.ensure_one()

        unit_model = self.env['s2u.warehouse.unit']
        unit_product_model = self.env['s2u.warehouse.unit.product']

        assign_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assign_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        # select all units with products on it we have to deliver
        units_to_check = []
        todos_cache = {}
        units_used = []

        # only use unit picking for production company
        if self.user_has_groups('s2ubase.production_company'):
            for todo in self.outgoing_id.todo_ids:
                products = unit_product_model.search([('product_id', '=', todo.product_id.id),
                                                      ('product_detail', '=', todo.product_detail)])
                units_to_check += [p.unit_id.id for p in products]
            units_to_check = list(set(units_to_check))

            units = unit_model.browse(units_to_check)
            for unit in units:
                if self.outgoing_id.unit_for_assignment(unit, todos_cache):
                    assign_unit_model.create({
                        'outgoing_id': self.outgoing_id.id,
                        'unit_id': unit.id,
                    })
                    units_used.append(unit)

        for todo in self.outgoing_id.todo_ids:
            qty_to_assign = round(todo.product_qty + todo.shipped_qty + todos_cache.get(todo.id, 0.0), 2)
            if qty_to_assign > 0.0:
                products = unit_product_model.search([('product_id', '=', todo.product_id.id),
                                                      ('product_detail', '=', todo.product_detail)],
                                                     order='product_qty desc')
                for product in products:
                    if self.product_allowed(product, units_used):
                        if product.product_qty >= qty_to_assign:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= qty_to_assign
                            else:
                                todos_cache[todo.id] = qty_to_assign * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': qty_to_assign
                            })
                            break
                        else:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= product.product_qty
                            else:
                                todos_cache[todo.id] = product.product_qty * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': product.product_qty
                            })
                            qty_to_assign -= product.product_qty

        return True

    @api.multi
    def do_picking_serialnumber(self):

        self.ensure_one()

        unit_product_model = self.env['s2u.warehouse.unit.product']
        assign_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        todos_cache = {}
        units_used = []

        sn_lines = []
        sn_index = 0
        if self.serialnumbers:
            for sn in self.serialnumbers.split('\n'):
                if not sn.strip():
                    continue
                sn_lines.append(sn)

        for todo in self.outgoing_id.todo_ids:
            if sn_index >= len(sn_lines):
                break
            todo_product_detail = todo.product_detail if todo.product_detail else ''
            self_product_detail = self.product_detail if self.product_detail else ''
            if not (todo.product_id.id == self.product_id.id and todo_product_detail == self_product_detail):
                continue

            qty_to_assign = round(todo.product_qty + todo.shipped_qty + todos_cache.get(todo.id, 0.0), 2)
            if qty_to_assign <= 0.0:
                continue

            while int(qty_to_assign) > 0:
                if sn_index >= len(sn_lines):
                    break
                products = unit_product_model.search([('product_id', '=', todo.product_id.id),
                                                      ('product_detail', '=', todo.product_detail),
                                                      ('sn_registration', '=', True),
                                                      ('serialnumber', '=', sn_lines[sn_index]),
                                                      ('product_qty', '>', 0.0)],
                                                     order='product_qty desc')
                if not products:
                    raise UserError(_('Serialnumber %s not found!' % sn_lines[sn_index]))
                for product in products:
                    if self.product_allowed(product, units_used):
                        if product.product_qty >= qty_to_assign:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= qty_to_assign
                            else:
                                todos_cache[todo.id] = qty_to_assign * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': qty_to_assign
                            })
                            sn_index += 1
                            qty_to_assign = 0.0
                        else:
                            if todo.id in todos_cache:
                                todos_cache[todo.id] -= product.product_qty
                            else:
                                todos_cache[todo.id] = product.product_qty * -1.0
                            assign_product_model.create({
                                'outgoing_id': self.outgoing_id.id,
                                'unitproduct_id': product.id,
                                'assigned_qty': product.product_qty
                            })
                            sn_index += 1
                            qty_to_assign -= product.product_qty
        return True

    @api.multi
    def do_confirm(self):

        self.ensure_one()

        #self.outgoing_id.units_assigned_ids.unlink()
        #self.outgoing_id.items_assigned_ids.unlink()
        if self.outgoing_id.units_assigned_ids:
            raise UserError(_('Products already assigned!'))
        if self.outgoing_id.items_assigned_ids:
            raise UserError(_('Products already assigned!'))

        if self.picking_method == 'over':
            self.do_picking_over_below()
        elif self.picking_method in ['exact', 'below']:
            self.do_picking_exact()
        elif self.picking_method == 'sn':
            self.do_picking_serialnumber()

        self.outgoing_id.calculate_assigned()

        if self.picking_method == 'exact':
            for todo in self.outgoing_id.todo_ids:
                qty_to_assign = round(todo.product_qty + todo.shipped_qty - todo.assigned_qty, 2)
                if qty_to_assign > 0.0:
                    raise UserError(_('Not enough present for product %s to deliver!' % todo.product_id.name))

        return True

