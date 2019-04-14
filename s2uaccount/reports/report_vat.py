# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountReportVatSaved(models.Model):
    _name = "report.s2uaccount.vat.saved"
    _description = "Vat report saved"

    company_id = fields.Many2one('res.company', string='Company', readonly=True, index=True,
                                 default=lambda self: self.env.user.company_id)
    amount_name = fields.Char(required=True, index=True)
    vat_report = fields.Char(required=True, index=True)
    currency_id = fields.Many2one('res.currency', string='Account Currency')
    vat_till = fields.Date(string='VAT till', index=True)
    amount = fields.Monetary(string='Amount net')


class AccountReportVat(models.TransientModel):
    _name = "report.s2uaccount.vat"
    _description = "Vat Report"

    @api.model
    def _default_vat_till(self):

        cm = datetime.date.today().month
        cy = datetime.date.today().year

        return datetime.date(cy, cm, 1) - datetime.timedelta(days=1)

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    vat_till = fields.Date(string='Vat till', default=_default_vat_till)

    def _print_report(self, data):

        return self.env.ref('s2uaccount.s2uaccount_report_vat').report_action(self, data=data)

    @api.multi
    def check_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['vat_till', 'company_id'])[0],
            'final': False
        }
        return self._print_report(data)

    @api.multi
    def make_final(self):
        self.ensure_one()
        data = {
            'ids': self.env.context.get('active_ids', []),
            'model': self.env.context.get('active_model', 'ir.ui.menu'),
            'form': self.read(['vat_till', 'company_id'])[0],
            'final': True
        }
        return self._print_report(data)
