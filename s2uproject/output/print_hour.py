import base64
from odoo import api, models
from datetime import datetime

class PrintReportHour(models.AbstractModel):
    _name = 'report.s2uproject.print_hour'

    @api.model
    def get_report_values(self, docids, data=None):
        project_obj = self.env['s2u.project']
        hour_obj = self.env['s2u.project.hour']

        data_info = {}
        hour_ids = []
        if data['form']['type'] == 'partner':
            projects = project_obj.search([('partner_id', '=', data['form']['partner_id'][0])
                                           ])
            hours = hour_obj.search([('project_id', 'in', projects.ids),
                                     ('date', '>=', data['form']['date_from']),
                                     ('date', '<=', data['form']['date_till'])])
            list_key = data['form']['partner_id'][1]
            data_info[list_key] = {}
        else:
            hours = hour_obj.search([('project_id', '=', data['form']['project_id'][0]),
                                     ('date', '>=', data['form']['date_from']),
                                     ('date', '<=', data['form']['date_till'])
                                     ])
            list_key = data['form']['project_id'][1]
            data_info[list_key] = {}

        tot_hours = 0.0
        for phour in hours:
            if phour.id not in hour_ids:
                hour_ids.append(phour.id)
                tot_hours += phour.hours
                data_info[list_key][phour.id] = {
                    'project': phour.project_id.name,
                    'user': phour.user_id.name,
                    'date': datetime.strptime(phour.date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                    'hours': phour.hours,
                    'fase': phour.projectrate_id.stage_id.name,
                    'description': phour.name,
                    'partner': phour.project_id.partner_id.name,
                    'rate': phour.projectrate_id.rate_id.name
                }
        print(data_info)
        return {
            'data': data_info,
            'hour_sort': hour_ids,
            'tot_hours': tot_hours
        }
