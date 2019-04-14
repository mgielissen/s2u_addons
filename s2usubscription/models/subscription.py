# -*- coding: utf-8 -*-

import logging
import datetime
import math

from odoo.osv import expression
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Subscriptionv2(models.Model):
    _name = "s2u.subscriptionv2"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Subscription"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Subscriptionv2, self)._track_subtype(init_values)

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for s in self:
            if s.type == 'b2b':
                if s.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b debitor!'))
                if s.contact_id and s.contact_id.entity_id != s.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if s.address_id and s.address_id.entity_id != s.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if s.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.partner_id:
            delivery = self.partner_id.prepare_delivery()
            self.delivery_address = delivery

            if self.partner_id.type == 'b2b':
                address = self.partner_id.get_physical()
                if address and address.country_id:
                    self.delivery_country_id = address.country_id
                else:
                    self.delivery_country_id = False

                if self.partner_id.tinno:
                    self.delivery_tinno = self.partner_id.tinno
                else:
                    self.delivery_tinno = False
            else:
                if self.partner_id.country_id:
                    self.delivery_country_id = self.partner_id.country_id
                else:
                    self.delivery_country_id = False
                self.delivery_tinno = False

            if self.partner_id.lang:
                self.delivery_lang = self.partner_id.lang
            else:
                self.delivery_lang = False

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            delivery = self.contact_id.display_company + '\n'
            if self.contact_id.prefix:
                delivery += '%s\n' % self.contact_id.prefix
            else:
                delivery += '%s\n' % self.contact_id.name
            if self.contact_id.address_id:
                if self.contact_id.address_id.address:
                    delivery += '%s\n' % self.contact_id.address_id.address
                if self.contact_id.address_id.zip and self.contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.contact_id.address_id.zip, self.contact_id.address_id.city)
                elif self.contact_id.address_id.city:
                    delivery += '%s\n' % self.contact_id.address_id.city
                if self.contact_id.address_id.country_id:
                    delivery += '%s\n' % self.contact_id.address_id.country_id.name
            elif self.partner_id:
                address = self.partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    elif address.city:
                        delivery += '%s\n' % address.city
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.one
    def unlink(self):

        for subscription in self:
            if subscription.state == 'active':
                raise ValidationError(_('You can not delete an active subscription!'))

        res = super(Subscriptionv2, self).unlink()

        return res

    def _get_invoice_count(self):

        for subscription in self:
            invoices = self.env['s2u.subscriptionv2.invoice'].search([('subscription_id', '=', subscription.id)])
            invoice_ids = [l.invoice_id.id for l in invoices]
            invoice_ids = list(set(invoice_ids))
            subscription.invoice_count = len(invoice_ids)

    @api.multi
    def action_view_invoice(self):
        invoices = self.env['s2u.subscriptionv2.invoice'].search([('subscription_id', '=', self.id)])
        invoice_ids = [l.invoice_id.id for l in invoices]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice').read()[0]
        if len(invoice_ids) >= 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_rma_count(self):

        for subscription in self:
            rmas = self.env['s2u.warehouse.rma'].search([('subscriptionv2_id', '=', subscription.id)])
            subscription.rma_count = len(rmas)

    @api.multi
    def action_view_rma(self):
        rmas = self.env['s2u.warehouse.rma'].search([('subscriptionv2_id', '=', self.id)])

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rmas) >= 1:
            action['domain'] = [('id', 'in', rmas.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def name_get(self):
        result = []
        for sub in self:
            if sub.service_id:
                name = sub.service_id.get_product_name()
            else:
                name = ''
            if sub.sale_id and sub.reference:
                order_info = sub.sale_id.name + '/' + sub.reference
            elif sub.sale_id:
                order_info = sub.sale_id.name
            elif sub.reference:
                order_info = sub.reference
            else:
                order_info = ''
            if name:
                name = '%s %s' % (name, order_info)
            else:
                name = order_info
            result.append((sub.id, name))
        return result

    def _get_outgoing_count(self):

        for sub in self:
            todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', sub.sale_id.id)])
            outgoing_ids = [l.outgoing_id.id for l in todolines]
            outgoing_ids = list(set(outgoing_ids))
            sub.outgoing_count = len(outgoing_ids)

    @api.multi
    def action_view_outgoing(self):
        todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', self.sale_id.id)])
        outgoing_ids = [l.outgoing_id.id for l in todolines]
        outgoing_ids = list(set(outgoing_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_outgoing').read()[0]
        if len(outgoing_ids) > 1:
            action['domain'] = [('id', 'in', outgoing_ids)]
        elif len(outgoing_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_outgoing_form').id, 'form')]
            action['res_id'] = outgoing_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def _get_amount_for_invoice(self):

        for sub in self:
            sub.amount_for_invoice = 0.0
            if sub.invoice_condition == 'monthly':
                if sub.current_period < sub.periods:
                    sub.amount_for_invoice = sub.amount
                    sub.period_for_invoice = 1
            elif sub.invoice_condition == 'quarterly':
                periods_left = sub.periods - sub.current_period
                if periods_left >= 3:
                    sub.amount_for_invoice = sub.amount * 3
                    sub.period_for_invoice = 3
                else:
                    sub.amount_for_invoice = sub.amount * periods_left
                    sub.period_for_invoice = periods_left
            elif sub.invoice_condition == 'half-yearly':
                periods_left = sub.periods - sub.current_period
                if periods_left >= 6:
                    sub.amount_for_invoice = sub.amount * 6
                    sub.period_for_invoice = 6
                else:
                    sub.amount_for_invoice = sub.amount * periods_left
                    sub.period_for_invoice = periods_left
            elif sub.invoice_condition == 'yearly':
                periods_left = sub.periods - sub.current_period
                if periods_left >= 12:
                    sub.amount_for_invoice = sub.amount * 12
                    sub.period_for_invoice = 12
                else:
                    sub.amount_for_invoice = sub.amount * periods_left
                    sub.period_for_invoice = periods_left
            else:
                raise ValueError(_('Unknown invoice condition!'))

    @api.one
    @api.depends('date_end', 'partner_id.service_notify', 'state')
    def _compute_notify(self):

        if self.state and self.date_end and self.state == 'active':
            date_notify = datetime.datetime.strptime(self.date_end, "%Y-%m-%d")
            if self.partner_id and self.partner_id.service_notify:
                date_notify = date_notify - datetime.timedelta(days=self.partner_id.service_notify)
            else:
                date_notify = date_notify - datetime.timedelta(days=45)
            self.date_notify = date_notify.strftime('%Y-%m-%d')
        else:
            self.date_notify = False

    def _get_serialnumber_count(self):

        for subscription in self:
            serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('subscription_id', '=', subscription.id)])
            serialnumbers = [s for s in serialnumbers if s.by_customer]
            subscription.serialnumber_count = len(serialnumbers)

    @api.multi
    def action_view_serialnumber(self):
        serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('subscription_id', '=', self.id)])
        serialnumbers = [s.id for s in serialnumbers if s.by_customer]

        action = self.env.ref('s2uwarehouse.action_warehouse_serialnumber').read()[0]
        if len(serialnumbers) >= 1:
            action['domain'] = [('id', 'in', serialnumbers)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    _subscription_state = {
        'draft': [('readonly', False)],
    }

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_subscription_state)
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor', required=True, index=True,
                                 readonly=True, states=_subscription_state)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True, readonly=True,
                                 states=_subscription_state)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, readonly=True,
                                 states=_subscription_state)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('stop', 'Stopped'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', track_visibility='onchange')
    date = fields.Date(string='Date', index=True, copy=False, readonly=True, states=_subscription_state,
                       default=lambda self: fields.Date.context_today(self))
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')
    payment_type = fields.Selection([
        ('transfer', 'Rekening'),
        ('incasso', 'Incasso')
    ], required=True, default='transfer', string='Payment type', readonly=True, states=_subscription_state)
    payment_key = fields.Char(string='Payment key', readonly=True, states=_subscription_state)
    sale_id = fields.Many2one('s2u.sale', string='SO', readonly=True, related='saleline_id.sale_id', store=True)
    saleline_id = fields.Many2one('s2u.sale.line', string='SO', required=True, index=True,
                                  readonly=True, states=_subscription_state, ondelete='restrict')
    reference = fields.Char(string='Short descript.', index=True, readonly=True, related='sale_id.reference',
                            store=True)
    service_id = fields.Many2one('s2u.subscription.template', string='Service', required=True, ondelete='restrict')
    product_detail = fields.Char(string='Service details')
    amount = fields.Monetary(string='Amount (monthly)', required=True, readonly=True, states=_subscription_state)
    periods = fields.Integer(string='Duration (months)', required=True, readonly=True, states=_subscription_state)
    period_unit = fields.Selection([
        ('month', 'Month'),
        ('year', 'Year'),
    ], required=True, default='month', string='Unit', readonly=True, states=_subscription_state)
    date_start = fields.Date(string='Start', index=True, copy=False, readonly=True, states=_subscription_state)
    date_end = fields.Date(string='Ends', index=True, copy=False)
    action_on_end = fields.Selection([
        ('stop', 'Stop subscription'),
        ('extend', 'Extend subscription')
    ], required=True, default='stop', string='Action on end')
    current_period = fields.Integer(string='Current period', default=0)
    create_next_invoice = fields.Date(string='Create next invoice', index=True, copy=False)
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)
    outgoing_count = fields.Integer(string='# of Deliveries', compute='_get_outgoing_count', readonly=True)
    invoice_condition = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half-yearly', 'Half-yearly'),
        ('yearly', 'Yearly'),
    ], required=True, default='monthly', string='Invoicing', readonly=True, states=_subscription_state)
    amount_for_invoice = fields.Monetary(string='Amount for invoice', compute='_get_amount_for_invoice', readonly=True)
    period_for_invoice = fields.Integer(string='Period for invoice', compute='_get_amount_for_invoice', readonly=True)
    date_notify = fields.Date(string='Notify', index=True, store=True, compute='_compute_notify', readonly=True)
    serialnumber_count = fields.Integer(string='# of Serialnumbers', compute='_get_serialnumber_count', readonly=True)

    @api.multi
    def action_activate(self):

        def make_next_date(start_date, prev_date, periods):

            dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            dt_previous = datetime.datetime.strptime(prev_date, '%Y-%m-%d')

            new_month = dt_previous.month
            new_year = dt_previous.year
            for i in range(periods):
                if new_month == 12:
                    new_month = 1
                    new_year += 1
                else:
                    new_month += 1

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

        self.ensure_one()

        if self.state != 'draft':
            return False

        if not self.date_start:
            start_date = fields.Date.context_today(self)
        else:
            start_date = self.date_start
        end_date = start_date

        end_date = make_next_date(start_date, end_date, self.periods)

        self.write({
            'date_start': start_date,
            'date_end': end_date,
            'current_period': 0,
            'create_next_invoice': start_date,
            'state': 'active'
        })

    @api.multi
    def create_invoices(self):

        def make_next_date(start_date, prev_date, periods):

            dt_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            dt_previous = datetime.datetime.strptime(prev_date, '%Y-%m-%d')

            new_month = dt_previous.month
            new_year = dt_previous.year
            for i in range(periods):
                if new_month == 12:
                    new_month = 1
                    new_year += 1
                else:
                    new_month += 1

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

        def get_key(subscription):
            key = [
                str(subscription.sale_id.id),
                subscription.type,
                str(subscription.partner_id.id),
                str(subscription.contact_id.id) if subscription.contact_id and subscription.type == 'b2b' else '',
                str(subscription.address_id.id) if subscription.address_id and subscription.type == 'b2b' else '',
            ]

            return ','.join(key)

        invoice_model = self.env['s2u.account.invoice']

        subscriptions = {}
        for subscription in self:
            if get_key(subscription) not in subscriptions:
                subscriptions[get_key(subscription)] = [subscription]
            else:
                subscriptions[get_key(subscription)].append(subscription)

        for k, subscriptions_grouped in iter(subscriptions.items()):
            services = {}
            for sg in subscriptions_grouped:
                if sg.current_period == sg.periods:
                    if sg.action_on_end == 'extend':
                        sg.write({
                            'create_next_invoice': False,
                            'current_period': 0
                        })
                        # TODO: build history
                    else:
                        sg.write({
                            'state': ' stop',
                            'create_next_invoice': False
                        })
                        # try to create RMA if needed for products we need to receive back
                        sg.create_rma()
                        continue

                if services.get(sg.service_id.id, False):
                    services[sg.service_id.id]['qty'] += sg.period_for_invoice
                    services[sg.service_id.id]['net_amount'] += sg.amount_for_invoice
                else:
                    services[sg.service_id.id] = {
                        'qty': sg.period_for_invoice,
                        'descript': sg.service_id.get_product_name(),
                        'account': sg.service_id.account_id,
                        'net_amount': sg.amount_for_invoice,
                        'net_price': sg.amount,
                        'vat': sg.service_id.vat_id
                    }

            lines = []
            for k, v in iter(services.items()):
                vals = {
                    'net_amount': v['net_amount'],
                    'account_id': v['account'].id,
                    'descript': v['descript'],
                    'qty': '%d stuks' % v['qty'],
                    'net_price': v['net_price'],
                    'price_per': 'total',
                    'sale_id': subscriptions_grouped[0].sale_id.id
                }

                if subscriptions_grouped[0].partner_id.vat_sell_id:
                    vals['vat_id'] = subscriptions_grouped[0].partner_id.vat_sell_id.id
                    vals['vat_amount'] = subscriptions_grouped[0].partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = subscriptions_grouped[0].partner_id.vat_sell_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                else:
                    vals['vat_id'] = v['vat'].id
                    vals['vat_amount'] = v['vat'].calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = v['vat'].calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])

                lines.append((0, 0, vals))

            invdata = {
                'type': subscriptions_grouped[0].type,
                'partner_id': subscriptions_grouped[0].partner_id.id,
                'address_id': subscriptions_grouped[0].address_id.id if subscriptions_grouped[0].address_id else False,
                'contact_id': subscriptions_grouped[0].contact_id.id if subscriptions_grouped[0].contact_id else False,
                'line_ids': lines,
                'date_invoice': fields.Date.context_today(self),
                'date_financial': fields.Date.context_today(self),
            }

            invdata['reference'] = _('Subscription %s' % subscriptions_grouped[0].reference)

            if subscriptions_grouped[0].partner_id.payment_term_id:
                due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                due_date = due_date + datetime.timedelta(days=subscriptions_grouped[0].partner_id.payment_term_id.payment_terms)
                invdata['date_due'] = due_date.strftime('%Y-%m-%d')

            invoice = invoice_model.create(invdata)
            invoice.do_validate()
            for sg in subscriptions_grouped:
                if sg.state != 'active':
                    continue
                if not sg.current_period:
                    start_date = sg.date_start
                else:
                    start_date = sg.create_next_invoice
                add_periods = sg.period_for_invoice
                end_date = make_next_date(start_date, start_date, add_periods)
                sg.write({
                    'current_period': sg.current_period + add_periods,
                    'create_next_invoice': end_date
                })

                self.env['s2u.subscriptionv2.invoice'].create({
                    'subscription_id': sg.id,
                    'invoice_id': invoice.id
                })
            invoice_model += invoice

        return invoice_model

    @api.multi
    def create_rma(self):
        self.ensure_one()

        regs = self.env['s2u.warehouse.serialnumber'].search([('subscription_id', '=', self.id)])

        lines = []
        for reg in regs:
            if not reg.by_customer:
                continue
            lines.append((0, _, {
                'product_id': reg.product_id.id,
                'product_detail': reg.product_detail,
                'product_value': reg.todo_id.product_value,
                'qty': '1 stuks',
                'product_qty': 1.0,
                'todo_id': reg.todo_id.id,
                'serialnumber': reg.name
            }))

        if lines:
            rma_vals = {
                'entity_id': self.partner_id.id,
                'reference': '%s - %s' % (self.sale_id.name, self.reference),
                'line_ids': lines,
                'subscriptionv2_id': self.id
            }
            return self.env['s2u.warehouse.rma'].create(rma_vals)
        else:
            return False

    @api.multi
    def action_cancel(self):
        self.ensure_one()

        rma = self.create_rma()

        self.write({
            'state': 'cancel'
        })

    @api.multi
    def action_outgoing(self):

        outgoing_model = self.env['s2u.warehouse.outgoing']
        type_model = self.env['s2u.warehouse.outgoing.type']

        self.ensure_one()

        default_outgoing_type_id = type_model.search([('default', '=', True)])
        if not default_outgoing_type_id:
            raise UserError(_('Please define a default outgoing delivery type!'))
        default_outgoing_type_id = default_outgoing_type_id[0].id

        todos = []

        for p in self.service_id.product_ids:
            if not p.product_id.is_stockable():
                continue
            if self.saleline_id.price_per == 'item':
                product_value = self.saleline_id.price
            else:
                product_value = self.saleline_id.amount / self.saleline_id.product_qty
            v = {
                'sale_id': self.sale_id.id,
                'saleline_id': self.saleline_id.id,
                'product_id': p.product_id.id,
                'product_value': product_value,
                'product_qty': p.product_qty
            }

            if p.use_product_detail_so:
                if self.saleline_id.product_detail:
                    v['product_detail'] = self.saleline_id.product_detail
                else:
                    v['product_detail'] = p.product_detail
            else:
                v['product_detail'] = p.product_detail
            todos.append((0, 0, v))

        if todos:
            vals = {
                'type': self.sale_id.type,
                'entity_id': self.sale_id.partner_id.id,
                'contact_id': self.sale_id.contact_id.id if self.sale_id.contact_id else False,
                'delivery_type': self.sale_id.delivery_type,
                'delivery_entity_id': self.sale_id.delivery_partner_id.id,
                'delivery_contact_id': self.sale_id.delivery_contact_id.id if self.sale_id.delivery_contact_id else False,
                'delivery_address': self.sale_id.delivery_address,
                'project': self.sale_id.project,
                'reference': self.sale_id.reference,
                'customer_code': self.sale_id.customer_code,
                'outgoing_type_id': default_outgoing_type_id,
                'todo_ids': todos,
                'delivery_country_id': self.sale_id.delivery_country_id.id if self.sale_id.delivery_country_id else False,
                'delivery_tinno': self.sale_id.delivery_tinno,
                'subscriptionv2_id': self.id
            }
            outgoing_model.create(vals)

    @api.model
    def cron_create_invoices(self):
        """WARNING: meant for cron usage only - will commit() after each validation!"""

        def get_key(subscription):
            key = [
                str(subscription.sale_id.id),
                subscription.type,
                str(subscription.partner_id.id),
                str(subscription.contact_id.id) if subscription.contact_id and subscription.type == 'b2b' else '',
                str(subscription.address_id.id) if subscription.address_id and subscription.type == 'b2b' else '',
            ]

            return ','.join(key)

        subscriptions = self.env['s2u.subscriptionv2'].sudo()\
            .search([('state', '=', 'active'), ('create_next_invoice', '<=', fields.Date.context_today(self))])

        _logger.info('Start creating invoices for %d subscriptions ...', len(subscriptions))

        subscriptions_grouped = {}
        for subscription in subscriptions:
            if get_key(subscription) not in subscriptions_grouped:
                subscriptions_grouped[get_key(subscription)] = self.env['s2u.subscriptionv2']
            subscriptions_grouped[get_key(subscription)] += subscription

        for k, subscriptions in iter(subscriptions_grouped.items()):
            try:
                invoices = subscriptions.create_invoices()
                for invoice in invoices:
                    if self.env['ir.config_parameter'].sudo().get_param('s2usubscription.invoice_by_mail', 'False').lower() == 'true':
                        if invoice.use_email_address:
                            template = self.env['mail.template'].sudo().search([('model', '=', 's2u.account.invoice')])
                            if template:
                                template.send_mail(invoice.id, force_send=False)
                                _logger.info('Invoice with id#%d sent by mail', invoice.id)
                            else:
                                _logger.info('No mail template found for invoice by mail with id#%d. You need to send invoice manually!', invoice.id)
                                invoice.write({
                                    'alert_for_send': True
                                })
                        else:
                            _logger.info('No mail address present to use for invoice by mail with id#%d. You need to send invoice manually!', invoice.id)
                            invoice.write({
                                'alert_for_send': True
                            })
                    else:
                        _logger.info('s2usubscription.invoice_by_mail is disabled. You need to send invoices manually or set s2usubscription.invoice_by_mail = True!', invoice.id)
                        invoice.write({
                            'alert_for_send': True
                        })
                    self._cr.commit()
            except:
                self._cr.rollback()
                _logger.info('Failed to validate subscriptions: %s', subscriptions.ids, exc_info=True)
        _logger.info('Creating invoices for subscriptions finished.')
        return True


