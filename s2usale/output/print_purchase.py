import base64
from odoo import api, models


class PrintQuotationPO(models.AbstractModel):
    _name = 'report.s2usale.print_quotation_po'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.purchase'],
            'data': data,
            'docs': self.env['s2u.purchase'].browse(docids)
        }


class PrintOrderPO(models.AbstractModel):
    _name = 'report.s2usale.print_order_po'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.purchase'],
            'data': data,
            'docs': self.env['s2u.purchase'].browse(docids)
        }
