# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class MainController(http.Controller):

    @http.route('/shop/checkout/payment/manual', type='http', auth='public', website=True)
    def shop_checkout_payment_manual(self):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        domain = [('company_id', '=', request.website.company_id.id),
                  ('provider', '=', 'manual'),
                  ('provider_active', '=', True)]
        acquirers = request.env['s2u.payment.acquirer'].sudo().search(domain)

        if not acquirers:
            return http.request.render('s2upayment_manual.payment_oops', {
                'error': 'No manual payment acquirer defined.'
            })

        acquirer = acquirers[0]

        try:
            transaction = request.env['s2u.payment.transaction'].start_transaction(acquirer,
                                                                                   request.session['checkout_data'],
                                                                                   request.session['shoppingcart'])
        except Exception as e:
            return http.request.render('s2upayment_manual.payment_oops', {
                'error': e.message
            })

        return http.request.render('s2upayment_manual.shop_checkout_confirm', {
            'transaction': transaction
        })

    @http.route('/shop/checkout/payment/manual/confirm/<string:trans_id1>/<string:trans_id2>', type='http', auth='public', website=True)
    def shop_checkout_payment_manual_confirm(self, trans_id1, trans_id2):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        trans_model = request.env['s2u.payment.transaction']

        try:
            domain = [('company_id', '=', request.website.company_id.id),
                      ('name', '=', trans_id1),
                      ('id', '=', int(trans_id2))]
            transactions = trans_model.sudo().search(domain)
        except Exception as e:
            return http.request.render('s2upayment_manual.payment_oops', {
                'error': e.message
            })

        if not transactions:
            return http.request.render('s2upayment_manual.payment_oops', {
                'error': 'No transaction present.'
            })
        transaction = transactions[0]
        if not transaction.is_valid:
            return request.redirect('/shop')

        transaction.confirm_transaction(method='manual', default_vals=None)

        request.session['shoppingcart'] = False
        return http.request.render('s2uecommerce.shop_checkout_thanks')
