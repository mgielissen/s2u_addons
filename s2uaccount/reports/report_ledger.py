# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountReportLedger(models.TransientModel):
    _name = "report.s2uaccount.ledger"
    _description = "Ledger Report"

    @api.model
    def _default_ledger_till(self):

        return datetime.date.today()

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    ledger_till = fields.Date(string='Ledger till', default=_default_ledger_till)

    def _print_report(self, data):

        return self.env.ref('s2uaccount.s2uaccount_report_ledger').report_action(self, data=data)

    @api.multi
    def check_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['ledger_till', 'company_id'])[0]
        }
        return self._print_report(data)

