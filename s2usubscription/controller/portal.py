# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import consteq


class PortalSubscription(CustomerPortal):
    
    def _get_subscription_domain(self):
        entity = request.env['s2u.crm.entity'].sudo(). \
            search([('odoo_res_partner_id', '=', request.env.user.partner_id.id)], limit=1)
        domain = [
            ('partner_id', '=', entity.id)
        ]
        return domain

    def _prepare_portal_layout_values(self):
        values = super(PortalSubscription, self)._prepare_portal_layout_values()
        subscription_count = request.env['s2u.subscription.order'].search_count(self._get_subscription_domain())
        values['subscription_count'] = subscription_count
        return values

    # ------------------------------------------------------------
    # My Subscriptions
    # ------------------------------------------------------------

    def _subscription_check_access(self, subscription_id, access_token=None):
        subscription = request.env['s2u.subscription.order'].browse([subscription_id])
        subscription_sudo = subscription.sudo()
        try:
            subscription.check_access_rights('read')
            subscription.check_access_rule('read')
        except AccessError:
            raise
        return subscription_sudo

    def _subscription_get_page_view_values(self, subscription, access_token, **kwargs):
        values = {
            'page_name': 'subscription',
            'subscription': subscription,
        }
        if access_token:
            values['no_breadcrumbs'] = True
            values['access_token'] = access_token

        if kwargs.get('error'):
            values['error'] = kwargs['error']
        if kwargs.get('warning'):
            values['warning'] = kwargs['warning']
        if kwargs.get('success'):
            values['success'] = kwargs['success']

        return values

    @http.route(['/my/subscriptions', '/my/subscriptions/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_subscriptions(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Subscription = request.env['s2u.subscription.order']

        domain = self._get_subscription_domain()

        searchbar_sortings = {
            'date_start': {'label': _('Date from'), 'order': 'date_start desc'},
            'date_end': {'label': _('Date till'), 'order': 'date_end desc'},
            'state': {'label': _('Status'), 'order': 'state'},
        }
        # default sort by order
        if not sortby:
            sortby = 'date_start'
        order = searchbar_sortings[sortby]['order']

        archive_groups = self._get_archive_groups('s2u.subscription.order', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # count for pager
        subscription_count = Subscription.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/subscriptions",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=subscription_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        subscriptions = Subscription.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        values.update({
            'date': date_begin,
            'subscriptions': subscriptions,
            'page_name': 'subscription',
            'pager': pager,
            'archive_groups': archive_groups,
            'default_url': '/my/subscriptions',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("s2usubscription.portal_my_subscriptions", values)

    @http.route(['/my/subscriptions/<int:subscription_id>'], type='http', auth="public", website=True)
    def portal_my_subscription_detail(self, subscription_id, access_token=None, **kw):
        try:
            subscription_sudo = self._subscription_check_access(subscription_id, access_token)
        except AccessError:
            return request.redirect('/my')

        values = self._subscription_get_page_view_values(subscription_sudo, access_token, **kw)
        return request.render("s2usubscription.portal_subscription_page", values)

    # ------------------------------------------------------------
    # My Home
    # ------------------------------------------------------------

    def details_form_validate(self, data):
        error, error_message = super(PortalSubscription, self).details_form_validate(data)

        return error, error_message
