# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PaymentTransaction(models.Model):
    _inherit = 's2u.payment.transaction'

    @api.multi
    def do_order_confirmation(self, method, sale, default_vals=None):
        self.ensure_one()

        if method == 'manual':
            if not sale.do_quotation():
                raise ValueError(_('Problem during order confirmation, please contact customer services.'))
            if not sale.do_payment():
                raise ValueError(_('Problem during order confirmation, please contact customer services.'))
            return True
        else:
            return super(PaymentTransaction, self).do_order_confirmation(method, sale, default_vals=default_vals)

class PaymentAcquirer(models.Model):
    _inherit = 's2u.payment.acquirer'

    def _get_providers(self):

        providers = super(PaymentAcquirer, self)._get_providers()
        providers.append(['manual', 'Manual'])
        return providers

    manual_account = fields.Char(string='Account',
                                 help='The account information customer has to transfer money to.')
    manual_account_owner = fields.Char(string='Account owner',
                                       help='The owner of the account, also displayed to customer.')






