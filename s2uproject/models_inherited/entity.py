# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    def _get_project_count(self):

        for entity in self:
            projects = self.env['s2u.project'].search([('partner_id', '=', entity.id)])
            project_ids = [l.id for l in projects]
            project_ids = list(set(project_ids))
            entity.project_count = len(project_ids)

    def _get_project_open_count(self):

        for entity in self:
            projects = self.env['s2u.project'].search([('partner_id', '=', entity.id),
                                                       ('state', '!=', 'closed')])
            project_ids = [l.id for l in projects]
            project_ids = list(set(project_ids))
            entity.project_open_count = len(project_ids)

    @api.multi
    def action_view_project(self):
        projects = self.env['s2u.project'].search([('partner_id', '=', self.id)])
        project_ids = [l.id for l in projects]
        project_ids = list(set(project_ids))

        action = self.env.ref('s2uproject.action_project').read()[0]
        if len(project_ids) > 1:
            action['domain'] = [('id', 'in', project_ids)]
        elif len(project_ids) == 1:
            action['views'] = [(self.env.ref('s2uproject.project_form').id, 'form')]
            action['res_id'] = project_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    def compute_classification(self):

        projects = self.env['s2u.project'].search([('partner_id', '=', self.id), ('state', '=', 'open')])
        classification = [p.projecttype_id.classification for p in projects if p.projecttype_id and p.projecttype_id.classification != 'none']
        self.classification_visual = ''.join(classification)

    def _get_discount_rates_count(self):

        for entity in self:
            discounts = self.env['s2u.project.hour.rate.def.partner'].search([('partner_id', '=', entity.id)])
            entity.discount_rates_count = len(discounts)

    @api.multi
    def action_view_discount_rates(self):
        discounts = self.env['s2u.project.hour.rate.def.partner'].search([('partner_id', '=', self.id)])

        action = self.env.ref('s2uproject.action_sale_rate_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_partner_id': self.id
        }
        action['context'] = str(context)
        return action

    project_count = fields.Integer(string='# of Projects', compute='_get_project_count', readonly=True)
    project_open_count = fields.Integer(string='# of Open rrojects', compute='_get_project_open_count', readonly=True)
    classification_visual = fields.Char(string='Classification', readonly=True, compute='compute_classification')
    discount_rate_ids = fields.One2many('s2u.project.hour.rate.def.partner', 'partner_id', string='Discount for rates')
    discount_rates_count = fields.Integer(string='# of Rates discounts',
                                          compute='_get_discount_rates_count',
                                          readonly=True)
    use_project_zones = fields.Boolean(string='Overrule zones', default=False)
    project_zone1 = fields.Float(string='Office hours (%)', default='0.0')
    project_zone2 = fields.Float(string='After hours (%)', default='35.0')
    project_zone3 = fields.Float(string='Sat. and Sun. (%)', default='50.0')
    project_zone4 = fields.Float(string='Holidays (%)', default='100.0')



