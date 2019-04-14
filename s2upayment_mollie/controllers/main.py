# -*- coding: utf-8 -*-

from mollie.api.client import Client
from mollie.api.error import Error

from odoo import http
from odoo.http import request


class MainController(http.Controller):

    @http.route('/shop/checkout/payment/ideal', type='http', auth='public', website=True)
    def shop_checkout_payment_ideal(self):

        if not request.session['shoppingcart']:
            return request.redirect('/shop')

        domain = [('company_id', '=', request.website.company_id.id),
                  ('provider', '=', 'mollie'),
                  ('provider_active', '=', True)]
        acquirers = request.env['s2u.payment.acquirer'].sudo().search(domain)

        if not acquirers:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'No iDeal payment acquirer defined.'
            })

        acquirer = acquirers[0]

        try:
            transaction = request.env['s2u.payment.transaction'].start_transaction(acquirer,
                                                                                   request.session['checkout_data'],
                                                                                   request.session['shoppingcart'])
        except Exception as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

        try:
            mollie = Client()
            if acquirer.environment == 'test':
                mollie.set_api_key(acquirer.mollie_api_key_test)
                base_url = acquirer.mollie_base_url_test
            else:
                mollie.set_api_key(acquirer.mollie_api_key_prod)
                base_url = acquirer.mollie_base_url_prod

            redirectUrl = '%s/shop/checkout/payment/ideal/return/%s/%s' % (base_url, transaction.name, transaction.id)
            webhookUrl = '%s/shop/checkout/payment/ideal/webhook/%s/%s' % (base_url, transaction.name, transaction.id)

            payment_vals = {
                'amount': {
                    'currency': 'EUR',
                    'value': '%0.2f' % transaction.tot_to_pay
                },
                'description': acquirer.mollie_description,
                'redirectUrl': redirectUrl,
                'webhookUrl': webhookUrl,
                'method': 'ideal'
            }
            payment = mollie.payments.create(payment_vals)
            return request.redirect(payment.checkout_url)
        except Error as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })
        except Exception as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

    @http.route('/shop/checkout/payment/ideal/return/<string:trans_id1>/<string:trans_id2>', type='http', auth='public',
                website=True)
    def shop_checkout_payment_ideal_return(self, trans_id1=False, trans_id2=False):

        trans_model = request.env['s2u.payment.transaction']

        try:
            domain = [('company_id', '=', request.website.company_id.id),
                      ('name', '=', trans_id1),
                      ('id', '=', int(trans_id2))]
            transaction = trans_model.sudo().search(domain, limit=1)
        except Exception as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

        if not transaction:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'No transaction present.'
            })
        if not transaction.is_valid:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'No valid transaction present.'
            })

        try:
            mollie = Client()
            if transaction.acquirer_id.environment == 'test':
                mollie.set_api_key(transaction.acquirer_id.mollie_api_key_test)
            else:
                mollie.set_api_key(transaction.acquirer_id.mollie_api_key_prod)
        except Error as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

        request.session['shoppingcart'] = False

        if transaction.state == 'done':
            return http.request.render('s2uecommerce.shop_checkout_thanks')
        elif transaction.state == 'draft':
            return http.request.render('s2uecommerce.shop_checkout_pending')
        elif transaction.state == 'cancel':
            return request.redirect('/shop')
        else:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'Something did go wrong in your transaction.'
            })

    @http.route('/shop/checkout/payment/ideal/webhook/<string:trans_id1>/<string:trans_id2>', methods=['POST'], type='http',
                auth='public', website=True, csrf=False)
    def shop_checkout_payment_ideal_webhook(self, trans_id1, trans_id2,  **post):

        trans_model = request.env['s2u.payment.transaction']

        try:
            domain = [('company_id', '=', request.website.company_id.id),
                      ('name', '=', trans_id1),
                      ('id', '=', int(trans_id2))]
            transaction = trans_model.sudo().search(domain, limit=1)
        except Exception as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

        if not transaction:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'No transaction present.'
            })
        if not transaction.is_valid:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': 'No valid transaction present.'
            })

        try:
            mollie = Client()
            if transaction.acquirer_id.environment == 'test':
                mollie.set_api_key(transaction.acquirer_id.mollie_api_key_test)
            else:
                mollie.set_api_key(transaction.acquirer_id.mollie_api_key_prod)

            payment_id = post.get('id')
            payment = mollie.payments.get(payment_id)
        except Error as e:
            return http.request.render('s2upayment_mollie.payment_oops', {
                'error': str(e)
            })

        if payment.is_paid():
            vals = {
                'is_paid': True,
                'reference': payment_id
            }
            transaction.confirm_transaction(method='mollie', default_vals=vals)
        elif payment['status'] == 'error':
            transaction.write({
                'state': 'error'
            })
        elif payment['status'] == 'cancelled':
            transaction.write({
                'state': 'cancel'
            })
        elif payment['status'] == 'expired':
            transaction.write({
                'state': 'expired'
            })

        return http.request.render('s2upayment_mollie.payment_webhook_ok')
