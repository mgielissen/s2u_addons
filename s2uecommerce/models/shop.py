# -*- coding: utf-8 -*-

from odoo.http import request
from odoo import api, fields, models, _
from odoo import tools, modules
from odoo.addons.base.ir.ir_mail_server import encode_header_param


class Shop(models.Model):
    _name = 's2u.ecommerce.shop'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)

    @api.multi
    def get_relative_url_from_shop_part(self):

        try:
            url = request.httprequest.url
            if '?' in url:
                url = url.split('?')
                part = url[0].index('/shop')
                url = url[0][part:]
            else:
                url = False
        except:
            url = False

        return url

    @api.multi
    def prepare_canonical(self, values, params):

        url = self.get_relative_url_from_shop_part()

        if not url:
            return values

        if params and len(params) == 1 and params.get('page', False):
            try:
                page = int(params.get('page', False))
            except:
                page = 1
            if page > 1:
                return values

        values['use_canonical'] = 'https://%s%s' % (request.website.domain, url)

        return values

    @api.multi
    def search_products(self, product_domain, use_variant=False):

        def check_filters_active(domain):
            for d in domain:
                if d[0] in ['sub_ids', 'name', 'description']:
                    return True
            return False

        res = []
        variants_used = []
        filters_active = check_filters_active(product_domain)

        products = self.env['s2u.sale.product'].sudo().search(product_domain)
        for p in products:
            if p.hona and p.qty_virtual <= 0.0:
                continue
            if filters_active:
                # ignore variant when using filters
                res.append(p)
            elif use_variant:
                res.append(p)
            elif p.variant_id:
                if p.variant_id.id not in variants_used:
                    res.append(p)
                    variants_used.append(p.variant_id.id)
            else:
                res.append(p)
        return res




