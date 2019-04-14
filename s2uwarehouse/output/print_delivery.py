import base64
from odoo import api, models


class PrintDelivery(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_delivery'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.warehouse.outgoing'],
            'data': data,
            'docs': self.env['s2u.warehouse.outgoing'].browse(docids)
        }

