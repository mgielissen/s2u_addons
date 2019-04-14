# -*- coding: utf-8 -*-

import math
import base64

from odoo import api, fields, models, _
from odoo import tools, modules
from odoo.exceptions import UserError, ValidationError
from odoo.addons.website.models.website import slugify


class CrmEntityDiscountProduct(models.Model):
    _name = 's2u.crm.entity.discount.product'

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    product_id = fields.Many2one('s2u.sale.product', string='Product', required=True, ondelete='cascade')
    discount_type = fields.Selection([('price', 'Use this price'),
                                      ('percent', '% discount')], required=True, string='Type', default='price')
    discount = fields.Monetary(string='Price/%', currency_field='currency_id')


class CrmEntity(models.Model):

    _inherit = 's2u.crm.entity'

    def _get_discount_products_count(self):

        for entity in self:
            discounts = self.env['s2u.crm.entity.discount.product'].search([('entity_id', '=', entity.id)])
            entity.discount_products_count = len(discounts)

    @api.multi
    def action_view_discount_products(self):
        discounts = self.env['s2u.crm.entity.discount.product'].search([('entity_id', '=', self.id)])

        action = self.env.ref('s2uproduct.action_sale_product_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.id
        }
        action['context'] = str(context)
        return action

    discount_product_ids = fields.One2many('s2u.crm.entity.discount.product', 'entity_id',
                                           string='Discount for products', copy=True)
    discount_products_count = fields.Integer(string='# of Product discounts', compute='_get_discount_products_count', readonly=True)

