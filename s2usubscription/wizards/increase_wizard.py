# -*- coding: utf-8 -*-
import datetime

from odoo import _, api, fields, models


class ActionSubscriptionIncreaseService(models.TransientModel):
    _name = 's2usubscription.action.increase.service'
    _description = 'Extends or adds a service to an existing subscription'

    @api.onchange('extend_subscription', 'service_id')
    def _onchange_service(self):
        if self.extend_subscription and self.service_id:
            self.price = self.service_id.price
            self.date_start = self.subscription_order_id.date_end
        else:
            self.price = 0.0
            self.date_start = False

    increase_id = fields.Many2one('s2usubscription.action.increase', string='Increase', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='increase_id.currency_id', store=True)
    subscription_order_id = fields.Many2one('s2u.subscription.order', string='Service', ondelete='set null')
    extend_subscription = fields.Boolean('Extend', default=False)
    service_id = fields.Many2one('s2u.subscription.template', string='Service', ondelete='set null')
    price = fields.Monetary(string='Amount monthly', related='service_id.price')
    date_start = fields.Date(string='Start')
    state = fields.Selection([
        ('draft', 'Concept'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], string='State')
    date_end = fields.Date(string='Ends')


class ActionubscriptionIncrease(models.TransientModel):
    """
    """
    _name = 's2usubscription.action.increase'
    _description = 'Extends or adds a service to an existing subscription'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    subscription_id = fields.Many2one('s2u.subscription', string="Subscription", ondelete='set null')
    service_ids = fields.One2many('s2usubscription.action.increase.service', 'increase_id', string='Services')

    @api.model
    def default_get(self, fields):

        result = super(ActionubscriptionIncrease, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        subscription = self.env['s2u.subscription'].browse(active_ids[0])

        lines = []
        for so in subscription.order_ids:
            if so.is_extended:
                continue
            if so.state in ['active', 'done', 'cancel']:
                lines.append((0, 0, {
                    'subscription_order_id': so.id,
                    'state': so.state,
                    'date_end': so.date_end,
                    'service_id': so.template_id.id,
                    'price': so.amount
                }))
        result['service_ids'] = lines
        result['subscription_id'] = subscription.id

        return result

    @api.multi
    def do_increase(self):

        self.ensure_one()

        def make_next_date(start_date, prev_date, unit):

            dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            dt_previous = datetime.datetime.strptime(prev_date, '%Y-%m-%d')

            if unit == 'month':
                if dt_previous.month == 12:
                    new_month = 1
                    new_year = dt_previous.year + 1
                else:
                    new_month = dt_previous.month + 1
                    new_year = dt_previous.year
            else:
                new_month = dt_previous.month
                new_year = dt_previous.year + 1

            new_day = dt_start.day
            next_date = False
            while new_day:
                try:
                    next_date = '%d-%d-%d' % (new_year, new_month, new_day)
                    dt = datetime.datetime.strptime(next_date, '%Y-%m-%d')
                    break
                except ValueError:
                    # blijkbaar hebben we met de 31e te maken of schikkeljaar voor feb, van 31 terug naar 30 etc.
                    # en dan opnieuw proberen
                    new_day -= 1

            return next_date

        subscription = self.subscription_id

        for service in self.service_ids:
            if not service.extend_subscription:
                continue
            service_vals = {
                'subscription_id': subscription.id,
                'template_id': service.service_id.id,
                'product_detail': service.subscription_order_id.product_detail
            }
            new_service = self.env['s2u.subscription.order'].create(service_vals)

            start_date = fields.Date.context_today(self)
            if service.date_start:
                start_date = service.date_start

            next_date = start_date
            for i in range(service.service_id.months):
                exists = self.env['s2u.subscription.period'].search([('subscription_id', '=', subscription.id),
                                                                     ('state', '=', 'pending'),
                                                                     ('date', '=', next_date)])
                if exists:
                    period = exists[0]
                else:
                    period = self.env['s2u.subscription.period'].create({
                        'subscription_id': subscription.id,
                        'type': subscription.type,
                        'partner_id': subscription.partner_id.id,
                        'contact_id': subscription.contact_id.id if subscription.contact_id else False,
                        'address_id': subscription.address_id.id if subscription.address_id else False,
                        'date': next_date,
                    })

                trans = self.env['s2u.subscription.period.transaction'].create({
                    'period_id': period.id,
                    'template_id': service.service_id.id,
                    'order_id': new_service.id,
                    'amount': service.service_id.price,
                    'reference': _('Extended/added services')
                })
                next_date = make_next_date(start_date, next_date, service.service_id.period_unit)

            new_service.write({
                'date_start': start_date,
                'date_end': next_date,
                'state': 'active'
            })

            service.subscription_order_id.write({
                'is_extended': True
            })

        subscription.write({
            'state': 'active'
        })

        return {'type': 'ir.actions.act_window_close'}
