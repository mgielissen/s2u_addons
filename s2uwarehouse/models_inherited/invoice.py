# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountInvoiceLine(models.Model):
    _inherit = "s2u.account.invoice.line"

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Outgoing', index=True,
                                  ondelete='restrict')

