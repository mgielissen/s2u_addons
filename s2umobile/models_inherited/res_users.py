# -*- coding: utf-8 -*-

from odoo import fields, models


class User(models.Model):

    _inherit = 'res.users'

    pushover_user_key = fields.Char('Pushover user key', copy=False)
    pushover_messages = fields.Boolean('Pushover messages', default=True)
    pushover_leads = fields.Boolean('Pushover leads', default=True)


