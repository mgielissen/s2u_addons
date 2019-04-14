# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

logger = logging.getLogger(__name__)

class MainController(http.Controller):

    @http.route(['/instance'], auth='public', type="http", website=True)
    def instance_activate(self, **post):

        instances = request.env['s2u.instance'].sudo().search([('company_id', '=', request.website.company_id.id),
                                                               ('active', '=', True)])
        if not instances:
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'At the moment we have no instances you can choose from.'
            })

        return request.render("s2uecommerce_instance.instance_activate", {
            'error': {},
            'instances': instances,
            'form_values': {
                'email': '',
                'instance_id': instances[0].id
            }
        })

    @http.route('/instance/confirm', type='http', methods=['POST'], auth='public', website=True, csrf=True)
    def instance_activate_confirm(self, **post):

        fields = {
            'instance_id': 'int',
            'email': 'string',
        }

        form_values = {}
        for fld, fldtype in iter(fields.items()):
            if post.get(fld, False):
                if fldtype == 'int':
                    form_values[fld] = int(post.get(fld))
                else:
                    form_values[fld] = post.get(fld)

        if not form_values.get('email'):
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'We did not receive an email address.'
            })

        if not form_values.get('instance_id'):
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'There was no instance selected.'
            })

        instance = request.env['s2u.instance'].sudo().search([('company_id', '=', request.website.company_id.id),
                                                              ('id', '=', form_values['instance_id']),
                                                              ('active', '=', True)], limit=1)
        if not instance:
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'The selected instance is not available anymore.'
            })

        entity = request.env['s2u.crm.entity'].sudo().search([('company_id', '=', request.website.company_id.id),
                                                              ('entity_code', 'ilike', form_values['email'])], limit=1)
        if entity:
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'It seems an instance is already requested and/or activated on this email address.'
            })

        try:
            instance.create_and_send_quotation(form_values['email'])
        except Exception as e:
            logger.error("Error in create_and_send_quotation(): %s" % str(e))
            request.cr.rollback()
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'There was a problem during the confirmation process.'
            })

        return request.redirect('/instance/confirm/thanks')

    @http.route(['/instance/confirm/mail/<string:token>'], auth='public', type="http", website=True)
    def instance_activate_confirm_mail(self, token, **post):

        sale = request.env['s2u.sale'].sudo().search([('company_id', '=', request.website.company_id.id),
                                                      ('instance_token', '=', token),
                                                      ('state', '=', 'draft')], limit=1)
        if not sale:
            return request.render("website.404")
        if sale.instance_expired:
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'Your request was expired, please contact support.'
            })

        try:
            sale.do_quotation()
            sale.do_confirm()
        except Exception as e:
            logger.error("Error in do_quotation/do_confirm: %s" % str(e))
            request.cr.rollback()
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'There was a problem during creating the instance.'
            })

        request.cr.commit()

        try:
            sale.instance_id.activate_instance_and_send_login_info(sale)
        except Exception as e:
            logger.error("Error in activate_instance_and_send_login_info(): %s" % str(e))
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'There was a problem during creating the instance.'
            })

        return http.request.render('s2uecommerce_instance.instance_activate_mail_confirmed')

    @http.route('/instance/confirm/thanks', type='http', auth='public', website=True)
    def shop_checkout_thanks(self, **post):

        return http.request.render('s2uecommerce_instance.instance_activate_thanks')

    @http.route(['/instance/overview'], auth='public', type="http", website=True)
    def instance_overview(self, **post):

        instances = request.env['s2u.instance'].sudo().search([('company_id', '=', request.website.company_id.id)], order='name')
        if not instances:
            return http.request.render('s2uecommerce_instance.instance_oops', {
                'error': 'At the moment we have no instances you can choose from.'
            })

        return request.render("s2uecommerce_instance.instance_overview", {
            'instances': instances,
        })


