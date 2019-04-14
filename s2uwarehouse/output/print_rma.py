import base64
from odoo import api, models


class PrintRMA(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_rma'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.warehouse.rma'],
            'data': data,
            'docs': self.env['s2u.warehouse.rma'].browse(docids)
        }

