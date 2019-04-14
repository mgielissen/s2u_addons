# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class Uom(models.Model):
    _name = "s2u.warehouse.uom"
    _description = "Uom"
    _order = "name"

    name = fields.Char(string='Uom', required=True, index=True)
    name_lower = fields.Char(string='Uom (lower)', index=True)
    name_singular = fields.Char(string='Uom (singular)', required=True, index=True)
    name_lower_singular = fields.Char(string='Uom (lower/singular)', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)

    @api.model
    def create(self, vals):
        if vals.get('name', False):
            vals['name_lower'] = vals['name'].lower()
        if vals.get('name_singular', False):
            vals['name_lower_singular'] = vals['name_singular'].lower()
        uom = super(Uom, self).create(vals)

        return uom

    @api.multi
    def write(self, vals):
        if vals.get('name', False):
            vals['name_lower'] = vals['name'].lower()
        if vals.get('name_singular', False):
            vals['name_lower_singular'] = vals['name_singular'].lower()
        res = super(Uom, self).write(vals)

        return res

    def parse_qty(self, qty):

        try:
            items = qty.split(' ')
            if len(items) == 1:
                parsed = [False, False, float(items[0])]
            elif len(items) == 3:
                parsed = [int(items[0]), items[1], float(items[2])]
            else:
                return False
        except:
            return False

        if parsed[1]:
            if not self.search(['|', ('name_lower', '=', parsed[1].lower()), ('name_lower_singular', '=', parsed[1].lower())]):
                raise UserError(_('Unknown value [%s] for uom!' % parsed[1]))

        return parsed


