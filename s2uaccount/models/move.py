# -*- coding: utf-8 -*-

import datetime

from odoo.osv import expression
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _name = "s2u.account.move"
    _description = "Financial moves related to other objects"

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(string='Description', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=_default_currency)
    date_trans = fields.Date(string='Date', index=True, copy=False, required=True,
                             default=lambda self: fields.Date.context_today(self))
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True, ondelete='restrict',
                                 index=True)
    debit = fields.Monetary(string='Debit', currency_field='currency_id')
    credit = fields.Monetary(string='Credit', currency_field='currency_id')
    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Id.', required=True, index=True)
    special_info = fields.Char(string="Special info", index=True)