class Subscriptionv2Invoice(models.Model):
    _name = "s2u.subscriptionv2.invoice"

    subscription_id = fields.Many2one('s2u.subscriptionv2', string='Subscription', required=True, ondelete='cascade')
    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='cascade')


class SubscriptionTemplate(models.Model):
    _name = "s2u.subscription.template"
    _inherit = 's2u.baseproduct.abstract'
    _description = "Subscription Template"

    @api.multi
    def check_product_detail(self, detail, product_name=False):

        # product details mag voor alle waarden bevatten, geen speciale syntax noodzakelijk
        if not detail:
            return ''
        return detail

    @api.multi
    def get_so_account(self):

        self.ensure_one()
        if self.account_id:
            return self.account_id
        else:
            return super(SubscriptionTemplate, self).get_so_account()

    @api.multi
    def get_so_vat(self):

        self.ensure_one()
        if self.vat_id:
            return self.vat_id
        else:
            return super(SubscriptionTemplate, self).get_so_vat()

    @api.multi
    def get_po_account(self, supplier=False):

        self.ensure_one()
        return super(SubscriptionTemplate, self).get_po_account(supplier=supplier)

    @api.multi
    def get_po_vat(self, supplier=False):

        self.ensure_one()
        return super(SubscriptionTemplate, self).get_po_vat(supplier=supplier)

    @api.multi
    def get_product_price(self, qty, details, ctx=False):
        """"Inherited from base product"""

        if not (isinstance(qty, int) or isinstance(qty, float)):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(qty)
        if not qty:
            return False

        if ctx and ctx.get('customer_id'):
            discount = self.env['s2u.crm.entity.discount.subscription'].search([('entity_id', '=', ctx['customer_id']),
                                                                                ('subscription_id', '=', self.id)], limit=1)
            if discount:
                if discount.discount_type == 'percent':
                    res = {
                        'price': self.price * self.months,
                        'price_per': 'item',
                        'total_amount': qty * self.price * self.months,
                        'discount': discount.discount
                    }
                    return res
                else:
                    res = {
                        'price': discount.discount * self.months,
                        'price_per': 'item',
                        'total_amount': qty * discount.discount * self.months,
                        'discount': 0.0
                    }
                    return res

        res = {
            'price': self.price * self.months,
            'price_per': 'item',
            'total_amount': qty * self.price * self.months,
            'discount': 0.0
        }

        return res

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.one
    @api.depends('price', 'price_is_net', 'vat_id')
    def _compute_gross_amount(self):
        if self.price_is_net:
            self.price_netto = self.price
            self.price_gross = self.price + self.vat_id.calc_vat_from_netto_amount(self.price)
        else:
            if self.vat_id:
                self.price_netto = self.price - self.vat_id.calc_vat_from_gross_amount(self.price)
            else:
                self.price_netto = self.price
            self.price_gross = self.price

    @api.multi
    def get_duration(self):

        self.ensure_one()
        if self.period_unit == 'month':
            if self.months == 1:
                return _('1 month')
            else:
                return '%d %s' % (self.months, _('months'))
        if self.period_unit == 'year':
            if self.months == 1:
                return _('1 year')
            else:
                return '%d %s' % (self.months, _('years'))
        return ''

    @api.multi
    def get_unit(self):

        self.ensure_one()
        if self.period_unit == 'month':
            return _('per month')
        if self.period_unit == 'year':
            return _('per year')
        return ''

    def _get_discount_count(self):

        for product in self:
            discounts = self.env['s2u.crm.entity.discount.subscription'].search([('subscription_id', '=', product.id)])
            product.discount_count = len(discounts)

    @api.multi
    def action_view_discount(self):
        discounts = self.env['s2u.crm.entity.discount.subscription'].search([('subscription_id', '=', self.id)])

        action = self.env.ref('s2usubscription.action_sale_subscription_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_subscription_id': self.id
        }
        action['context'] = str(context)
        return action

    @api.multi
    def get_product_name(self):

        name = []
        if self.ec:
            name.append(self.ec)
        if self.name:
            name.append(self.name)
        if self.label_for_service:
            name.append(self.label_for_service)
        if self.period_unit == 'month':
            name.append('%dmnd' % self.months)
        elif self.period_unit == 'year':
            name.append('%djr' % self.months)
        return '-'.join(name)

    @api.multi
    @api.depends('ec', 'label_for_service', 'name', 'months', 'period_unit')
    def name_get(self):
        result = []
        for service in self:
            result.append((service.id, service.get_product_name()))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', ('ec', '=ilike', name + '%'), ('label_for_service', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        services = self.search(domain + args, limit=limit)
        return services.name_get()

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(ec=_("COPY"))
        source_id = self.id
        new_record = super(SubscriptionTemplate, self).copy(default)

        discounts = self.env['s2u.crm.entity.discount.subscription'].search([('subscription_id', '=', source_id)])
        for discount in discounts:
            discount.copy(default={
                'subscription_id': new_record.id
            })

        return new_record

    @api.multi
    def write(self, vals):

        for sub in self:
            ec = vals.get('ec', self.ec)
            name = vals.get('name', self.name)
            label_for_service = vals.get('label_for_service', self.label_for_service)
            months = vals.get('months', self.months)

            exists = self.env['s2u.subscription.template'].search([('ec', '=', ec),
                                                                   ('name', '=', name),
                                                                   ('label_for_service', '=', label_for_service),
                                                                   ('months', '=', months),
                                                                   ('id', '!=', sub.id)])
            if exists:
                raise UserError(_('Service name already exists!'))

        return super(SubscriptionTemplate, self).write(vals)

    @api.model
    def create(self, vals):

        ec = vals.get('ec', False)
        name = vals.get('name', False)
        label_for_service = vals.get('label_for_service', False)
        months = vals.get('months', False)

        exists = self.env['s2u.subscription.template'].search([('ec', '=', ec),
                                                               ('name', '=', name),
                                                               ('label_for_service', '=', label_for_service),
                                                               ('months', '=', months)])
        if exists:
            raise UserError(_('Service name already exists!'))

        return super(SubscriptionTemplate, self).create(vals)

    @api.one
    @api.depends('product_ids', 'months', 'surcharge', 'interest', 'margin', 'writeoff_periods')
    def _compute_cost_price(self):
        try:
            tot_purchase = 0.0
            for product in self.product_ids:
                tot_purchase += product.product_qty * product.price
            interest = self.interest / 100.0
            surcharge = (self.surcharge / 100.0) + 1.0
            margin = (self.margin / 100.0) + 1.0

            costs = ((interest / 12) / (1 - (math.pow((1 + (interest / 12)), -1.0 * self.writeoff_periods)))) * tot_purchase
            self.cost_price = round((costs * surcharge) * margin, 2)
        except:
            self.cost_price = 0.0

    @api.onchange('ec')
    def onchange_ec(self):
        if self.ec:
            self.ec = self.ec.upper()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id and self.partner_id.entity_code:
            self.ec = self.partner_id.entity_code

    ec = fields.Char(string='Service code', required=True, index=True, size=5,
                     help='Use this field to mark this service entity specific.')
    label_for_service = fields.Char(string='Label', readonly=True, related='projecttype_id.label_for_service',
                                    store=True, index=True)
    name = fields.Char(string='Name', index=True, required=False)
    code = fields.Char(index=True, string='Code')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    months = fields.Integer(string='Duration', default=12, required=True)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    price = fields.Monetary(string='Amount unit', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    vat_id = fields.Many2one('s2u.account.vat', string='Vat', required=True, domain=[('type', '=', 'sell')])
    product_ids = fields.One2many('s2u.subscription.template.product', 'template_id',
                                  string='Products', copy=True)
    product_type = fields.Selection(default='service')
    price_is_net = fields.Boolean(string='Price is netto', default=True)
    price_gross = fields.Monetary(string='Gross', currency_field='currency_id',
                                  store=True, readonly=True, compute='_compute_gross_amount')
    price_netto = fields.Monetary(string='Netto', currency_field='currency_id',
                                  readonly=True, compute='_compute_gross_amount')
    create_project = fields.Boolean(string='Create project', default=True)
    create_project_criteria = fields.Selection([
        ('no', 'No'),
        ('always', 'Always'),
        ('exists', 'Only if not exists')
    ], required=True, default='exists', string='Create project')
    projecttype_id = fields.Many2one('s2u.project.type', string='Project type', ondelete='set null')
    period_unit = fields.Selection([
        ('month', 'Month'),
        ('year', 'Year'),
    ], required=True, default='month', string='Unit')
    subs_descript = fields.Text(string='Description')
    discount_count = fields.Integer(string='# of Discounts', compute='_get_discount_count', readonly=True)
    action_on_end = fields.Selection([
        ('stop', 'Stop subscription'),
        ('extend', 'Exten subscription')
    ], required=True, default='stop', string='Action on end')
    cost_price = fields.Monetary(string='Cost price', currency_field='currency_id',
                                 readonly=True, compute='_compute_cost_price')
    surcharge = fields.Float(string='Surcharge (%)', default=40.0)
    margin = fields.Float(string='Margin (%)', default=20.0)
    interest = fields.Float(string='Interest (%)', default=5.0)
    writeoff_periods = fields.Integer(string='Periods for writeoff', default=0)
    invoice_condition = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half-yearly', 'Half-yearly'),
        ('yearly', 'Yearly'),
    ], required=True, default='monthly', string='Invoicing')
    partner_id = fields.Many2one('s2u.crm.entity', string='Entity', index=True, ondelete='set null')
    stock_account_id = fields.Many2one('s2u.account.account', string='Stock Account for deliveries',
                                       domain=[('type', 'in', ['stock'])], ondelete='restrict')


