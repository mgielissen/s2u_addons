import base64
from odoo import api, models


class PrintQuotationSO(models.AbstractModel):
    _name = 'report.s2usale.print_quotation_so'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.sale'],
            'data': data,
            'docs': self.env['s2u.sale'].browse(docids)
        }


class PrintOrderSO(models.AbstractModel):
    _name = 'report.s2usale.print_order_so'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.sale'],
            'data': data,
            'docs': self.env['s2u.sale'].browse(docids)
        }
