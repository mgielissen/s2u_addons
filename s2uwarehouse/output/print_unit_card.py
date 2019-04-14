import base64
from odoo import api, models


class PrintUnitCard(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_unit_card'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': 's2u.warehouse.unit',
            'docs': self.env['s2u.warehouse.unit'].browse(docids),
        }

