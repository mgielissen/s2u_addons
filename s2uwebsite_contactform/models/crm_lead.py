# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 's2u.crm.lead'

    def website_form_input_filter(self, request, values):

        return values
