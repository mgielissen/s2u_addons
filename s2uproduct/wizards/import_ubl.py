# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ImportUBL(models.TransientModel):
    _inherit = "wizard.import.ubl"

    @api.multi
    def ubl_match_account(self, company_id, supplier, ubl_match):

        product_model = self.env['s2u.sale.product']

        if supplier and ubl_match:
            products = product_model.search([('company_id', '=', company_id),
                                             ('entity_id', '=', supplier.id),
                                             ('ubl_match', '=', ubl_match)])
            if products and products[0].po_account_id and products[0].po_vat_id:
                return {'account_id': products[0].po_account_id.id,
                        'vat_id': products[0].po_vat_id.id}

            account = super(ImportUBL, self).ubl_match_account(company_id, supplier, ubl_match)
            return account
        else:
            return super(ImportUBL, self).ubl_match_account(company_id, supplier, ubl_match)

