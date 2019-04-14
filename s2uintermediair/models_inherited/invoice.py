# -*- coding: utf-8 -*-

import datetime

from openerp.exceptions import UserError, ValidationError
from openerp import api, fields, models, _


class Invoice(models.Model):
    _inherit = "s2u.account.invoice"

    def _compute_bijdrage(self):
        account = self.env['s2u.account.account'].search([('code', '=', '8075')])
        if account:
            bijdrage = 0.0
            excl_bijdrage = 0.0
            for l in self.line_ids:
                if l.account_id.id == account.id:
                    bijdrage += l.net_amount
            self.amount_bijdrage = bijdrage
        else:
            self.amount_bijdrage = 0.0

    def _compute_linked_orders(self):
        linked_so = []
        for l in self.line_ids:
            if l.sale_id and l.sale_id.reference:
                linked_so.append(l.sale_id.reference)
        self.intermediair_linked_orders = ','.join(linked_so)

    amount_bijdrage = fields.Monetary(string='Bijdrage', store=False, compute='_compute_bijdrage')
    intermediair_linked_orders = fields.Char(string='Linked orders', store=False, compute='_compute_linked_orders')



