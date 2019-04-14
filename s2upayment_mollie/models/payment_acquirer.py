# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PaymentTransaction(models.Model):
    _inherit = 's2u.payment.transaction'

    @api.multi
    def do_order_confirmation(self, method, sale, default_vals=None):
        self.ensure_one()

        if method == 'mollie':
            if not sale.do_quotation():
                raise ValueError(_('Problem during order confirmation, please contact customer services. #1'))
            if not sale.do_order():
                raise ValueError(_('Problem during order confirmation, please contact customer services. #2'))
            if not sale.do_confirm():
                raise ValueError(_('Problem during order confirmation, please contact customer services. #3'))

            lines = self.env['s2u.account.invoice.line'].sudo().search([('sale_id', '=', sale.id)])
            if not lines:
                raise ValueError(_('Problem during order confirmation, please contact customer services. #4'))
            invoices = [l.invoice_id.id for l in lines]
            invoices = list(set(invoices))
            invoices = self.env['s2u.account.invoice'].sudo().browse(invoices)

            amount = 0.0
            for invoice in invoices:
                if invoice.state == 'draft':
                    invoice.do_validate()
                amount += invoice.amount_gross
            if round(amount, 2) != round(self.tot_amount, 2):
                raise ValueError(_('Problem during order confirmation, please contact customer services. #5'))

            journal_model = self.env['s2u.account.memorial']

            so_ids = []
            invoice_numbers = []
            for invoice in invoices:
                inv = {
                    'currency_id': invoice.currency_id.id,
                    'trans_amount': invoice.amount_gross,
                    'invoice_id': invoice.id
                }
                so_ids.append((0, 0, inv))
                invoice_numbers.append(invoice.name)

            vals1 = {
                'currency_id': invoices[0].currency_id.id,
                'type': 'deb',
                'partner_id': invoices[0].partner_id.id,
                'gross_amount': round(amount, 2),
                'vat_amount': 0.0,
                'so_ids': so_ids
            }

            vals2 = {
                'currency_id': invoices[0].currency_id.id,
                'type': 'nor',
                'gross_amount': amount * -1.0,
                'vat_amount': 0.0,
                'account_id': self.acquirer_id.mollie_account_id.id
            }

            mollie_ref = default_vals.get('reference', self.name)

            journal_vals = {
                'name': 'Mollie payment %s for invoice %s' % (mollie_ref, ','.join(invoice_numbers)),
                'date_trans': fields.Date.context_today(self),
                'currency_id': invoices[0].currency_id.id,
                'memorial_type': 'nor',
                'line_ids': [(0, 0, vals1), (0, 0, vals2)]
            }

            journal_model.sudo().create(journal_vals)

            return True
        else:
            return super(PaymentTransaction, self).do_order_confirmation(method, sale, default_vals=default_vals)


class PaymentAcquirer(models.Model):
    _inherit = 's2u.payment.acquirer'

    def _get_providers(self):

        providers = super(PaymentAcquirer, self)._get_providers()
        providers.append(['mollie', 'Mollie'])
        return providers

    mollie_api_key_prod = fields.Char(string='Api key (production)')
    mollie_api_key_test = fields.Char(string='Api key (test)')
    mollie_base_url_prod = fields.Char(string='Base url (production)')
    mollie_base_url_test = fields.Char(string='Base url (test)')
    mollie_description = fields.Char(string='Description', size=35, help='Description visible for customer on Mollie transaction.')
    mollie_account_id = fields.Many2one('s2u.account.account', string='Account',
                                        domain=[('type', 'in', ['bank', 'cash'])])




