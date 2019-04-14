# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Warehouse(models.Model):
    _name = "s2u.warehouse"
    _description = "Warehouse"
    _order = "name"

    @api.model
    def _default_address(self):
        return self.env.user.company_id.entity_id.get_physical()

    name = fields.Char(string='Warehouse', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    entity_id = fields.Many2one('s2u.crm.entity', string='Warehouse', required=True, index=True,
                                default=lambda self: self.env.user.company_id.entity_id, domain=[('type', '=', 'b2b')])
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, required=True,
                                 default=_default_address)
    default = fields.Boolean('Default', default=False)


class Location(models.Model):
    _name = "s2u.warehouse.location"
    _description = "Location Warehouse"
    _order = "name"

    name = fields.Char(string='Location', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    usage = fields.Selection([
        ('normal', 'Normal'),
        ('incoming', 'Incoming'),
        ('not', 'Not usable'),
        ('rma', 'RMA'),
        ('outgoing', 'Outgoing'),
        ('produced', 'Produced'),
        ('leftover', 'Leftover')
    ], required=True, default='normal', string='Usage', copy=False)

