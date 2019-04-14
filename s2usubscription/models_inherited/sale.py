# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class SaleTemplate(models.Model):
    _inherit = "s2u.sale.template"

    @api.multi
    def render_template(self, template, entity=False, address=False, contact=False, user=False, date=False,
                        other=False):

        template = super(SaleTemplate, self).render_template(template, entity=entity, address=address, contact=contact,
                                                             user=user, date=date, other=other)
        if template and entity and entity.invoice_condition:
            if entity.invoice_condition == 'monthly':
                template = template.replace('[[service_condition]]', _('Maandelijks'))
            if entity.invoice_condition == 'quarterly':
                template = template.replace('[[service_condition]]', _('Kwartaal'))
            if entity.invoice_condition == 'half-yearly':
                template = template.replace('[[service_condition]]', _('Halfjaarlijks'))
            if entity.invoice_condition == 'yearly':
                template = template.replace('[[service_condition]]', _('Jaarlijks'))

        if template:
            template = template.replace('[[service_condition]]', '')

        return template


class SaleLine(models.Model):
    _inherit = "s2u.sale.line"

    @api.one
    def _compute_subscription_per_month(self):

        self.subscription_price_month = 0.0
        self.subscription_total_month = 0.0
        if self.product_id:
            if self.product_id.res_model == 's2u.subscription.template':
                if self.product_id.fetch_object().period_unit == 'month':
                    duration = self.product_id.fetch_object().months
                else:
                    duration = self.product_id.fetch_object().months * 12
                self.subscription_price_month = round(self.amount / self.product_qty / float(duration), 2)
                self.subscription_total_month = round(self.amount / float(duration), 2)

    subscription_price_month = fields.Monetary(string='Subscription price/month', currency_field='currency_id',
                                               compute=_compute_subscription_per_month, readonly=True)
    subscription_total_month = fields.Monetary(string='Subscription total/month', currency_field='currency_id',
                                               compute=_compute_subscription_per_month, readonly=True)


