# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseSerialnumber(models.Model):
    _name = "s2u.warehouse.serialnumber"
    _order = "product_id, name"

    @api.one
    def _compute_by_customer(self):

        self.by_customer = False

        if self.entity_id and self.product_id and self.name:
            transactions = self.env['s2u.warehouse.unit.product.transaction'].search([('entity_id', '=', self.entity_id.id),
                                                                                      ('rel_product_id', '=', self.product_id.id),
                                                                                      ('rel_serialnumber', '=', self.name)])
            tot_trans = 0.0
            for t in transactions:
                trans_product_detail = t.rel_product_detail if t.rel_product_detail else ''
                self_product_detail = self.product_detail if self.product_detail else ''
                if trans_product_detail != self_product_detail:
                    continue
                tot_trans += t.qty
            if int(tot_trans) < 0:
                self.by_customer = True

    @api.multi
    def do_sn_shipped(self, sn_shipped):

        return self.create(sn_shipped)

    def _get_transaction_count(self):

        for serialnumber in self:
            transactions = self.env['s2u.warehouse.unit.product.transaction'].search([('rel_product_id', '=', serialnumber.product_id.id),
                                                                                      ('rel_serialnumber', '=', serialnumber.name)])
            serialnumber.transaction_count = len(transactions)

    @api.multi
    def action_view_transaction(self):
        transactions = self.env['s2u.warehouse.unit.product.transaction'].search([('rel_product_id', '=', self.product_id.id),
                                                                                  ('rel_serialnumber', '=', self.name)])
        action = self.env.ref('s2uwarehouse.action_warehouse_unit_product_transaction').read()[0]
        if len(transactions) >= 1:
            action['domain'] = [('id', 'in', transactions.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(string='Serialnumber', index=True, required=True, copy=False)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True, ondelete='cascade')
    product_detail = fields.Char(string='Details')
    outgoing_line_id = fields.Many2one('s2u.warehouse.outgoing.todo', string='Outgoing line', index=True,
                                       ondelete='cascade')
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Outgoing', index=True, related='outgoing_line_id.outgoing_id')
    entity_id = fields.Many2one('s2u.crm.entity', string='Customer', index=True, related='outgoing_id.entity_id')
    by_customer = fields.Boolean(string='By customer', compute=_compute_by_customer, readonly=True)
    transaction_count = fields.Integer(string='# of Transactions', compute='_get_transaction_count', readonly=True)
