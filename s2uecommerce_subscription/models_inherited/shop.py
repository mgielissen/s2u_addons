# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class Shop(models.Model):
    _inherit = 's2u.ecommerce.shop'

    @api.multi
    def search_products(self, product_domain):

        res = super(Shop, self).search_products(product_domain)

        products = self.env['s2u.subscription.template'].sudo().search(product_domain)
        for p in products:
            res.append(p)

        return res