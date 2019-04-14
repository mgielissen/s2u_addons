# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountReportDebtor(models.TransientModel):
    _name = "report.s2uaccount.debtor"
    _description = "Debtor Report"

    @api.model
    def _default_date_till(self):
        cd = datetime.date.today().day
        cm = datetime.date.today().month
        cy = datetime.date.today().year

        return datetime.date(cy, cm, cd) - datetime.timedelta(days=0)

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    date_till = fields.Date(string='Till', default=_default_date_till)

    def _print_report(self, data):
        return self.env.ref('s2uaccount.s2uaccount_report_debtor'). \
            with_context(landscape=True).report_action(self, data=data)

    @api.multi
    def check_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['date_till', 'company_id'])[0]
        }
        return self._print_report(data)

