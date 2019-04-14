# -*- coding: utf-8 -*-

import logging
import datetime
import math
import base64

from odoo import tools, modules
from odoo.osv import expression
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.website.models.website import slugify


class SubscriptionTemplate(models.Model):
    _inherit = "s2u.subscription.template"

    @api.model
    def _get_default_image(self):
        img_path = modules.get_module_resource('s2uproduct', 'static/src/img', 'product.png')
        with open(img_path, 'rb') as f:
            image = f.read()

        return tools.image_resize_image_big(base64.b64encode(image))

    @api.one
    def _compute_price_before_comma(self):

        def add_separator(number):
            s = '%d' % number
            groups = []
            while s and s[-1].isdigit():
                groups.append(s[-3:])
                s = s[:-3]
            return s + '.'.join(reversed(groups))

        if not self.price_gross:
            self.price_before_comma = '-'
        else:
            price_before = int(math.floor(self.price_gross))
            self.price_before_comma = add_separator(price_before)

    @api.one
    def _compute_price_after_comma(self):

        if not self.price_gross:
            self.price_after_comma = '--'
        else:
            price_after = int(round(self.price_gross - math.floor(self.price_gross), 2) * 100.0)
            self.price_after_comma = '%02d' % price_after

    @api.one
    def _compute_price_net_as_string(self):

        def add_separator(number):
            s = '%d' % number
            groups = []
            while s and s[-1].isdigit():
                groups.append(s[-3:])
                s = s[:-3]
            return s + '.'.join(reversed(groups))

        if not self.price:
            self.price_net_as_str = '-,--'
        else:
            if self.price_is_net:
                price = self.price
            else:
                price = self.price - self.vat_id.calc_vat_from_gross_amount(self.price)
            price_after = int(round(price - math.floor(price), 2) * 100.0)
            price_before = int(math.floor(price))
            self.price_net_as_str = '%s,%02d' % (add_separator(price_before), price_after)

    @api.one
    def _compute_price_as_float(self):

        if not self.price_gross:
            self.price_as_float = '0.00'
        else:
            price_before = int(math.floor(self.price_gross))
            price_after = int(round(self.price_gross - math.floor(self.price_gross), 2) * 100.0)
            self.price_as_float = '%d.%02d' % (price_before, price_after)

    @api.one
    def _compute_product_url(self):

        url = '/shop/subscription/%s-%s' % (slugify(self.name), self.id)

        self.product_url = url

    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        result = super(SubscriptionTemplate, self).write(vals)
        return result

    @api.model
    def create(self, vals):
        tools.image_resize_images(vals)
        result = super(SubscriptionTemplate, self).create(vals)
        return result

    image = fields.Binary("Image", attachment=True,
                          default=lambda self: self._get_default_image())
    image_medium = fields.Binary("Medium-sized image", attachment=True)
    image_small = fields.Binary("Small-sized image", attachment=True)
    description = fields.Text(string='Description')
    publish_webshop = fields.Boolean(string='Active in shop')
    price_before_comma = fields.Char(string='Before comma',
                                     store=False, readonly=True, compute='_compute_price_before_comma')
    price_after_comma = fields.Char(string='After comma',
                                    store=False, readonly=True, compute='_compute_price_after_comma')
    price_net_as_str = fields.Char(string='Net as str',
                                   store=False, readonly=True, compute='_compute_price_net_as_string')
    price_as_float = fields.Char(string='As float',
                                 store=False, readonly=True, compute='_compute_price_as_float')
    product_url = fields.Char(string='Product Url', store=False, readonly=True, compute='_compute_product_url')
    delivery_id = fields.Many2one('s2u.product.delivery', string='Delivery', index=True)
    hona = fields.Boolean(string='Hide when not available', default=False)
    no_delivery_id = fields.Many2one('s2u.product.delivery', string='No delivery', index=True)
    price_prefix = fields.Char(string='Price prefix')
    sub_ids = fields.Many2many('s2u.product.sub.category', 's2u_subscription_sub_cat_rel', 'subscription_id', 'sub_id',
                               string='Subscription categories')
    weight = fields.Float(string='Weight (kg)', digits=(16, 3))
