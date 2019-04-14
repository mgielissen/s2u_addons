# -*- coding: utf-8 -*-

import datetime
import uuid

from odoo import api, fields, models, _


class Sale(models.Model):
    _inherit = "s2u.sale"

    def _get_default_instance_token(self):
        return str(uuid.uuid4())

    def _get_default_instance_valid(self):
        return datetime.datetime.now() + datetime.timedelta(hours=4)

    def _compute_instance_expired(self):
        now = datetime.datetime.now()
        for order in self:
            if order.instance_valid and fields.Datetime.from_string(order.instance_valid) < now:
                order.instance_expired = True
            else:
                order.instance_expired = False

    instance_token = fields.Char('Instance Token', copy=False, default=_get_default_instance_token)
    instance_valid = fields.Datetime(string='Instance valid till', index=True, copy=False,
                                     default=_get_default_instance_valid)
    instance_expired = fields.Boolean(compute='_compute_instance_expired', string="Instance expired")
    create_instance = fields.Boolean(string="Create instance", default=False)
    instance_id = fields.Many2one('s2u.instance', string='Instance to create', ondelete='set null')
    instance_db = fields.Char(string='Instance DB')
    instance_admin_pw = fields.Char(string='Instance admin pw', invisible=True, copy=False)


