import base64
from odoo import api, models
from datetime import datetime

class PrintHourInvoicing(models.AbstractModel):
    _name = 'report.s2uproject.print_hour_invoicing'

    @api.model
    def get_report_values(self, docids, data=None):
        partner_hour_obj = self.env['s2u.project.hour.invoicing.partner.hour']
        project_hour_obj = self.env['s2u.project.hour']

        data_info = {}
        partner_ids = []
        hour_ids = []
        tot_hours = 0.0
        for out in self.env['s2u.project.hour.invoicing'].browse(docids):
            for partner in out.partner_ids:
                if partner.partner_id not in partner_ids:
                    data_info[partner.partner_id.name] = {}
                    partner_ids.append(partner.partner_id)
                hours = partner_hour_obj.search([('invpartner_id', '=', partner.id)])
                for hour in hours:
                    phours = project_hour_obj.search([('invpartnerline_id', '=', hour.id)], order="date desc")
                    for phour in phours:
                        if phour.id not in hour_ids:
                            hour_ids.append(phour.id)
                            tot_hours += phour.hours
                            data_info[partner.partner_id.name][phour.id] = {
                                'project': phour.project_id.name,
                                'user': phour.user_id.name,
                                'date': datetime.strptime(phour.date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                                'hours': phour.hours,
                                'type': '',
                                'description': phour.name,
                                'partner': partner.partner_id.name,
                                'fase': hour.projectrate_id.stage_id.name,
                                'rate': hour.projectrate_id.rate_id.name
                            }

        return {
            'data': data_info,
            'hour_sort': hour_ids,
            'tot_hours': tot_hours
        }

