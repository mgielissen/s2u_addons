# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class Users(models.Model):
    _inherit = 'res.users'

    @api.onchange('image')
    def _onchange_image(self):

        self.gdpr_profile_picture = False

    gdpr_profile_picture = fields.Boolean(string='Uploading the profile picture is on a voluntary basis. The profile picture is only visible within the Odoo ERP and can be viewed by colleagues within the system. You can delete your profile photo yourself at any time.', default=False)

    @api.multi
    def write(self, vals):
        if 'image' in vals:
            if vals.get('image', False):
                for user in self:
                    if vals['image'] != user.image:
                        if 'gdpr_profile_picture' in vals:
                            if not vals.get('gdpr_profile_picture', False):
                                raise UserError(_('You need to agree with the GDPR for uploading your profile picture!'))
                        else:
                            if not user.gdpr_profile_picture:
                                raise UserError(_('You need to agree with the GDPR for uploading your profile picture!'))
        elif 'gdpr_profile_picture' in vals:
            for user in self:
                if user.image and not vals.get('gdpr_profile_picture'):
                    raise UserError(_('You need to agree with the GDPR for uploading your profile picture!'))

        return super(Users, self).write(vals)

    @api.model
    def create(self, vals):

        if vals.get('image', False):
            if not vals.get('gdpr_profile_picture', False):
                raise UserError(_('You need to agree with the GDPR for uploading your profile picture!'))

        return super(Users, self).create(vals)

