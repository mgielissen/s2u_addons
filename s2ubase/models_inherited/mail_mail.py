# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MailMail(models.Model):

    _inherit = 'mail.mail'

    @api.model
    def create(self, values):

        # we set the header "references" to the message ID. Some mail servers overwrite Message-ID
        res = super(MailMail, self).create(values)
        if not values.get('references', False):
            res.write({
                'references': res.message_id
            })

        return res
