# -*- coding: utf-8 -*-

import math
import json
import base64
import werkzeug.urls

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import binary_content
from odoo import tools, modules, SUPERUSER_ID

MAX_PRODUCTS_PER_PAGE = 6

class MainController(http.Controller):

    def convert_float(self, v):

        def add_separator(number):
            s = '%d' % number
            groups = []
            while s and s[-1].isdigit():
                groups.append(s[-3:])
                s = s[:-3]
            return s + '.'.join(reversed(groups))

        if not v:
            return '0,00'
        else:
            price_after = int(round(v - math.floor(v), 2) * 100.0)
            price_before = int(math.floor(v))
            return  '%s,%02d' % (add_separator(price_before), price_after)

    def abbreviated_pages(self, n, page, page_url=''):

        if not n or not page:
            return []

        if '?' in page_url:
            page_url = '%s&page=' % page_url
        else:
            page_url = '%s?page=' % page_url

        assert(0 < n)
        assert(0 < page <= n)

        if n <= 5:
            pages = set(range(1, n + 1))
        else:
            pages = (set(range(1, 4))
                     | set(range(max(1, page - 1), min(page + 2, n + 1)))
                     | set(range(n - 1, n + 2)))

        def display():
            pages_o = []
            last_page = 0
            for p in sorted(pages):
                if p != last_page + 1:
                    pages_o.append('...')
                if p <= n:
                    pages_o.append({'url': page_url + '%s' % p,
                                    'num': p})
                last_page = p

            return pages_o

        return display()

    def save_shoppingcard(self, post):

        if request.httprequest.method == 'GET':
            return False

        items = post.get('items', 0)
        request.session['shoppingcart'] = False

        if items:
            shoppingcart = []
            no = 0
            for i in range(int(items)):
                product_id = post.get('product_%d' % (i + 1))
                product_model = post.get('model_%d' % (i + 1))
                domain = [('company_id', '=', request.website.company_id.id),
                          ('publish_webshop', '=', True),
                          ('id', '=', product_id)]
                product = request.env[product_model].sudo().search(domain)
                if not product:
                    continue
                product = product[0]
                if product.publish_webshop:
                    no += 1
                    item = {
                        'product_model': product._name,
                        'product_url': product.product_url,
                        'product_id': product_id,
                        'product': product.name,
                        'no': no,
                        'price': product.price_gross,
                        'price_net': product.price_netto,
                        'price_string': self.convert_float(product.price_gross),
                        'weight': product.weight,
                        'qty_1': '',
                        'qty_2': '',
                        'qty_3': '',
                        'qty_4': '',
                        'qty_5': '',
                        'qty_6': '',
                        'qty_7': '',
                        'qty_8': '',
                        'qty_9': '',
                        'qty': 0,
                    }
                    qty = int(post.get('qty_%d' % (i + 1), 0))
                    if 1 <= qty <= 9:
                        item['qty_%d' % qty] = 'selected'
                        item['qty'] = qty

                    shoppingcart.append(item)

            request.session['shoppingcart'] = shoppingcart

        return True

    def save_filter(self, post, use_variant=False):

        domain = [('company_id', '=', request.website.company_id.id),
                  ('publish_webshop', '=', True)]
        if use_variant:
            domain.append(('variant_id', '=', use_variant.id))

        if request.httprequest.method == 'GET':
            if request.session.get('filter_values'):
                filter_values = request.session['filter_values']
            else:
                filter_values = {}
            filter_items = filter_values
        else:
            filter_items = {}
            convert_items = post.items()
            for k, v in iter(convert_items):
                filter_items[k] = v

        filter_values = {
            'filter_search': ''
        }

        subids = []
        try:
            for k, v in filter_items.items():
                if k == 'filter_search':
                    continue
                if k.startswith('subfilter'):
                    subids.append(int(v))
                    filter_values[k] = int(v)
                if k.startswith('filter'):
                    filter_values[k] = int(v)
        except:
            subids = []

        if subids:
            domain.append(('sub_ids', 'in', subids))
        if filter_items.get('filter_search'):
            domain.append('|')
            domain.append(('name', 'ilike', filter_items.get('filter_search')))
            domain.append(('description', 'ilike', filter_items.get('filter_search')))
            filter_values['filter_search'] = filter_items.get('filter_search')

        request.session['filter_values'] = filter_values
        return domain

    def get_categories(self):

        categories = request.env['s2u.product.category'].sudo().search(
            [('company_id', '=', request.website.company_id.id)])

        filter_categories = []
        if categories:
            for cat in categories:
                vals = {'name': cat.title,
                        'id': cat.id,
                        'subcats': []}
                for sub in cat.sub_ids:
                    vals['subcats'].append({'name': sub.name,
                                            'id': sub.id})
                filter_categories.append(vals)

        return filter_categories

    @http.route('/shop', type='http', auth='public', website=True)
    def shop_product_list(self, **post):

        self.save_shoppingcard(post)
        product_domain = self.save_filter(post)

        if request.session.get('shoppingcart'):
            shoppingcart = request.session['shoppingcart']
        else:
            shoppingcart = []

        if request.session.get('filter_values'):
            filter_values = request.session['filter_values']
        else:
            filter_values = {
                'filter_search': ''
            }

        products = request.env['s2u.ecommerce.shop'].search_products(product_domain)
        if not products:
            domain = [('company_id', '=', request.website.company_id.id),
                      ('publish_webshop', '=', True)]
            products = request.env['s2u.ecommerce.shop'].search_products(domain)
            if not products:
                return http.request.render('s2uecommerce.shop_product_empty')
            else:
                return http.request.render('s2uecommerce.shop_product_empty_filter', {
                    'shoppingcart': shoppingcart,
                    'categories': self.get_categories(),
                    'filtervals': filter_values
                })

        tot_products = len(products)

        tot_pages = len(products) / MAX_PRODUCTS_PER_PAGE
        if len(products) % MAX_PRODUCTS_PER_PAGE > 0:
            tot_pages += 1
        tot_pages = int(tot_pages)
        pages = self.abbreviated_pages(tot_pages, 1, '/shop')

        try:
            current_page = int(post.get('page', 1))
        except:
            current_page = 1

        if current_page > 1:
            rel_prev = '%s?page=%d' % ('/shop', current_page - 1)
        else:
            rel_prev = False
        if current_page < tot_pages:
            rel_next = '%s?page=%d' % ('/shop', current_page + 1)
        else:
            rel_next = False

        page = current_page
        counter_product = 0
        page -= 1
        selected_products = []
        for product in products:
            if page == 0:
                selected_products.append(product)
                counter_product += 1
                if counter_product == MAX_PRODUCTS_PER_PAGE:
                    break
            else:
                counter_product += 1
                if counter_product == MAX_PRODUCTS_PER_PAGE:
                    page -= 1
                    counter_product = 0
        values = {
            'products': selected_products,
            'shoppingcart': shoppingcart,
            'pages': pages,
            'tot_pages': tot_pages,
            'tot_products': tot_products,
            'current_page': current_page,
            'rel_prev': rel_prev,
            'rel_next': rel_next,
            'categories': self.get_categories(),
            'filtervals': filter_values
        }

        values = request.env['s2u.ecommerce.shop'].prepare_canonical(values, post)
        return http.request.render('s2uecommerce.shop_product_list', values)

    @http.route(['/shop/variant/<string:variantname_and_id>'], auth='public', type="http", website=True)
    def shop_product_variants(self, variantname_and_id, **post):

        self.save_shoppingcard(post)

        if request.session.get('shoppingcart'):
            shoppingcart = request.session['shoppingcart']
        else:
            shoppingcart = []

        if request.session.get('filter_values'):
            filter_values = request.session['filter_values']
        else:
            filter_values = {
                'filter_search': ''
            }

        variant_data = variantname_and_id.split('-')
        if variant_data and len(variant_data) > 1:
            variant_id = variant_data[-1]
        else:
            variant_id = 0
        try:
            variant_id = int(variant_id)
        except:
            return request.render("website.404")

        variant_domain = [('company_id', '=', request.website.company_id.id),
                          ('id', '=', variant_id)]
        variant = request.env['s2u.product.variant'].sudo().search(variant_domain, limit=1)
        if not variant:
            return request.render("website.404")

        product_domain = self.save_filter(post, use_variant=variant)

        products = request.env['s2u.ecommerce.shop'].search_products(product_domain, use_variant=variant)
        if not products:
            return http.request.render('s2uecommerce.shop_product_empty_filter', {
                'shoppingcart': shoppingcart,
                'categories': self.get_categories(),
                'filtervals': filter_values
            })

        tot_products = len(products)

        tot_pages = len(products) / MAX_PRODUCTS_PER_PAGE
        if len(products) % MAX_PRODUCTS_PER_PAGE > 0:
            tot_pages += 1
        tot_pages = int(tot_pages)
        pages = self.abbreviated_pages(tot_pages, 1, '/shop/variant/%s' % variantname_and_id)

        try:
            current_page = int(post.get('page', 1))
        except:
            current_page = 1

        if current_page > 1:
            rel_prev = '%s?page=%d' % ('/shop/variant/%s' % variantname_and_id, current_page - 1)
        else:
            rel_prev = False
        if current_page < tot_pages:
            rel_next = '%s?page=%d' % ('/shop/variant/%s' % variantname_and_id, current_page + 1)
        else:
            rel_next = False

        page = current_page
        counter_product = 0
        page -= 1
        selected_products = []
        for product in products:
            if page == 0:
                selected_products.append(product)
                counter_product += 1
                if counter_product == MAX_PRODUCTS_PER_PAGE:
                    break
            else:
                counter_product += 1
                if counter_product == MAX_PRODUCTS_PER_PAGE:
                    page -= 1
                    counter_product = 0
        values = {
            'products': selected_products,
            'shoppingcart': shoppingcart,
            'pages': pages,
            'tot_pages': tot_pages,
            'tot_products': tot_products,
            'current_page': current_page,
            'rel_prev': rel_prev,
            'rel_next': rel_next,
            'categories': self.get_categories(),
            'filtervals': filter_values
        }

        values = request.env['s2u.ecommerce.shop'].prepare_canonical(values, post)
        return http.request.render('s2uecommerce.shop_variant_list', values)

    @http.route(['/shop/product/<string:productname_and_id>'], auth='public', type="http", website=True)
    def shop_product_detail(self, productname_and_id, **post):

        product_data = productname_and_id.split('-')
        if product_data and len(product_data) > 1:
            product_id = product_data[-1]
        else:
            product_id = 0

        try:
            product_id = int(product_id)
        except:
            return request.render("website.404")

        product_domain = [('company_id', '=', request.website.company_id.id),
                          ('publish_webshop', '=', True),
                          ('id', '=', product_id)]
        product = request.env['s2u.sale.product'].sudo().search(product_domain)
        if product:

            if request.session.get('shoppingcart'):
                shoppingcart = request.session['shoppingcart']
            else:
                shoppingcart = []

            values = {
                'product': product,
                'shoppingcart': shoppingcart,
            }
            values = request.env['s2u.ecommerce.shop'].prepare_canonical(values, post)
            return request.render("s2uecommerce.shop_product_detail", values)
        else:
            return request.render("website.404")


    @http.route('/shop/checkout', type='http', auth='public', website=True, csrf=True)
    def shop_checkout(self, **post):

        if request.httprequest.method == 'POST':
            self.save_shoppingcard(post)

        if not request.session.get('shoppingcart', False):
            return request.redirect('/shop')

        countries = request.env['s2u.sale.country'].allowed_countries(request.website.company_id.id)
        if not countries:
            return http.request.render('s2uecommerce.ecommerce_oops', {
                'error': 'Er zijn geen landen aanwezig om naar te leveren.'
            })

        if request.session.get('checkout_data'):
            default = request.session['checkout_data']
        else:
            entity = False
            # check if user is logged in
            if request.env.user != request.website.user_id:
                entity = request.env['s2u.crm.entity'].sudo().\
                    search([('odoo_res_partner_id', '=', request.env.user.partner_id.id)], limit=1)
                if entity:
                    default = {
                        'country_id': request.env['s2u.sale.country'].default_country(request.website.company_id.id),
                        'delivery_country_id': request.env['s2u.sale.country'].default_country(
                            request.website.company_id.id),
                        'type_b2c': 'True' if entity.type == 'b2c' else '',
                        'type_b2b': 'True' if entity.type == 'b2b' else '',
                        'delivery_same': 'True',
                        'delivery_different': '',
                        'type_delivery_b2c': 'True',
                        'type_delivery_b2b': '',
                    }
                    if entity.type == 'b2b':
                        default['company'] = entity.name
                        if entity.tinno:
                            default['tinno'] = entity.tinno
                        if entity.c_of_c:
                            default['c_of_c'] = entity.c_of_c

                        address = entity.get_physical()
                        if address:
                            if address.address:
                                default['address'] = address.address
                            if address.zip:
                                default['zip'] = address.zip
                            if address.city:
                                default['city'] = address.city
                            if address.country_id:
                                default['country_id'] = request.env['s2u.sale.country'].\
                                    convert_country(request.website.company_id.id, address.country_id.id)
                    else:
                        default['name'] = entity.name
                        if entity.address:
                            default['address'] = entity.address
                        if entity.zip:
                            default['zip'] = entity.zip
                        if entity.city:
                            default['city'] = entity.city
                        if entity.country_id:
                            default['country_id'] = request.env['s2u.sale.country'].\
                                    convert_country(request.website.company_id.id, entity.country_id.id)
                        if entity.email:
                            default['email'] = entity.email
                        if entity.phone:
                            default['phone'] = entity.phone
                else:
                    default = {
                        'country_id': request.env['s2u.sale.country'].\
                                    convert_country(request.website.company_id.id, request.env.user.partner_id.country_id.id),
                        'delivery_country_id': request.env['s2u.sale.country'].\
                                    convert_country(request.website.company_id.id, request.env.user.partner_id.country_id.id),
                        'type_b2c': 'True' if not request.env.user.partner_id.company_name else '',
                        'type_b2b': 'True' if request.env.user.partner_id.company_name else '',
                        'company': request.env.user.partner_id.company_name,
                        'address': request.env.user.partner_id.street,
                        'zip': request.env.user.partner_id.zip,
                        'city': request.env.user.partner_id.city,
                        'delivery_same': 'True',
                        'delivery_different': '',
                        'type_delivery_b2c': 'True',
                        'type_delivery_b2b': '',
                        'name': request.env.user.partner_id.name,
                        'email': request.env.user.partner_id.email
                    }
            else:
                default = {
                    'country_id': request.env['s2u.sale.country'].default_country(request.website.company_id.id),
                    'delivery_country_id': request.env['s2u.sale.country'].default_country(request.website.company_id.id),
                    'type_b2c': 'True',
                    'type_b2b': '',
                    'delivery_same': 'True',
                    'delivery_different': '',
                    'type_delivery_b2c': 'True',
                    'type_delivery_b2b': '',
                }
                if request.env.user != request.website.user_id:
                    default['name'] = request.env.user.name
                    default['email'] = request.env.user.email

        return http.request.render('s2uecommerce.shop_checkout', {
            'default': default,
            'error': {},
            'countries': countries
        })

    @http.route('/shop/checkout/confirm', type='http', methods=['POST'], auth='public', website=True, csrf=True)
    def shop_checkout_confirm(self, **post):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        fields = {
            'order_type': 'string',
            'company': 'string',
            'c_of_c': 'string',
            'tinno': 'string',
            'contact_prefix': 'string',
            'name': 'string',
            'address': 'string',
            'zip': 'string',
            'city': 'string',
            'country_id': 'int',
            'email': 'string',
            'phone': 'string',
            'delivery_type': 'string',
            'order_delivery_type': 'string',
            'delivery_company': 'string',
            'delivery_name': 'string',
            'delivery_address': 'string',
            'delivery_zip': 'string',
            'delivery_city': 'string',
            'delivery_country_id': 'int'
        }

        form_values = {}
        for fld, fldtype in iter(fields.items()):
            if post.get(fld, False):
                if fldtype == 'int':
                    form_values[fld] = int(post.get(fld))
                else:
                    form_values[fld] = post.get(fld)

        if form_values.get('order_type', False) == 'b2b':
            form_values['type_b2c'] = ''
            form_values['type_b2b'] = 'True'
        else:
            form_values['type_b2c'] = 'True'
            form_values['type_b2b'] = ''

        if form_values.get('delivery_type', False) == 'different':
            form_values['delivery_same'] = ''
            form_values['delivery_different'] = 'True'
        else:
            form_values['delivery_same'] = 'True'
            form_values['delivery_different'] = ''

        if form_values.get('order_delivery_type', False) == 'b2b':
            form_values['type_delivery_b2c'] = ''
            form_values['type_delivery_b2b'] = 'True'
        else:
            form_values['type_delivery_b2c'] = 'True'
            form_values['type_delivery_b2b'] = ''

        request.session['checkout_data'] = form_values

        order_items = []
        tot_netto = 0.0
        tot_bruto = 0.0
        shipment_costs = request.env['s2u.payment.transaction'].get_shipment_costs(request.session['checkout_data'],
                                                                                   request.session['shoppingcart'])
        if shipment_costs:
            tot_shipment = shipment_costs.price
        else:
            tot_shipment = 0.0
        for item in request.session['shoppingcart']:
            order_items.append({'model': item['product_model'],
                                'data': request.env[item['product_model']].sudo().browse(int(item['product_id'])),
                                'product': item['product'],
                                'qty': item['qty'],
                                'tot_amount': self.convert_float(item['qty'] * item['price_net'])})
            tot_netto += (item['qty'] * item['price_net'])
            tot_bruto += (item['qty'] * item['price'])

        domain = [('company_id', '=', request.website.company_id.id),
                  ('provider_active', '=', True)]
        return http.request.render('s2uecommerce.shop_checkout_payment', {
            'acquirers': request.env['s2u.payment.acquirer'].sudo().search(domain),
            'order_items': order_items,
            'order': {
                'tot_amount_net': self.convert_float(tot_netto),
                'tot_amount_vat': self.convert_float(round(tot_bruto - tot_netto, 2)),
                'tot_amount_gross': self.convert_float(tot_bruto),
                'tot_amount_shipment': self.convert_float(tot_shipment),
                'tot_amount_to_pay': self.convert_float(round(tot_bruto + tot_shipment, 2))
            },
            'default': {},
            'error': {}
        })

    @http.route('/shop/sync_cart', type='http', methods=['POST'], auth='public', website=True, csrf=False)
    def shop_sync_cart(self, **post):

        return json.dumps({
            'sync': self.save_shoppingcard(post)
        })

    @http.route('/shop/checkout/payment', type='http', methods=['POST'], auth='public', website=True, csrf=True)
    def shop_checkout_payment(self, **post):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        return http.request.render('s2uecommerce.shop_checkout_final', {
            'default': {},
            'error': {}
        })

    @http.route('/shop/checkout/final', type='http', methods=['POST'], auth='public', website=True, csrf=True)
    def shop_checkout_final(self, **post):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        request.session['shoppingcart'] = False
        request.session['checkout_data'] = False
        request.session['filter_values'] = False

        return request.redirect('/shop/checkout/thanks')

    @http.route('/shop/checkout/thanks', type='http', auth='public', website=True)
    def shop_checkout_thanks(self, **post):

        return http.request.render('s2uecommerce.shop_checkout_thanks')

    @http.route(['/shop/product/picture/<string:product_model>/<string:product_id>/<string:picture>/<string:size>'], type='http', auth='public', website=True)
    def shop_product_picture(self, product_model=None, product_id=None, picture='default', size='default'):

        try:
            product_id = int(product_id)
        except:
            product_id = False

        if size == 'medium':
            field_name = 'image_medium'
        elif size == 'small':
            field_name = 'image_small'
        else:
            field_name = 'image'

        content = False

        request.cr.execute("SELECT id FROM s2u_baseproduct_item "
                           "WHERE company_id = %s AND res_model = %s LIMIT 1",
                           (request.website.company_id.id, product_model))

        exists = request.cr.fetchall()
        if exists:
            status, headers, content = binary_content(model=product_model, id=product_id, field=field_name,
                                                      default_mimetype='image/jpeg',
                                                      env=request.env(user=SUPERUSER_ID))

        if not content:
            img_path = modules.get_module_resource('s2uecommerce', 'static/src/img', 'product_preview.png')
            with open(img_path, 'rb') as f:
                image = f.read()

            content = base64.b64encode(image)

        if status == 304:
            return werkzeug.wrappers.Response(status=304)
        image_base64 = base64.b64decode(content)

        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status = str(status)
        return response
