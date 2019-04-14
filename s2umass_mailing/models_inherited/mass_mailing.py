# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

MASS_MAILING_BUSINESS_MODELS = [
    'event.registration',
    'hr.applicant',
    'event.track',
    'mail.mass_mailing.list',
    's2u.crm.entity',
    's2u.crm.entity.contact',
    's2u.crm.lead',
    's2u.project'
]


class MassMailing(models.Model):

    _inherit = 'mail.mass_mailing'

    mailing_model_id = fields.Many2one(domain=[('model', 'in', MASS_MAILING_BUSINESS_MODELS)])


class MassMailingContact(models.Model):

    _inherit = 'mail.mass_mailing.contact'

    s2u_model = fields.Char('Model', index=True)
    s2u_res_id = fields.Integer('Res-Id', index=True)

