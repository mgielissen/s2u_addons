# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class MainController(http.Controller):

    @http.route(['/shop/subscription/<string:productname_and_id>'], auth='public', type="http", website=True)
    def shop_product_detail(self, productname_and_id, **post):

        product_data = productname_and_id.split('-')
        if product_data and len(product_data) > 1:
            product_id = product_data[-1]
        else:
            product_id = 0

        try:
            product_id = int(product_id)
        except:
            return request.website.render("website.404")

        product_domain = [('company_id', '=', request.website.company_id.id),
                          ('publish_webshop', '=', True),
                          ('id', '=', product_id)]
        subscription = request.env['s2u.subscription.template'].sudo().search(product_domain)
        if subscription:
            if request.session.get('shoppingcart'):
                shoppingcart = request.session['shoppingcart']
            else:
                shoppingcart = []

            values = {
                'product': subscription,
                'shoppingcart': shoppingcart,
            }
            values = request.env['s2u.ecommerce.shop'].prepare_canonical(values, post)
            return request.render("s2uecommerce_subscription.shop_product_detail", values)
        else:
            return request.render("website.404")
