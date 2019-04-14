# -*- coding: utf-8 -*-

from openerp import api, fields, models, _


class CrmEntityKickback(models.Model):
    _name = "s2u.crm.entity.kickback"

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True, ondelete='cascade')
    name = fields.Char(string='Kickback', required=True)
    kickback = fields.Float(string='Kickback in %', default=0.0, required=True)


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    intermediair_kickback = fields.Float(string='Kickback in %', default=0.0, copy=False, help="Default kickback")
    intermediair_marge = fields.Float(string='Marge in %', default=25.0, copy=False)
    intermediair_kickback_ids = fields.One2many('s2u.crm.entity.kickback', 'entity_id',
                                                string='Kickback in %')

