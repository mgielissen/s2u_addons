# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AccountInvoiceHour(models.Model):
    _name = 's2u.account.invoice.hour'

    @api.onchange('hours', 'rate_per_hour')
    def _onchange_hours(self):
        if self.hours and self.rate_per_hour:
            self.amount = self.rate_per_hour * self.hours
        else:
            self.amount = 0.0

    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True)
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase', ondelete='cascade')
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', ondelete='cascade')
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id')
    hours = fields.Float(string='Hours', digits=(16, 2))
    amount = fields.Monetary(string='Amount')
    hours_paid = fields.Boolean(string='Paid', default=False, index=True)


class AccountInvoice(models.Model):
    _inherit = 's2u.account.invoice'

    @api.multi
    def invoice_paid(self):

        self.ensure_one()

        for hour in self.hour_ids:
            # already booked, then skip
            if hour.hours_paid:
                continue

            if hour.invoice_id.project_id:
                exists = self.env['s2u.project.stage.role'].search([('project_id', '=', hour.invoice_id.project_id.id),
                                                                    ('stage_id', '=', hour.stage_id.id),
                                                                    ('rate_id', '=', hour.rate_id.id)], limit=1)
                if exists:
                    exists.write({
                        'hours': exists.hours + hour.hours,
                        'amount': exists.amount + hour.amount
                    })
                else:
                    exists.create({
                        'project_id': hour.invoice_id.project_id.id,
                        'rate_per_hour': hour.rate_per_hour,
                        'hours': hour.hours,
                        'amount': hour.amount
                    })
                hour.write({
                    'hours_paid': True
                })

        return super(AccountInvoice, self).invoice_paid()

    @api.multi
    def invoice_not_paid(self):

        self.ensure_one()

        for hour in self.hour_ids:
            # already reverted, then skip
            if not hour.hours_paid:
                continue

            if hour.invoice_id.project_id:
                exists = self.env['s2u.project.stage.role'].search([('project_id', '=', hour.invoice_id.project_id.id),
                                                                    ('stage_id', '=', hour.stage_id.id),
                                                                    ('rate_id', '=', hour.rate_id.id)], limit=1)
                if exists:
                    exists.write({
                        'hours': exists.hours - hour.hours,
                        'amount': exists.amount - hour.amount
                    })

                hour.write({
                    'hours_paid': False
                })

        return super(AccountInvoice, self).invoice_not_paid()

    hour_ids = fields.One2many('s2u.account.invoice.hour', 'invoice_id', string='Hours')
    project_id = fields.Many2one('s2u.project', string='Project', ondelete='cascade')
