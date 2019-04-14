# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    def _get_invoice_count(self):

        for entity in self:
            invoices = self.env['s2u.account.invoice'].search([('partner_id', '=', entity.id)])
            invoice_ids = [l.id for l in invoices]
            invoice_ids = list(set(invoice_ids))
            entity.invoice_count = len(invoice_ids)

    def _get_invoice_open_count(self):

        for entity in self:
            invoices = self.env['s2u.account.invoice'].search([('partner_id', '=', entity.id), ('paid_state', '=', 'open')])
            invoice_ids = [l.id for l in invoices]
            invoice_ids = list(set(invoice_ids))
            entity.invoice_open_count = len(invoice_ids)

    def _get_so_count(self):

        for entity in self:
            sales = self.env['s2u.sale'].search([('partner_id', '=', entity.id)])
            sales_ids = [l.id for l in sales]
            sales_ids = list(set(sales_ids))
            entity.so_count = len(sales_ids)

    def _get_so_open_count(self):

        for entity in self:
            sales = self.env['s2u.sale'].search([('partner_id', '=', entity.id),
                                                 ('state', 'in', ['draft', 'quot', 'order', 'payment', 'confirm', 'run'])])
            sales_ids = [l.id for l in sales]
            sales_ids = list(set(sales_ids))
            entity.so_open_count = len(sales_ids)

    @api.multi
    def action_view_invoice(self):
        invoices = self.env['s2u.account.invoice'].search([('partner_id', '=', self.id)])
        invoice_ids = [l.id for l in invoices]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice').read()[0]
        action['context'] = {
            'default_partner_id': self.id
        }
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('s2uaccount.invoice_form').id, 'form')]
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_so(self):
        sales = self.env['s2u.sale'].search([('partner_id', '=', self.id)])
        sales_ids = [l.id for l in sales]
        sales_ids = list(set(sales_ids))

        action = self.env.ref('s2usale.action_sale').read()[0]
        action['context'] = {
            'default_partner_id': self.id
        }
        if len(sales_ids) > 1:
            action['domain'] = [('id', 'in', sales_ids)]
        elif len(sales_ids) == 1:
            action['views'] = [(self.env.ref('s2usale.sale_form').id, 'form')]
            action['res_id'] = sales_ids[0]
        else:
            action['domain'] = [('partner_id', '=', self.id)]
            context = {
                'search_default_open': 1,
                'default_partner_id': self.id,
            }
            action['context'] = str(context)
        return action

    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    invoice_open_count = fields.Integer(string='# of Open invoices', compute='_get_invoice_open_count', readonly=True)
    so_count = fields.Integer(string='# of Sales', compute='_get_so_count', readonly=True)
    so_open_count = fields.Integer(string='# of Open sales', compute='_get_so_open_count', readonly=True)