class SubscriptionTemplateProduct(models.Model):
    _name = "s2u.subscription.template.product"
    _inherit = "s2u.baseproduct.transaction.abstract"

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SubscriptionTemplateProduct, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(SubscriptionTemplateProduct, self).write(vals)

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            if self.product_id.res_model != 's2u.sale.product':
                return
            po_prices = self.env['s2u.sale.product.purchase'].search([('product_id', '=', self.product_id.res_id)],
                                                                     order='po_price')
            if po_prices:
                self.price = po_prices[0].po_price

    template_id = fields.Many2one('s2u.subscription.template', string='Template', required=True, ondelete='cascade')
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
    use_product_detail_so = fields.Boolean(string='Use details SO', default=False)
    currency_id = fields.Many2one('res.currency', related='template_id.currency_id', store=True)
    price = fields.Monetary(string='Item price', currency_field='currency_id', required=True, default=0.0)


class Subscription(models.Model):
    _name = "s2u.subscription"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Subscription"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Subscription, self)._track_subtype(init_values)

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for s in self:
            if s.type == 'b2b':
                if s.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b debitor!'))
                if s.contact_id and s.contact_id.entity_id != s.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if s.address_id and s.address_id.entity_id != s.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if s.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.partner_id:
            delivery = self.partner_id.prepare_delivery()
            self.delivery_address = delivery

            if self.partner_id.type == 'b2b':
                address = self.partner_id.get_physical()
                if address and address.country_id:
                    self.delivery_country_id = address.country_id
                else:
                    self.delivery_country_id = False

                if self.partner_id.tinno:
                    self.delivery_tinno = self.partner_id.tinno
                else:
                    self.delivery_tinno = False
            else:
                if self.partner_id.country_id:
                    self.delivery_country_id = self.partner_id.country_id
                else:
                    self.delivery_country_id = False
                self.delivery_tinno = False

            if self.partner_id.lang:
                self.delivery_lang = self.partner_id.lang
            else:
                self.delivery_lang = False

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            delivery = self.contact_id.display_company + '\n'
            if self.contact_id.prefix:
                delivery += '%s\n' % self.contact_id.prefix
            else:
                delivery += '%s\n' % self.contact_id.name
            if self.contact_id.address_id:
                if self.contact_id.address_id.address:
                    delivery += '%s\n' % self.contact_id.address_id.address
                if self.contact_id.address_id.zip and self.contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.contact_id.address_id.zip, self.contact_id.address_id.city)
                elif self.contact_id.address_id.city:
                    delivery += '%s\n' % self.contact_id.address_id.city
                if self.contact_id.address_id.country_id:
                    delivery += '%s\n' % self.contact_id.address_id.country_id.name
            elif self.partner_id:
                address = self.partner_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    elif address.city:
                        delivery += '%s\n' % address.city
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.model
    def _default_delivery_country(self):
        domain = [
            ('code', '=', 'NL'),
        ]
        return self.env['res.country'].search(domain, limit=1)

    @api.model
    def _delivery_lang_get(self):
        languages = self.env['res.lang'].search([])
        return [(language.code, language.name) for language in languages]

    @api.one
    @api.depends('period_ids.state')
    def _compute_amount(self):
        self.amount_paid = sum(p.amount for p in self.period_ids if p.state == 'paid')
        self.amount_open = sum(p.amount for p in self.period_ids if p.state == 'open')

    @api.one
    @api.depends('order_ids.date_end', 'order_ids.state', 'state')
    def _compute_notify(self):

        if self.state == 'active':
            date_notify = False
            for service in self.order_ids:
                if service.state == 'cancel':
                    continue
                if not service.date_end:
                    continue
                if not date_notify or service.date_end > date_notify:
                    date_notify = service.date_end
            if date_notify:
                date_notify = datetime.datetime.strptime(date_notify, "%Y-%m-%d")
                date_notify = date_notify - datetime.timedelta(days=45)
                self.date_notify = date_notify.strftime('%Y-%m-%d')
            else:
                self.date_notify = date_notify
        else:
            self.date_notify = False

    def _get_period_count(self):

        for subscription in self:
            period_ids = [p.id for p in subscription.period_ids if p.state != 'cancel']
            subscription.period_count = len(period_ids)

    @api.multi
    def action_view_period(self):
        period_ids = [p.id for p in self.period_ids if p.state != 'cancel']

        action = self.env.ref('s2usubscription.action_subscription_period').read()[0]
        if len(period_ids) > 1:
            action['domain'] = [('id', 'in', period_ids)]
        elif len(period_ids) == 1:
            action['views'] = [(self.env.ref('s2usubscription.subscription_period_form').id, 'form')]
            action['res_id'] = period_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_rma_count(self):

        for subscription in self:
            rmas = self.env['s2u.warehouse.rma'].search([('subscription_id', '=', subscription.id)])
            subscription.rma_count = len(rmas)

    @api.multi
    def action_view_rma(self):
        rmas = self.env['s2u.warehouse.rma'].search([('subscription_id', '=', self.id)])

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rmas) > 1:
            action['domain'] = [('id', 'in', rmas.ids)]
        elif len(rmas) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_rma_form').id, 'form')]
            action['res_id'] = rmas.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_increase(self):
        self.ensure_one()
        wiz_form = self.env.ref('s2usubscription.wizard_action_increase_view', False)
        ctx = dict(
            default_model='s2u.subscription',
            default_res_id=self.id,
        )
        return {
            'name': _('Extend/add services'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2usubscription.action.increase',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.one
    def unlink(self):

        for subscription in self:
            if subscription.state not in ['draft', 'active']:
                raise ValidationError(_('You can not delete a confirmed subscription!'))

        res = super(Subscription, self).unlink()

        return res

    _subscription_state = {
        'draft': [('readonly', False)],
    }

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_subscription_state)
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor', required=True, index=True,
                                 readonly=True, states=_subscription_state)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True, readonly=True,
                                 states=_subscription_state)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, readonly=True,
                                 states=_subscription_state)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', track_visibility='onchange')
    date = fields.Date(string='Date', index=True, copy=False, readonly=True, states=_subscription_state,
                       default=lambda self: fields.Date.context_today(self))
    currency_id = fields.Many2one('res.currency', string='Currency', related='company_id.currency_id')
    amount_total = fields.Monetary(string='Amount Total', currency_field='currency_id')
    amount_paid = fields.Monetary(string='Amount Paid',
                                  store=True, readonly=True, compute='_compute_amount')
    amount_open = fields.Monetary(string='Amount Open',
                                  store=True, readonly=True, compute='_compute_amount')
    payment_type = fields.Selection([
        ('transfer', 'Rekening'),
        ('incasso', 'Incasso')
    ], required=True, default='transfer', string='Payment type', readonly=True, states=_subscription_state)
    payment_key = fields.Char(string='Payment key', readonly=True, states=_subscription_state)
    product_ids = fields.One2many('s2u.subscription.product', 'subscription_id',
                                  string='Products', copy=False)
    order_ids = fields.One2many('s2u.subscription.order', 'subscription_id',
                                string='Services', copy=True, readonly=True, states=_subscription_state)
    period_ids = fields.One2many('s2u.subscription.period', 'subscription_id',
                                string='Periods', copy=False)
    sale_id = fields.Many2one('s2u.sale', string='SO', required=True, index=True,
                              readonly=True, states=_subscription_state, ondelete='restrict')
    date_notify = fields.Date(string='Notify', index=True, store=True, compute='_compute_notify', readonly=True)
    period_count = fields.Integer(string='# of Periods', compute='_get_period_count', readonly=True)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)


    @api.multi
    def action_activate(self):

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

        self.ensure_one()

        periods = {}
        first_period = False

        if self.state != 'draft':
            return False

        for order in self.order_ids:
            start_date = fields.Date.context_today(self)
            if order.product_detail and order.product_detail.startswith('start:'):
                start_date = order.product_detail.replace('start:', '').strip()
                start_date = start_date.split('-')
                start_date = '%04d-%02d-%02d' % (int(start_date[2]), int(start_date[1]), int(start_date[0]))
                datetime.datetime.strptime(start_date, '%Y-%m-%d')
                if start_date < fields.Date.context_today(self):
                    raise ValueError(_('Please select a start date for the service in the future!'))

            next_date = start_date
            for i in range(order.template_id.months):
                if periods.get(next_date, False):
                    period = periods[next_date]
                else:
                    period = self.env['s2u.subscription.period'].create({
                        'subscription_id': self.id,
                        'type': self.type,
                        'partner_id': self.partner_id.id,
                        'contact_id': self.contact_id.id if self.contact_id else False,
                        'address_id': self.address_id.id if self.address_id else False,
                        'date': next_date,
                    })
                    periods[next_date] = period

                trans = self.env['s2u.subscription.period.transaction'].create({
                    'period_id': period.id,
                    'template_id': order.template_id.id,
                    'order_id': order.id,
                    'product_detail': order.product_detail,
                    'amount': order.template_id.price,
                    'reference': self.sale_id.name
                })

                if self.payment_type == 'transfer' and not first_period:
                    first_period = period
                next_date = make_next_date(start_date, next_date, order.template_id.period_unit)
            order.write({
                'date_start': start_date,
                'date_end': next_date
            })

        if first_period:
            invoice = first_period.create_invoice()

        self.order_ids.write({
            'state': 'active'
        })

        self.write({
            'state': 'active'
        })


