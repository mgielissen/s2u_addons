# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseAvailable(models.Model):
    _name = "s2u.warehouse.available"

    @api.one
    def _compute_available(self):
        qty_available = 0.0
        qty_assigned = 0.0

        item = self.env['s2u.baseproduct.item'].search([('res_model', '=', self.product_id.res_model),
                                                        ('res_id', '=', self.product_id.res_id)])
        if not item:
            raise UserError(
                _("s2u.baseproduct.item not found. Please contact you administrator."))
        item = item[0]

        units = self.env['s2u.warehouse.unit.product'].search([('product_id', '=', item.id),
                                                               ('product_detail', '=', self.product_detail),
                                                               ('unit_id.active', '=', True)])
        for unit in units:
            qty_available += unit.product_qty
            qty_assigned += unit.assigned_qty
        self.qty_available = qty_available
        self.qty_assigned = qty_assigned

    @api.one
    def _compute_reserved(self):

        tot_reserved = 0.0

        self.qty_reserved = tot_reserved

    def _get_outgoing_count(self):

        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        for available in self:
            outgoing_ids = []

            item = self.env['s2u.baseproduct.item'].search([('res_model', '=', available.product_id.res_model),
                                                            ('res_id', '=', available.product_id.res_id)], limit=1)
            if not item:
                available.outgoing_count = 0
                continue

            unit_products = self.env['s2u.warehouse.unit.product'].search([('product_id', '=', item.id),
                                                                           ('product_detail', '=', available.product_detail),
                                                                           ('unit_id.active', '=', True),
                                                                           ('assigned_qty', '>', 0.0)])
            units = [up.unit_id.id for up in unit_products]
            assigned_products = assigned_product_model.search([('unitproduct_id', 'in', unit_products.ids)])
            for ap in assigned_products:
                outgoing_ids.append(ap.outgoing_id.id)
            assigned_units = assigned_unit_model.search([('unit_id', 'in', units)])
            for au in assigned_units:
                outgoing_ids.append(au.outgoing_id.id)

            outgoing_ids = list(set(outgoing_ids))
            available.outgoing_count = len(outgoing_ids)

    @api.multi
    def action_view_outgoing(self):
        assigned_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_product_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        outgoing_ids = []

        item = self.env['s2u.baseproduct.item'].search([('res_model', '=', self.product_id.res_model),
                                                        ('res_id', '=', self.product_id.res_id)], limit=1)
        if item:
            unit_products = self.env['s2u.warehouse.unit.product'].search([('product_id', '=', item.id),
                                                                           ('product_detail', '=', self.product_detail),
                                                                           ('unit_id.active', '=', True),
                                                                           ('assigned_qty', '>', 0.0)])
            units = [up.unit_id.id for up in unit_products]
            assigned_products = assigned_product_model.search([('unitproduct_id', 'in', unit_products.ids)])
            for ap in assigned_products:
                outgoing_ids.append(ap.outgoing_id.id)
            assigned_units = assigned_unit_model.search([('unit_id', 'in', units)])
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

    unitproduct_ids = fields.One2many('s2u.warehouse.unit.product', 'available_id',
                                      string='Products', copy=False)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True)
    product_detail = fields.Char(string='Details', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    qty_available = fields.Float(string='Available', compute=_compute_available, readonly=True)
    qty_assigned = fields.Float(string='Assigned', compute=_compute_available, readonly=True)
    qty_reserved = fields.Float(string='Qty reserved', compute=_compute_reserved, readonly=True)
    outgoing_count = fields.Integer(string='# of Deliveries', compute='_get_outgoing_count', readonly=True)
