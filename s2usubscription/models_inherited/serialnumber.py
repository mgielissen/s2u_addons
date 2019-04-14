# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseSerialnumber(models.Model):
    _inherit = "s2u.warehouse.serialnumber"

    subscription_id = pallet_id = fields.Many2one('s2u.subscriptionv2', string='Subscription', index=True,
                                                  ondelete='set null')