class SubscriptionPeriod(models.Model):
    _name = "s2u.subscription.period"
    _order = 'date'

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.one
    @api.depends('date', 'invoice_id', 'invoice_id.amount_open')
    def _compute_state(self):

        if not self.invoice_id:
            self.state = 'pending'
        elif self.invoice_id.amount_open <= 0.0:
            self.state = 'paid'
        else:
            self.state = 'open'

    @api.one
    @api.depends('transaction_ids')
    def _compute_amount(self):

        self.amount = sum(t.amount for t in self.transaction_ids if not t.is_canceled)

    @api.one
    @api.depends('date')
    def _compute_payment_month(self):
        if not self.date:
            self.month_payment = False
        else:
            paydat = datetime.datetime.strptime(self.date, '%Y-%m-%d')
            self.month_payment = "%02d (%s)" % (paydat.month, paydat.strftime("%B"))

    @api.one
    @api.depends('date')
    def _compute_payment_year(self):
        if not self.date:
            self.year_payment = False
        else:
            paydat = datetime.datetime.strptime(self.date, '%Y-%m-%d')
            self.year_payment = paydat.strftime("%Y")

    subscription_id = fields.Many2one('s2u.subscription', string='Subscription', required=True, ondelete='cascade')
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True)
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor', required=True, index=True)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True)
    date = fields.Date(string='Date', index=True, copy=False, default=lambda self: fields.Date.context_today(self))
    state = fields.Selection([
        ('pending', 'Pending'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('cancel', 'Canceled'),
    ], string='State', store=True, readonly=True, compute='_compute_state')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', compute='_compute_amount', readonly=True)
    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice')
    year_payment = fields.Char(string='Payment Year',
                               store=True, readonly=True, compute='_compute_payment_year')
    month_payment = fields.Char(string='Payment Month',
                                store=True, readonly=True, compute='_compute_payment_month')
    transaction_ids = fields.One2many('s2u.subscription.period.transaction', 'period_id',
                                      string='Transactions', copy=False)


    @api.multi
    def create_invoice(self):

        invoice_model = self.env['s2u.account.invoice']

        self.ensure_one()

        subscriptions = {}
        for t in self.transaction_ids:
            if subscriptions.get(t.template_id.id, False):
                subscriptions[t.template_id.id]['qty'] += 1
                subscriptions[t.template_id.id]['net_amount'] += t.amount
            else:
                subscriptions[t.template_id.id] = {
                    'qty': 1,
                    'descript': t.template_id.name,
                    'account': t.template_id.account_id,
                    'net_amount': t.amount,
                    'net_price': t.amount,
                    'vat': t.template_id.vat_id
                }

        lines = []

        for k, v in iter(subscriptions.items()):
            vals = {
                'net_amount': v['net_amount'],
                'account_id': v['account'].id,
                'descript': v['descript'],
                'qty': '%d x' % v['qty'],
                'net_price': v['net_price'],
                'price_per': 'total',
                'sale_id': self.subscription_id.sale_id.id
            }

            if self.partner_id.vat_sell_id:
                vals['vat_id'] = self.partner_id.vat_sell_id.id
                vals['vat_amount'] = self.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                    vals['net_amount'])
                vals['gross_amount'] = self.partner_id.vat_sell_id.calc_gross_amount(
                    vals['net_amount'], vals['vat_amount'])
            else:
                vals['vat_id'] = v['vat'].id
                vals['vat_amount'] = v['vat'].calc_vat_from_netto_amount(
                    vals['net_amount'])
                vals['gross_amount'] = v['vat'].calc_gross_amount(
                    vals['net_amount'], vals['vat_amount'])

            lines.append((0, 0, vals))

        invdata = {
            'type': self.type,
            'partner_id': self.partner_id.id,
            'address_id': self.address_id.id if self.address_id else False,
            'contact_id': self.contact_id.id if self.contact_id else False,
            'line_ids': lines,
            'date_invoice': fields.Date.context_today(self),
            'date_financial': fields.Date.context_today(self),
        }

        if self.year_payment and self.month_payment:
            invdata['reference'] = _('Period:') + ' %s/%s' % (self.year_payment, self.month_payment)

        if self.partner_id.payment_term_id:
            due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
            due_date = due_date + datetime.timedelta(days=self.partner_id.payment_term_id.payment_terms)
            invdata['date_due'] = due_date.strftime('%Y-%m-%d')

        invoice = invoice_model.create(invdata)
        self.write({
            'invoice_id': invoice.id
        })
        invoice.do_validate()
        return invoice

    @api.multi
    def action_create_invoice(self):

        self.ensure_one()

        invoice = self.create_invoice()

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uaccount.action_invoice')
        list_view_id = imd.xmlid_to_res_id('s2uaccount.invoice_tree')
        form_view_id = imd.xmlid_to_res_id('s2uaccount.invoice_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
            'views': [(form_view_id, 'form')],
            'res_id': invoice.id
        }
        return result

    @api.model
    def cron_validate_periods(self):
        """WARNING: meant for cron usage only - will commit() after each validation!"""

        # break method, not used anymore
        return True

        periods = self.env['s2u.subscription.period'].sudo().search([('state', '=', 'pending'),
                                                                     ('date', '<=', fields.Date.context_today(self))])
        _logger.info('Start validating subscription periods for %d records ...', len(periods))
        for period in periods:
            try:
                invoice = period.create_invoice()
                if invoice.use_email_address:
                    template = self.env['mail.template'].sudo().search([('model', '=', 's2u.account.invoice')])
                    if template:
                        template.send_mail(invoice.id, force_send=False)
                    else:
                        _logger.info('No mail template found for invoicing period by mail with id#%d. You need to send invoice manually!', period.id)
                        invoice.write({
                            'alert_for_send': True
                        })
                else:
                    _logger.info('No mail address present to use for invoicing period by mail with id#%d. You need to send invoice manually!', period.id)
                    invoice.write({
                        'alert_for_send': True
                    })
                self._cr.commit()
            except:
                self._cr.rollback()
                _logger.info('Failed to validate period with id#%d.', period.id, exc_info=True)
        _logger.info('Validating subscription periods finished.')
        return True


