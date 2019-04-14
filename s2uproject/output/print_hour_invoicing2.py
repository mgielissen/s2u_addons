import base64
from odoo import api, models
from datetime import datetime

class PrintHourInvoicing2(models.AbstractModel):
    _name = 'report.s2uproject.print_hour_invoicing2'

    @api.model
    def get_report_values(self, docids, data=None):
        partner_hour_obj = self.env['s2u.project.hour.invoicing.partner.hour']
        project_hour_obj = self.env['s2u.project.hour']
        project_role_obj = self.env['s2u.project.stage.role']

        data_info = {}
        hour_ids = []

        if data['form']['type'] == 'partner':
            hours = partner_hour_obj.search([('invpartner_id', '=', data['form']['invpartner_id'][0])])
            list_key = data['form']['invpartner_id'][1]
            data_info[list_key] = {}
        else:
            roles = project_role_obj.search([('project_id', '=', data['form']['project_id'][0])])
            hours = partner_hour_obj.search([('projectrate_id', 'in', roles.ids)])
            list_key = data['form']['project_id'][1]
            data_info[list_key] = {}

        tot_hours = 0.0
        for hour in hours:
            if hour.invpartner_id.invoicing_id.id == data['form']['invoicing_id'][0]:
                phours = project_hour_obj.search([('invpartnerline_id', '=', hour.id)], order="date desc")
                for phour in phours:
                    if phour.id not in hour_ids:
                        hour_ids.append(phour.id)
                        tot_hours += phour.hours
                        data_info[list_key][phour.id] = {
                            'project': phour.project_id.name,
                            'user': phour.user_id.name,
                            'date': datetime.strptime(phour.date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                            'hours': phour.hours,
                            'type': '',
                            'description': phour.name,
                            'partner': phour.project_id.partner_id.name,
                            'fase': hour.projectrate_id.stage_id.name,
                            'rate': hour.projectrate_id.rate_id.name
                        }

        return {
            'data': data_info,
            'hour_sort': hour_ids,
            'tot_hours': tot_hours
        }

