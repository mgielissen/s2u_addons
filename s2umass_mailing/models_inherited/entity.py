# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    mailinglist_ids = fields.Many2many(
        'mail.mass_mailing.list', 's2u_mass_mailing_entity_list_rel',
        'entity_id', 'list_id', string='Mailing Lists')

    @api.multi
    def write(self, vals):

        res = super(CrmEntity, self).write(vals)

        for entity in self:
            if not entity.mailinglist_ids and 'mailinglist_ids' not in vals:
                continue
            if not ('mailinglist_ids' in vals or 'email' in vals or 'name' in vals):
                continue
            email = vals.get('email', entity.email)
            if vals.get('mailinglist_ids'):
                mailinglist_ids = vals['mailinglist_ids']
            else:
                mailinglist_ids = [(6, 0, entity.mailinglist_ids.ids)]
            if entity.type == 'b2b':
                name = entity.name
            else:
                name = entity.communication if entity.communication else entity.name
            mailing_vals = {
                'name': name,
                'email': email,
                'list_ids': mailinglist_ids,
                's2u_model': 's2u.crm.entity',
                's2u_res_id': entity.id
            }
            exists = self.env['mail.mass_mailing.contact'].search([('s2u_model', '=', 's2u.crm.entity'),
                                                                   ('s2u_res_id', '=', entity.id)], limit=1)
            if exists:
                exists.write(mailing_vals)
            else:
                self.env['mail.mass_mailing.contact'].create(mailing_vals)

        return res

    @api.model
    def create(self, vals):
        res = super(CrmEntity, self).create(vals)

        if res.mailinglist_ids:
            if res.type == 'b2b':
                name = res.name
            else:
                name = res.communication if res.communication else res.name
            mailing_vals = {
                'name': name,
                'email': res.email,
                'list_ids': vals['mailinglist_ids'],
                's2u_model': 's2u.crm.entity',
                's2u_res_id': res.id
            }
            self.env['mail.mass_mailing.contact'].create(mailing_vals)

        return res

    @api.multi
    def unlink(self):
        for entity in self:
            exists = self.env['mail.mass_mailing.contact'].search([('s2u_model', '=', 's2u.crm.entity'),
                                                                   ('s2u_res_id', '=', entity.id)])
            if exists:
                exists.unlink()

        res = super(CrmEntity, self).unlink()

        return res


class CrmEntityContact(models.Model):
    _inherit = "s2u.crm.entity.contact"

    mailinglist_ids = fields.Many2many(
        'mail.mass_mailing.list', 's2u_mass_mailing_contact_list_rel',
        'contact_id', 'list_id', string='Mailing Lists')

    @api.multi
    def write(self, vals):

        res = super(CrmEntityContact, self).write(vals)

        for contact in self:
            if not contact.mailinglist_ids and 'mailinglist_ids' not in vals:
                continue

            if not ('mailinglist_ids' in vals or 'email' in vals or 'name' in vals):
                continue
            email = vals.get('email', contact.email)
            if vals.get('mailinglist_ids'):
                mailinglist_ids = vals['mailinglist_ids']
            else:
                mailinglist_ids = [(6, 0, contact.mailinglist_ids.ids)]
            name = contact.communication if contact.communication else contact.name
            mailing_vals = {
                'name': name,
                'company_name': contact.entity_id.name,
                'email': email,
                'list_ids': mailinglist_ids,
                's2u_model': 's2u.crm.entity.contact',
                's2u_res_id': contact.id
            }
            exists = self.env['mail.mass_mailing.contact'].search([('s2u_model', '=', 's2u.crm.entity.contact'),
                                                                   ('s2u_res_id', '=', contact.id)], limit=1)
            if exists:
                exists.write(mailing_vals)
            else:
                self.env['mail.mass_mailing.contact'].create(mailing_vals)

        return res

    @api.model
    def create(self, vals):

        res = super(CrmEntityContact, self).create(vals)

        if res.mailinglist_ids:
            name = res.communication if res.communication else res.name
            mailing_vals = {
                'name': name,
                'company_name': res.entity_id.name,
                'email': res.email,
                'list_ids': vals['mailinglist_ids'],
                's2u_model': 's2u.crm.entity.contact',
                's2u_res_id': res.id
            }
            self.env['mail.mass_mailing.contact'].create(mailing_vals)

        return res

    @api.multi
    def unlink(self):
        for contact in self:
            exists = self.env['mail.mass_mailing.contact'].search([('s2u_model', '=', 's2u.crm.entity.contact'),
                                                                   ('s2u_res_id', '=', contact.id)])
            if exists:
                exists.unlink()

        res = super(CrmEntityContact, self).unlink()

        return res



