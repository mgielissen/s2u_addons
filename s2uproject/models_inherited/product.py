# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class SaleProduct(models.Model):
    _inherit = 's2u.sale.product'

    def _get_product_types(self):
        types = super(SaleProduct, self)._get_product_types()
        types.append(['changerequest', 'Standard change request'])
        return types

    def is_service(self):

        self.ensure_one()
        if self.product_type == 'changerequest':
            return True
        return super(SaleProduct, self).is_service()

class BaseProductItem(models.Model):
    _inherit = "s2u.baseproduct.item"

    def _get_product_types(self):
        types = super(BaseProductItem, self)._get_product_types()
        types.append(['changerequest', 'Standard change request'])
        return types

    def is_service(self):
        self.ensure_one()
        if self.product_type == 'changerequest':
            return True
        return super(BaseProductItem, self).is_service()
