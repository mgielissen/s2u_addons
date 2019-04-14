# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class Outgoing(models.Model):
    _inherit = "s2u.warehouse.outgoing"

    @api.multi
    def sale_is_completed(self):

        for shipment in self:
            sales_orders = []
            for t in shipment.todo_ids:
                if self.env['s2u.subscriptionv2'].search([('sale_id', '=', t.sale_id.id),
                                                          ('state', '=', 'draft')]):
                    sales_orders.append(t.sale_id.id)
            sales_orders = list(set(sales_orders))
            for sale_id in sales_orders:
                todos = self.env['s2u.warehouse.outgoing.todo'].search([('outgoing_id', '=', shipment.id),
                                                                        ('sale_id', '=', sale_id)])
                activate_subscription = True
                for t in todos:
                    if round(t.product_qty + t.shipped_qty, 2) > 0.0:
                        activate_subscription = False
                        break
                if activate_subscription:
                    subscriptions = self.env['s2u.subscriptionv2'].search([('sale_id', '=', sale_id),
                                                                           ('state', '=', 'draft')])
                    for subscription in subscriptions:
                        subscription.action_activate()
                    subscriptions.create_invoices()

        return super(Outgoing, self).sale_is_completed()

    @api.multi
    def serialnumber_shipped_trigger(self, todo, product, product_detail, serialnumber, shipped):

        sn_shipped = super(Outgoing, self).serialnumber_shipped_trigger(todo, product, product_detail, serialnumber, shipped)

        # check if the products shipped, are done over a subscription
        if todo.saleline_id.product_id.res_model == 's2u.subscription.template':
            # is product has serialnumber registration, then shipped is always 1.0
            if product.sn_registration:
                needed_per_subscription = int(todo.product_qty / todo.saleline_id.product_qty)
                subscriptions = self.env['s2u.subscriptionv2'].search([('saleline_id', '=', todo.saleline_id.id)])
                for s in subscriptions:
                    serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('subscription_id', '=', s.id),
                                                                                   ('product_id', '=', product.id)])
                    serialnumbers = [s for s in serialnumbers if s.by_customer]

                    if len(serialnumbers) < needed_per_subscription:
                        sn_shipped['subscription_id'] = s.id
                        break
        return sn_shipped

    subscriptionv2_id = fields.Many2one('s2u.subscriptionv2', string='Subscription', ondelete='set null')


class RMA(models.Model):
    _inherit = "s2u.warehouse.rma"

    subscription_id = fields.Many2one('s2u.subscription', string='Subscription', ondelete='set null')
    subscriptionv2_id = fields.Many2one('s2u.subscriptionv2', string='Subscription', ondelete='set null')
