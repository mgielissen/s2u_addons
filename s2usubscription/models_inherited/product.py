# -*- coding: utf-8 -*-

import math
import base64

from odoo import api, fields, models, _
from odoo import tools, modules
from odoo.exceptions import UserError, ValidationError
from odoo.addons.website.models.website import slugify


class Registration(models.Model):
    _inherit = "s2u.product.registration"

    subscription_id = pallet_id = fields.Many2one('s2u.subscriptionv2', string='Subscription', index=True,
                                                  ondelete='set null')
