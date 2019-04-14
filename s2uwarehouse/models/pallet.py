# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Pallet(models.Model):
    _name = "s2u.warehouse.pallet"
    _inherit = 's2u.baseproduct.abstract'
    _description = "Pallet"
    _order = "name"

    name = fields.Char(string='Pallet', required=True, index=True)
    length = fields.Integer(string='Lengte (mm)', required=True)
    width = fields.Integer(string='Breedte (mm)', required=True)
    height = fields.Integer(string='Hoogte/dikte (mm)', required=True)
    weight = fields.Float(required=True, string='Gewicht (kg)', digits=(16, 3))
    max_height = fields.Integer(string='effectieve hoogte (mm)', required=True)
    max_weight = fields.Float(required=True, string='laadvermogen (kg)', digits=(16, 3))
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    full_name = fields.Char(required=True, index=True, string='Name', compute='_compute_get_full_name')
    code = fields.Char(string='Code', required=True, index=True, size=10)

    @api.multi
    @api.depends('name', 'length', 'width')
    def name_get(self):
        result = []
        for p in self:
            name = '%s - %d x %d' % (p.name, p.length, p.width)
            result.append((p.id, name))
        return result

    @api.one
    @api.depends('name', 'length', 'width')
    def _compute_get_full_name(self):
        self.full_name = '%s - %d x %d' % (self.name, self.length, self.width)