class SubscriptionPeriodTransaction(models.Model):
    _name = "s2u.subscription.period.transaction"

    period_id = fields.Many2one('s2u.subscription.period', string='Period', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency', related='period_id.currency_id')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    template_id = fields.Many2one('s2u.subscription.template', string='Subscription', required=True)
    product_detail = fields.Char(string='Version')
    company_id = fields.Many2one('res.company', string='Company', required=True, related='period_id.company_id')
    reference = fields.Char(string='Reference')
    order_id = fields.Many2one('s2u.subscription.order', string='Order')
    is_canceled = fields.Boolean(string='Canceled')


class SubscriptionOrder(models.Model):
    _name = "s2u.subscription.order"

    @api.multi
    def name_get(self):
        result = []
        for so in self:
            if so.product_detail:
                name = '%s (%s)' % (so.template_id.name, so.product_detail)
            else:
                name = so.template_id.name
            result.append((so.id, name))
        return result

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    subscription_id = fields.Many2one('s2u.subscription', string='Subscription', required=True, ondelete='cascade')
    template_id = fields.Many2one('s2u.subscription.template', string='Service', required=True)
    product_detail = fields.Char(string='Version')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', related='template_id.currency_id')
    amount = fields.Monetary(string='Amount (monthly)')
    months = fields.Integer(string='Duration (months)', related='template_id.months')
    state = fields.Selection([
        ('draft', 'Concept'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State')
    date_start = fields.Date(string='Start', index=True, copy=False)
    date_end = fields.Date(string='Ends', index=True, copy=False)
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor', readonly=True, related='subscription_id.partner_id')
    is_extended = fields.Boolean('Is extended', default=False)

    @api.multi
    def action_cancel(self):
        self.ensure_one()

        self.write({
            'state': 'cancel'
        })

        transactions = self.env['s2u.subscription.period.transaction'].search([('order_id', '=', self.id)])
        for t in transactions:
            if t.period_id.state == 'pending':
                t.write({
                    'is_canceled': True
                })

        periods = self.env['s2u.subscription.period'].search([('subscription_id', '=', self.subscription_id.id),
                                                              ('state', '=', 'pending')])
        for p in periods:
            transactions = self.env['s2u.subscription.period.transaction'].search([('period_id', '=', p.id),
                                                                                   ('is_canceled', '=', False)])
            if not transactions:
                p.write({
                    'state': 'cancel'
                })

        orders = self.env['s2u.subscription.order'].search([('subscription_id', '=', self.subscription_id.id),
                                                            ('state', '!=', 'cancel')])
        if not orders:
            if self.subscription_id.sale_id:
                todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', self.subscription_id.sale_id.id)])
                outgoing_ids = [l.outgoing_id.id for l in todolines]
                outgoing_ids = list(set(outgoing_ids))
                for outgoing in self.env['s2u.warehouse.outgoing'].browse(outgoing_ids):
                    rma = outgoing.do_rma()
                    rma.write({
                        'subscription_id': self.subscription_id.id
                    })

            self.subscription_id.write({
                'state': 'cancel'
            })

class SubscriptionProduct(models.Model):
    _name = "s2u.subscription.product"

    @api.multi
    @api.depends('product_id', 'product_detail', 'product_ref')
    def name_get(self):
        result = []
        for p in self:
            if p.product_id and p.product_detail and p.product_ref:
                name = '%s %s (%s)' % (p.product_id.name, p.product_detail, p.product_ref)
            elif p.product_id and p.product_detail:
                name = '%s %s' % (p.product_id.name, p.product_detail)
            elif p.product_id and p.product_ref:
                name = '%s (%s)' % (p.product_id.name, p.product_ref)
            else:
                name = '%s' % (p.product_id.name)

            result.append((p.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = [('product_ref', '=ilike', name + '%')]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        products = self.search(domain + args, limit=limit)
        return products.name_get()

    subscription_id = fields.Many2one('s2u.subscription', string='Subscription', required=True, ondelete='cascade')
    template_id = fields.Many2one('s2u.subscription.template', string='Template', required=True, ondelete='restrict')
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True, index=True)
    product_detail = fields.Char(string='Details')
    product_ref = fields.Char(string='Ref.', copy=False, index=True)


class SubscriptionBlock(models.Model):
    _name = "s2u.subscription.block"
    _order = "name"

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    name = fields.Char(string='Name', index=True, required=True)
    description = fields.Html(string='Description')
    short_descript = fields.Char(string='Short descript.', required=True)

