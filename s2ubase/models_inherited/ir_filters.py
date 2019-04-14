# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class IrFilters(models.Model):
    _inherit = 'ir.filters'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)

    @api.model
    def create(self, vals):

        if vals.get('name', False):
            vals['name'] = '%s/%d' % (vals['name'], self.env.user.company_id.id)
        filter = super(IrFilters, self).create(vals)

        return filter
