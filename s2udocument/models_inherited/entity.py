# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    def _get_document_count(self):

        for entity in self:
            docs = self.env['s2u.document'].search([('entity_id', '=', entity.id)])
            entity.document_count = len(docs.ids)

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('entity_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.entity_code if self.entity_code else self.name,
            'default_res_model': 's2u.crm.entity',
            'default_res_id': self.id
        }
        action['context'] = str(context)
        return action

    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)

