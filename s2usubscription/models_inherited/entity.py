# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntityDiscountSubscription(models.Model):
    _name = 's2u.crm.entity.discount.subscription'

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    subscription_id = fields.Many2one('s2u.subscription.template', string='Subscription', required=True, ondelete='cascade')
    discount_type = fields.Selection([('price', 'Use this price'),
                                      ('percent', '% discount')], required=True, string='Type', default='price')
    discount = fields.Monetary(string='Price/%', currency_field='currency_id')


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    def _get_subscriptions_count(self):

        for entity in self:
            subscriptions = self.env['s2u.subscriptionv2'].search([('partner_id', '=', entity.id)])
            subscriptions_ids = [l.id for l in subscriptions]
            subscriptions_ids = list(set(subscriptions_ids))
            entity.subscriptions_count = len(subscriptions_ids)

    def _get_subscriptions_open_count(self):

        for entity in self:
            subscriptions = self.env['s2u.subscriptionv2'].search([('partner_id', '=', entity.id),
                                                                   ('state', 'in', ['draft', 'active'])])
            subscriptions_ids = [l.id for l in subscriptions]
            subscriptions_ids = list(set(subscriptions_ids))
            entity.subscriptions_open_count = len(subscriptions_ids)

    @api.multi
    def action_view_subscriptions(self):
        subscriptions = self.env['s2u.subscriptionv2'].search([('partner_id', '=', self.id)])
        subscription_ids = [s.id for s in subscriptions]
        subscription_ids = list(set(subscription_ids))

        action = self.env.ref('s2usubscription.action_subscriptionv2').read()[0]
        if len(subscription_ids) > 1:
            action['domain'] = [('id', 'in', subscription_ids)]
        elif len(subscription_ids) == 1:
            action['views'] = [(self.env.ref('s2usubscription.subscriptionv2_form').id, 'form')]
            action['res_id'] = subscription_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_discount_subscriptions_count(self):

        for entity in self:
            discounts = self.env['s2u.crm.entity.discount.subscription'].search([('entity_id', '=', entity.id)])
            entity.discount_subscriptions_count = len(discounts)

    @api.multi
    def action_view_discount_subscriptions(self):
        discounts = self.env['s2u.crm.entity.discount.subscription'].search([('entity_id', '=', self.id)])

        action = self.env.ref('s2usubscription.action_sale_subscription_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.id
        }
        action['context'] = str(context)
        return action

    subscriptions_count = fields.Integer(string='# of Subscriptions', compute='_get_subscriptions_count', readonly=True)
    subscriptions_open_count = fields.Integer(string='# of Open subscriptions', compute='_get_subscriptions_open_count', readonly=True)
    discount_subscription_ids = fields.One2many('s2u.crm.entity.discount.subscription', 'entity_id',
                                                string='Discount for subscriptions', copy=True)
    discount_subscriptions_count = fields.Integer(string='# of Subscription discounts', compute='_get_discount_subscriptions_count',
                                                  readonly=True)
    invoice_condition = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half-yearly', 'Half-yearly'),
        ('yearly', 'Yearly'),
    ], string='Service invoicing')
    service_notify = fields.Integer(string='Service notify')
