# -*- coding: utf-8 -*-

import datetime

from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ProjectType(models.Model):
    _inherit = "s2u.project.type"

    label_for_service = fields.Char(string='Label for service')

    @api.multi
    def write(self, vals):
        if 'label_for_service' in vals:
            self.env['s2u.subscription.template'].search([('projecttype_id', '=', self.id)]).write({
                'label_for_service': vals['label_for_service']
            })
        return super(ProjectType, self).write(vals)
