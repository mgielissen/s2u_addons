import datetime
from odoo import api, fields, models, _


class PalletsHistory(models.TransientModel):
    _name = 'report.s2u_warehouse.pallets.history'

    @api.multi
    def print_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['date_till',
                               'entity_id',
                               'company_id', ])[0]
        }

        return self.env.ref('s2uwarehouse.s2u_warehouse_print_pallets_history').report_action(self, data=data)

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True,)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    date_till = fields.Date(string='Date Till', index=True, required=True,
                            default=lambda self: datetime.datetime.now())




