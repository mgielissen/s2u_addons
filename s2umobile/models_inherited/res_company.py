# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):

    _inherit = 'res.company'

    pushover_app_key = fields.Char('Pushover app key', copy=False)
