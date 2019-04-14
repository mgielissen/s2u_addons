import datetime

from odoo import api, fields, models, _


class InventoryLocation(models.TransientModel):
    _name = 'report.s2u_warehouse.inventory.location'

    @api.multi
    def print_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['date_till',
                               'company_id', ])[0]
        }

        return self.env.ref('s2uwarehouse.s2u_warehouse_print_inventory_location').report_action(self, data=data)

    date_till = fields.Date(string='Date Till', index=True, required=True,
                            default=lambda self: datetime.datetime.now())
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)




