# -*- coding: utf-8 -*-

import os
import os.path

from odoo import api, fields, models, _


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def create(self, vals):

        attachment = super(IrAttachment, self).create(vals)

        if 'res_field' in vals:
            entity_id = False
        else:
            entity_id = False
            if attachment.res_model and attachment.res_model.startswith('s2u.'):
                doc_context = self.env[attachment.res_model]._description if self.env[attachment.res_model]._description \
                    else self.env[attachment.res_model]._name
                if attachment.res_model == 's2u.document':
                    entity_id = False
                elif attachment.res_model == 's2u.crm.entity':
                    entity_id = attachment.res_id
                    model_data = self.env[attachment.res_model].sudo().browse(attachment.res_id)
                    rec_context = model_data.entity_code if model_data.entity_code else model_data.name
                else:
                    model_data = self.env[attachment.res_model].sudo().browse(attachment.res_id)
                    if hasattr(model_data, 'name'):
                        rec_context = model_data.name
                    else:
                        rec_context = 'ID:%d' % attachment.res_id
                    if hasattr(model_data, 'partner_id'):
                        entity_id = model_data.partner_id.id
                    elif hasattr(model_data, 'entity_id'):
                        entity_id = model_data.entity_id.id

        if entity_id:
            extension = os.path.splitext(attachment.name)[1][1:]
            unknown_ext = self.env['s2u.document.type.ext'].sudo().search([('name', '=', '*.*')], limit=1)
            doctype_id = False
            if extension:
                ext = self.env['s2u.document.type.ext'].sudo().search([('name', 'ilike', extension)], limit=1)
                if ext:
                    doctype_id = ext.doctype_id.id
                elif unknown_ext:
                    doctype_id = unknown_ext.doctype_id.id
            elif unknown_ext:
                doctype_id = unknown_ext.doctype_id.id

            exists = self.env['s2u.document'].search([('entity_id', '=', entity_id),
                                                      ('res_model', '=', attachment.res_model),
                                                      ('res_id', '=', attachment.res_id),
                                                      ('name', '=', attachment.name)], limit=1)
            if not exists:
                self.env['s2u.document'].create({
                    'entity_id': entity_id,
                    'name': attachment.name,
                    'res_model': attachment.res_model,
                    'res_id': attachment.res_id,
                    'datas': attachment.datas,
                    'doctype_id': doctype_id,
                    'doc_context': doc_context,
                    'rec_context': rec_context
                })
            else:
                exists.write({
                    'name': attachment.name,
                    'datas': attachment.datas,
                    'doctype_id': doctype_id,
                    'doc_context': doc_context,
                    'rec_context': rec_context
                })

        return attachment