class SaleSubscriptionBlock(models.Model):
    _name = "s2u.sale.subscription.block"
    _order = 'sequence'

    sale_id = fields.Many2one('sale.order', string='Sale', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    block_id = fields.Many2one('s2u.subscription.block', string='Block', required=True, ondelete='restrict')

class Sale(models.Model):
    _inherit = "s2u.sale"

    def _get_subscription_count(self):

        for sale in self:
            subscriptions = self.env['s2u.subscription'].search([('sale_id', '=', sale.id)])
            subscription_ids = [s.id for s in subscriptions]
            subscription_ids = list(set(subscription_ids))
            sale.subscription_count = len(subscription_ids)

    def _get_subscriptionv2_count(self):

        for sale in self:
            subscriptions = self.env['s2u.subscriptionv2'].search([('sale_id', '=', sale.id)])
            sale.subscriptionv2_count = len(subscriptions)

    def _lines_with(self):

        for sale in self:
            sale.lines_with_products = False
            sale.lines_with_subscriptions = False
            sale.ordered_with_products = False
            sale.ordered_with_subscriptions = False
            for line in sale.line_ids:
                if line.product_id.res_model != 's2u.subscription.template':
                    sale.lines_with_products = True
                if line.for_order and line.product_id.res_model != 's2u.subscription.template':
                    sale.ordered_with_products = True
                if line.product_id.res_model == 's2u.subscription.template':
                    sale.lines_with_subscriptions = True
                if line.for_order and line.product_id.res_model == 's2u.subscription.template':
                    sale.ordered_with_subscriptions = True

    @api.multi
    def action_view_subscription(self):
        subscriptions = self.env['s2u.subscription'].search([('sale_id', '=', self.id)])
        subscription_ids = [s.id for s in subscriptions]
        subscription_ids = list(set(subscription_ids))

        action = self.env.ref('s2usubscription.action_subscription').read()[0]
        if len(subscription_ids) > 1:
            action['domain'] = [('id', 'in', subscription_ids)]
        elif len(subscription_ids) == 1:
            action['views'] = [(self.env.ref('s2usubscription.subscription_form').id, 'form')]
            action['res_id'] = subscription_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_view_subscriptionv2(self):
        subscriptions = self.env['s2u.subscriptionv2'].search([('sale_id', '=', self.id)])

        action = self.env.ref('s2usubscription.action_subscriptionv2').read()[0]
        if len(subscriptions) >= 1:
            action['domain'] = [('id', 'in', subscriptions.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def skip_for_invoice(self, line):

        if line.product_id and line.product_id.res_model == 's2u.subscription.template':
            return True
        return super(Sale, self).skip_for_invoice(line)

    @api.multi
    def add_outgoing_line(self, line, devider):

        if line.product_id.res_model == 's2u.subscription.template':
            service = self.env['s2u.subscription.template'].browse(line.product_id.res_id)
            if not service.product_ids:
                return False
            vals = []
            for p in service.product_ids:
                if not p.product_id.is_stockable():
                    continue
                if line.price_per == 'item':
                    product_value = line.price
                else:
                    product_value = line.amount / line.product_qty
                v = {
                    'sale_id': self.id,
                    'saleline_id': line.id,
                    'product_id': p.product_id.id,
                    'product_value': product_value
                }
                if devider > 1:
                    # wordt gebruikt als er meerdere adressen zijn om te leveren, b.v. 2 adressen is 50/50 verdelen
                    v['product_qty'] = round(line.product_qty / float(devider), 0)
                else:
                    v['product_qty'] = line.product_qty
                if p.use_product_detail_so:
                    if line.product_detail:
                        v['product_detail'] = line.product_detail
                    else:
                        v['product_detail'] = p.product_detail
                else:
                    v['product_detail'] = p.product_detail
                vals.append(v)
            return vals

        return super(Sale, self).add_outgoing_line(line, devider)

    @api.multi
    def do_undo_other_stuff(self):

        self.ensure_one()

        subscriptions = self.env['s2u.subscriptionv2'].search([('sale_id', '=', self.id)])
        subscriptions.unlink()

        return True

    @api.multi
    def create_project_for_service(self, projecttype_id):
        self.ensure_one()

        projecttype = self.env['s2u.project.type'].browse(projecttype_id)
        rates = []
        for stage in projecttype.stage_ids:
            if not stage.rate_ids:
                continue
            for rate in stage.rate_ids:
                partner_rate = False
                if self.partner_id:
                    partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                        search([('rate_id', '=', rate.rate_id.id),
                                ('partner_id', '=', self.partner_id.id)], limit=1)
                if partner_rate:
                    if partner_rate.discount_type == 'price':
                        rate_per_hour = partner_rate.rate_per_hour
                    else:
                        rate_per_hour = round(rate.rate_id.rate_per_hour - (rate.rate_id.rate_per_hour * (partner_rate.rate_per_hour / 100.0)), 2)
                else:
                    rate_per_hour = rate.rate_id.rate_per_hour
                vals = {
                    'stage_id': stage.stage_id.id,
                    'rate_id': rate.rate_id.id,
                    'hours': rate.hours,
                    'amount': rate.hours * rate_per_hour,
                    'rate_per_hour': rate_per_hour,
                    'descript': rate.descript
                }
                rates.append((0, 0, vals))
        short_descript = '%s - %s' % (self.reference, projecttype.name)
        project_vals = {
            'short_descript': short_descript,
            'customer_code': self.customer_code,
            'reference': self.name,
            'partner_id': self.partner_id.id,
            'rate_ids': rates,
            # skip_invoicing in this case always true, it's an internal project
            'skip_invoicing': True,
            'projecttype_id': projecttype_id,
            'sale_id': self.id
        }
        if self.partner_id.use_project_zones:
            project_vals['zone1'] = self.partner_id.project_zone1
            project_vals['zone2'] = self.partner_id.project_zone2
            project_vals['zone3'] = self.partner_id.project_zone3
            project_vals['zone4'] = self.partner_id.project_zone4

        return self.env['s2u.project'].create(project_vals)

    @api.multi
    def before_confirm(self):
        self.ensure_one()

        create_project_always = []
        create_project_exists = []

        for line in self.line_ids:
            if not (line.product_id and line.product_id.res_model == 's2u.subscription.template'):
                continue
            service = self.env['s2u.subscription.template'].browse(line.product_id.res_id)
            for qty in line.qty_ids:
                if not qty.for_order:
                    continue
                amount = round(line.amount / qty.product_qty / service.months, 2)
                for n in range(int(qty.product_qty)):
                    vals = {
                        'type': self.type,
                        'partner_id': self.partner_id.id,
                        'contact_id': self.contact_id.id if self.contact_id else False,
                        'address_id': self.address_id.id if self.address_id else False,
                        'saleline_id': line.id,
                        'service_id': service.id,
                        'product_detail': line.product_detail,
                        'amount': amount,
                        'periods': service.months,
                        'period_unit': service.period_unit,
                        'action_on_end': service.action_on_end,
                        'invoice_condition': self.partner_id.invoice_condition if self.partner_id.invoice_condition else service.invoice_condition
                    }
                    self.env['s2u.subscriptionv2'].create(vals)
            # we need to check if we have to create a project for the ordered services
            if service.create_project_criteria == 'always':
                create_project_always.append(service.projecttype_id.id)
            elif service.create_project_criteria == 'exists':
                create_project_exists.append(service.projecttype_id.id)

        if create_project_exists:
            # remove doubles - make 1 project for it
            create_project = list(set(create_project_exists))
            for projecttype_id in create_project:
                exists = self.env['s2u.project'].search([('partner_id', '=', self.partner_id.id),
                                                         ('projecttype_id', '=', projecttype_id),
                                                         ('state', '!=', 'closed')], limit=1)
                if exists:
                    exists.write({
                        'other_sale_ids': [(0, _, {
                            'sale_id': self.id
                        })]
                    })
                    continue
                self.create_project_for_service(projecttype_id)

        if create_project_always:
            # remove doubles - make 1 project for it
            create_project = list(set(create_project_always))
            for projecttype_id in create_project:
                self.create_project_for_service(projecttype_id)

        return super(Sale, self).before_confirm()

    @api.one
    def _compute_amount_quot_blocks(self):

        net_amount_products = 0.0
        vat_amount_products = 0.0
        gross_amount_products = 0.0
        net_amount_subscriptions = 0.0
        vat_amount_subscriptions = 0.0
        gross_amount_subscriptions = 0.0
        for line in self.line_ids:
            if line.product_id.res_model == 's2u.subscription.template':
                per_month = line.subscription_total_month
                net_amount_subscriptions += per_month
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_netto_amount(per_month)
                    gross = line.vat_id.calc_gross_amount(per_month, vat)
                    vat_amount_subscriptions += vat
                    gross_amount_subscriptions += gross
                else:
                    gross_amount_subscriptions += per_month
            else:
                if line.price_is_net:
                    net_amount_products += line.amount
                    if line.vat_id:
                        vat = line.vat_id.calc_vat_from_netto_amount(line.amount)
                        gross = line.vat_id.calc_gross_amount(line.amount, vat)
                        vat_amount_products += vat
                        gross_amount_products += gross
                    else:
                        gross_amount_products += line.amount
                else:
                    gross_amount_products += line.amount
                    if line.vat_id:
                        vat = line.vat_id.calc_vat_from_gross_amount(line.amount)
                        net = line.amount - vat
                        vat_amount_products += vat
                        net_amount_products += net
                    else:
                        net_amount_products += line.amount

        self.quot_net_amount_products = net_amount_products
        self.quot_vat_amount_products = vat_amount_products
        self.quot_gross_amount_products = gross_amount_products
        self.quot_net_amount_subscriptions = net_amount_subscriptions
        self.quot_vat_amount_subscriptions = vat_amount_subscriptions
        self.quot_gross_amount_subscriptions = gross_amount_subscriptions

    @api.one
    def _compute_amount_blocks(self):

        net_amount_products = 0.0
        vat_amount_products = 0.0
        gross_amount_products = 0.0
        net_amount_subscriptions = 0.0
        vat_amount_subscriptions = 0.0
        gross_amount_subscriptions = 0.0
        for line in self.line_ids:
            if line.product_id.res_model == 's2u.subscription.template':
                per_month = line.subscription_total_month
                net_amount_subscriptions += per_month
                if line.vat_id:
                    vat = line.vat_id.calc_vat_from_netto_amount(per_month)
                    gross = line.vat_id.calc_gross_amount(per_month, vat)
                    vat_amount_subscriptions += vat
                    gross_amount_subscriptions += gross
                else:
                    gross_amount_subscriptions += per_month
            else:
                if line.price_is_net:
                    net_amount_products += line.amount
                    if line.vat_id:
                        vat = line.vat_id.calc_vat_from_netto_amount(line.amount)
                        gross = line.vat_id.calc_gross_amount(line.amount, vat)
                        vat_amount_products += vat
                        gross_amount_products += gross
                    else:
                        gross_amount_products += line.amount
                else:
                    gross_amount_products += line.amount
                    if line.vat_id:
                        vat = line.vat_id.calc_vat_from_gross_amount(line.amount)
                        net = line.amount - vat
                        vat_amount_products += vat
                        net_amount_products += net
                    else:
                        net_amount_products += line.amount

        self.net_amount_products = net_amount_products
        self.vat_amount_products = vat_amount_products
        self.gross_amount_products = gross_amount_products
        self.net_amount_subscriptions = net_amount_subscriptions
        self.vat_amount_subscriptions = vat_amount_subscriptions
        self.gross_amount_subscriptions = gross_amount_subscriptions

    @api.multi
    def format_templates(self):
        super(Sale, self).format_templates()

        if self.subscription_prefix:
            if self.prefix_quotation:
                self.prefix_quotation = '%s\n%s' % (self.prefix_quotation, self.subscription_prefix)
            else:
                self.prefix_quotation = self.subscription_prefix

            if self.prefix_confirmation:
                self.prefix_confirmation = '%s\n%s' % (self.prefix_confirmation, self.subscription_prefix)
            else:
                self.prefix_confirmation = self.subscription_prefix

        for block in self.subscription_block_ids:
            if self.prefix_quotation:
                self.prefix_quotation = '%s<br><br>%s' % (self.prefix_quotation, block.block_id.description)
            else:
                self.prefix_quotation = block.block_id.description

            if self.prefix_confirmation:
                self.prefix_confirmation = '%s<br><br>%s' % (self.prefix_confirmation, block.block_id.description)
            else:
                self.prefix_confirmation = block.block_id.description

        if self.subscription_postfix:
            if self.postfix_quotation:
                self.postfix_quotation = '%s\n%s' % (self.subscription_postfix, self.postfix_quotation)
            else:
                self.postfix_quotation = self.subscription_postfix

            if self.postfix_confirmation:
                self.postfix_confirmation = '%s\n%s' % (self.subscription_postfix, self.postfix_confirmation)
            else:
                self.postfix_confirmation = self.subscription_postfix


    _order_state = {
        'draft': [('readonly', False)],
        'quot': [('readonly', False)],
        'order': [('readonly', False)],
        'payment': [('readonly', False)],
    }

    subscription_count = fields.Integer(string='# of Subscriptions', compute='_get_subscription_count', readonly=True)
    subscription_id = fields.Many2one('s2u.subscription', string='Subscription', ondelete='set null')
    lines_with_products = fields.Boolean(string='Lines with products', compute='_lines_with', readonly=True)
    lines_with_subscriptions = fields.Boolean(string='Lines with products', compute='_lines_with', readonly=True)
    ordered_with_products = fields.Boolean(string='Lines with products', compute='_lines_with', readonly=True)
    ordered_with_subscriptions = fields.Boolean(string='Lines with products', compute='_lines_with', readonly=True)
    subscriptionv2_count = fields.Integer(string='# of Subscriptions', compute='_get_subscriptionv2_count', readonly=True)
    quot_net_amount_products = fields.Monetary(string='Net amount', currency_field='currency_id', compute=_compute_amount_quot_blocks,
                                               readonly=True)
    quot_vat_amount_products = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount_quot_blocks,
                                               readonly=True)
    quot_gross_amount_products = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                                 compute=_compute_amount_quot_blocks, readonly=True)
    quot_net_amount_subscriptions = fields.Monetary(string='Net amount', currency_field='currency_id',
                                                    compute=_compute_amount_quot_blocks,
                                                    readonly=True)
    quot_vat_amount_subscriptions = fields.Monetary(string='VAT', currency_field='currency_id', compute=_compute_amount_quot_blocks,
                                                    readonly=True)
    quot_gross_amount_subscriptions = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                                      compute=_compute_amount_quot_blocks, readonly=True)
    net_amount_products = fields.Monetary(string='Net amount', currency_field='currency_id',
                                          compute=_compute_amount_blocks,
                                          readonly=True)
    vat_amount_products = fields.Monetary(string='VAT', currency_field='currency_id',
                                          compute=_compute_amount_blocks,
                                          readonly=True)
    gross_amount_products = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                            compute=_compute_amount_blocks, readonly=True)
    net_amount_subscriptions = fields.Monetary(string='Net amount', currency_field='currency_id',
                                               compute=_compute_amount_blocks,
                                               readonly=True)
    vat_amount_subscriptions = fields.Monetary(string='VAT', currency_field='currency_id',
                                               compute=_compute_amount_blocks,
                                               readonly=True)
    gross_amount_subscriptions = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                                 compute=_compute_amount_blocks, readonly=True)
    subscription_block_ids = fields.One2many('s2u.sale.subscription.block', 'sale_id',
                                             string='Block', copy=False, readonly=True, states=_order_state)
    subscription_prefix = fields.Html(string='Prefix')
    subscription_postfix = fields.Html(string='Postfix')





