# -*- coding: utf-8 -*-
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import _, api, fields, models


class ActionProjectIncreaseHour(models.TransientModel):
    _name = 's2uproject.action.increase.hour'
    _description = 'Increase hours within the project'

    @api.onchange('hours', 'rate_per_hour')
    def _onchange_hours(self):
        if self.hours and self.rate_per_hour:
            self.amount = self.rate_per_hour * self.hours
        else:
            self.amount = 0.0

    increase_id = fields.Many2one('s2uproject.action.increase', string='Increase', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='increase_id.currency_id', store=True)
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase', ondelete='set null')
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', ondelete='set null')
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id')
    hours = fields.Float(string='Hours', digits=(16, 2))
    amount = fields.Monetary(string='Amount')


class ActionProjectIncrease(models.TransientModel):
    """
    """
    _name = 's2uproject.action.increase'
    _description = 'Increase hours within the project'

    @api.onchange('projecttype_id')
    def onchange_projecttype_id(self):

        if self.projecttype_id:
            add_rates = []
            for stage in self.projecttype_id.stage_ids:
                if not stage.rate_ids:
                    continue
                for rate in stage.rate_ids:
                    if rate.rate_per_hour:
                        rate_per_hour = rate.rate_per_hour
                    else:
                        partner_rate = False
                        if self.project_id.partner_id:
                            partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                                search([('rate_id', '=', rate.rate_id.id),
                                        ('partner_id', '=', self.project_id.partner_id.id)], limit=1)
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
                        'rate_per_hour': rate_per_hour
                    }
                    add_rates.append((0, 0, vals))
            self.hour_ids = add_rates

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    project_id = fields.Many2one('s2u.project', string="Project", ondelete='set null')
    projecttype_id = fields.Many2one('s2u.project.type', string='Type', ondelete='set null')
    customer_code = fields.Char(string='Customer ref.')
    reference = fields.Char(string='Our ref.')
    hour_ids = fields.One2many('s2uproject.action.increase.hour', 'increase_id', string='Hours')

    @api.model
    def default_get(self, fields):

        result = super(ActionProjectIncrease, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        project = self.env['s2u.project'].browse(active_ids[0])
        if project.projecttype_id:
            result['projecttype_id'] = project.projecttype_id.id
            add_rates = []
            for stage in project.projecttype_id.stage_ids:
                if not stage.rate_ids:
                    continue
                for rate in stage.rate_ids:
                    partner_rate = False
                    if project.partner_id:
                        partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                            search([('rate_id', '=', rate.rate_id.id),
                                    ('partner_id', '=', project.partner_id.id)], limit=1)
                    rate_per_hour = partner_rate.rate_per_hour if partner_rate else rate.rate_id.rate_per_hour
                    vals = {
                        'stage_id': stage.stage_id.id,
                        'rate_id': rate.rate_id.id,
                        'hours': rate.hours,
                        'amount': rate.hours * rate_per_hour,
                        'rate_per_hour': rate_per_hour
                    }
                    add_rates.append((0, 0, vals))
            result['hour_ids'] = add_rates

        result['reference'] = project.name
        result['project_id'] = project.id

        return result

    @api.multi
    def do_increase(self):

        self.ensure_one()

        project = self.project_id

        invlines = []
        hourlines = []
        for hour in self.hour_ids:
            ihours = int(hour.hours)
            qty = "%02d:%02d" % (ihours, (hour.hours - ihours) * 60)
            descript = '%s - %s' % (hour.stage_id.name, hour.rate_id.name)

            vals = {
                'net_amount': hour.amount,
                'account_id': hour.rate_id.account_id.id,
                'descript': descript,
                'qty': qty,
                'net_price': hour.rate_per_hour,
                'price_per': 'item'
            }
            if project.partner_id.vat_sell_id:
                vals['vat_id'] = project.partner_id.vat_sell_id.id
                vals['vat_amount'] = project.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                    vals['net_amount'])
                vals['gross_amount'] = project.partner_id.vat_sell_id.calc_gross_amount(
                    vals['net_amount'], vals['vat_amount'])
            else:
                if hour.rate_id.account_id.vat_id:
                    vals['vat_id'] = hour.rate_id.account_id.vat_id.id
                    vals['vat_amount'] = hour.rate_id.account_id.vat_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = hour.rate_id.account_id.vat_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for role %s!' % hour.rate_id.name))
            invlines.append((0, 0, vals))

            hour_vals = {
                'stage_id': hour.stage_id.id,
                'rate_id': hour.rate_id.id,
                'rate_per_hour': hour.rate_per_hour,
                'hours': hour.hours,
                'amount': hour.amount
            }
            hourlines.append((0, 0, hour_vals))

        invoice_model = self.env['s2u.account.invoice']

        if invlines:
            if project.sale_id:
                invdata = {
                    'type': project.sale_id.type,
                    'partner_id': project.sale_id.invoice_partner_id.id,
                    'address_id': project.sale_id.invoice_address_id.id if project.sale_id.invoice_address_id else False,
                    'contact_id': project.sale_id.invoice_contact_id.id if project.sale_id.invoice_contact_id else False,
                    'reference': project.name,
                    'customer_code': self.customer_code,
                    'line_ids': invlines,
                    'hour_ids': hourlines,
                    'date_invoice': fields.Date.context_today(self),
                    'date_financial': fields.Date.context_today(self),
                    'project_id': project.id
                }

                if project.sale_id.invoice_partner_id.payment_term_id:
                    due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                    due_date = due_date + datetime.timedelta(days=project.sale_id.invoice_partner_id.payment_term_id.payment_terms)
                    invdata['date_due'] = due_date.strftime('%Y-%m-%d')
            else:
                invdata = {
                    'type': project.partner_id.type,
                    'partner_id': project.partner_id.id,
                    'address_id': False,
                    'contact_id': False,
                    'reference': project.reference,
                    'customer_code': self.customer_code,
                    'line_ids': invlines,
                    'hour_ids': hourlines,
                    'date_invoice': fields.Date.context_today(self),
                    'date_financial': fields.Date.context_today(self),
                    'project_id': project.id
                }

                if project.partner_id.payment_terms:
                    due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                    due_date = due_date + datetime.timedelta(days=project.partner_id.payment_terms)
                    invdata['date_due'] = due_date.strftime('%Y-%m-%d')

            invoice = invoice_model.create(invdata)

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
        else:
            return {'type': 'ir.actions.act_window_close'}
