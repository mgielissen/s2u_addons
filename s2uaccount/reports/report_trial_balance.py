# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountReportTrialBalance(models.TransientModel):
    _name = "report.s2uaccount.trial.balance"
    _description = "Trial Balance"

    @api.model
    def _default_vat_till(self):

        cm = datetime.date.today().month
        cy = datetime.date.today().year

        return datetime.date(cy, cm, 1) - datetime.timedelta(days=1)

    @api.model
    def _default_fiscal_year(self):
        cy = datetime.date.today().year

        return '%04d' % cy

    @api.onchange('fiscal_year', 'compare_left')
    def _onchange_compare_left(self):

        def get_date_from(cy):
            return datetime.date(cy, 1, 1).strftime('%Y-%m-%d')

        def get_date_till(cy):
            if cy == datetime.date.today().year:
                return datetime.date.today().strftime('%Y-%m-%d')
            else:
                return datetime.date(cy, 12, 31).strftime('%Y-%m-%d')

        try:
            cy = int(self.fiscal_year)
        except:
            cy = datetime.date.today().year
            self.fiscal_year = '%04d' % cy

        if self.compare_left and self.compare_left == 'period':
            self.left_from = get_date_from(cy)
            self.left_till = get_date_till(cy)

    @api.onchange('fiscal_year', 'compare_right')
    def _onchange_compare_right(self):

        def get_date_from(cy):
            return datetime.date(cy, 1, 1).strftime('%Y-%m-%d')

        def get_date_till(cy):
            if cy == datetime.date.today().year:
                return datetime.date.today().strftime('%Y-%m-%d')
            else:
                return datetime.date(cy, 12, 31).strftime('%Y-%m-%d')

        try:
            cy = int(self.fiscal_year)
        except:
            cy = datetime.date.today().year
            self.fiscal_year = '%04d' % cy

        if self.compare_right and self.compare_right == 'period':
            self.right_from = get_date_from(cy)
            self.right_till = get_date_till(cy)

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    compare_left = fields.Selection([('year', 'Complete year'),
                                     ('period', 'Period')], required=True, default='year', string='Left column')
    compare_right = fields.Selection([('year', 'Complete year'),
                                     ('period', 'Period')], required=True, default='year', string='Right column')
    fiscal_year = fields.Char(string='Fiscal year', default=_default_fiscal_year, size=4)
    left_from = fields.Date(string='From')
    left_till = fields.Date(string='Till')
    right_from = fields.Date(string='From')
    right_till = fields.Date(string='Till')

    @api.multi
    def print_report(self):
        self.ensure_one()

        data = {
            'form': self.read(['fiscal_year',
                               'left_from',
                               'left_till',
                               'right_from',
                               'right_till',
                               'company_id',
                               'compare_left',
                               'compare_right'])[0]
        }

        return self.env.ref('s2uaccount.s2uaccount_report_trial_balance'). \
            with_context(landscape=True).report_action(self, data=data)

