# -*- coding: utf-8 -*-

import uuid

from odoo import api, fields, models, _


class PaymentAcquirer(models.Model):
    _name = 's2u.payment.acquirer'
    _description = 'Payment Acquirer'
    _order = 'sequence'

    @api.multi
    def _get_providers(self):
        return []

    # indirection to ease inheritance
    _provider_selection = lambda self, *args, **kwargs: self._get_providers(*args, **kwargs)

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(required=True, index=True, string='Name')
    sequence = fields.Integer(string='Sequence', default=10)
    environment = fields.Selection([('test', 'Test'),
                                    ('prod', 'Production')], string='Environment', required=True, default='test')
    provider = fields.Selection(_provider_selection, string='Provider', required=True)
    provider_active = fields.Boolean(string='Active', default=True)
    so_template_id = fields.Many2one('s2u.sale.template', string='Sale template')

