# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    def _get_outgoing_count(self):

        for entity in self:
            outgoings = self.env['s2u.warehouse.outgoing'].search([('entity_id', '=', entity.id)])
            outgoing_ids = [l.id for l in outgoings]
            outgoing_ids = list(set(outgoing_ids))
            entity.outgoing_count = len(outgoing_ids)

    def _get_outgoing_open_count(self):

        for entity in self:
            outgoings = self.env['s2u.warehouse.outgoing'].search([('entity_id', '=', entity.id),
                                                                   ('state', 'in', ['draft', 'production', 'ok'])])
            outgoing_ids = [l.id for l in outgoings]
            outgoing_ids = list(set(outgoing_ids))
            entity.outgoing_open_count = len(outgoing_ids)

    @api.multi
    def action_view_outgoing(self):
        outgoings = self.env['s2u.warehouse.outgoing'].search([('entity_id', '=', self.id)])
        outgoing_ids = [l.id for l in outgoings]
        outgoing_ids = list(set(outgoing_ids))

        result = self.env.ref('s2uwarehouse.action_warehouse_outgoing').read()[0]
        if outgoing_ids:
            result['domain'] = [('id', 'in', outgoing_ids)]
            result['context'] = {'default_entity_id': self.id}
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def _get_rma_count(self):

        for entity in self:
            rmas = self.env['s2u.warehouse.rma'].search([('entity_id', '=', entity.id)])
            entity.rma_count = len(rmas)

    def _get_rma_open_count(self):

        for entity in self:
            rmas = self.env['s2u.warehouse.rma'].search([('entity_id', '=', entity.id),
                                                         ('state', '!=', 'done')])
            entity.rma_open_count = len(rmas)

    @api.multi
    def action_view_rma(self):
        rmas = self.env['s2u.warehouse.rma'].search([('entity_id', '=', self.id)])

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rmas) > 1:
            action['domain'] = [('id', 'in', rmas.ids)]
        elif len(rmas) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_rma_form').id, 'form')]
            action['res_id'] = rmas[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_serialnumber_count(self):

        for entity in self:
            serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('entity_id', '=', entity.id)])
            serialnumbers = [s for s in serialnumbers if s.by_customer]
            entity.serialnumber_count = len(serialnumbers)

    @api.multi
    def action_view_serialnumber(self):
        serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('entity_id', '=', self.id)])
        serialnumbers = [s.id for s in serialnumbers if s.by_customer]

        action = self.env.ref('s2uwarehouse.action_warehouse_serialnumber').read()[0]
        if len(serialnumbers) >= 1:
            action['domain'] = [('id', 'in', serialnumbers)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    outgoing_count = fields.Integer(string='# of Deliveries', compute='_get_outgoing_count', readonly=True)
    outgoing_open_count = fields.Integer(string='# of Open deliveries', compute='_get_outgoing_open_count', readonly=True)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)
    rma_open_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_open_count', readonly=True)
    serialnumber_count = fields.Integer(string='# of Serialnumbers', compute='_get_serialnumber_count', readonly=True)
