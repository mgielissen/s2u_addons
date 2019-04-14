# -*- coding: utf-8 -*-

import logging
import http.client
import urllib
import html2text

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class Message(models.Model):
    _inherit = 'mail.message'

    def pushover_push_message(self, partner_ids, message):

        for partner_id in partner_ids:
            user = self.env['res.users'].sudo().search([('partner_id', '=', partner_id)])
            if user and user.pushover_user_key and user.company_id.pushover_app_key:
                try:
                    conn = http.client.HTTPSConnection("api.pushover.net:443")
                    body = html2text.html2text(message.body)
                    conn.request("POST", "/1/messages.json",
                                 urllib.parse.urlencode({
                                     "token": user.company_id.pushover_app_key,
                                     "user": user.pushover_user_key,
                                     "message": body,
                                     "title": message.subject if message.subject else ''
                                 }), {"Content-type": "application/x-www-form-urlencoded"})
                    conn.getresponse()
                except:
                    pass
        return True

    @api.model
    def create(self, values):

        pushover_ids = []

        res = super(Message, self).create(values)

        if res._name not in ['mail.compose.message']:
            try:
                if hasattr(res, 'channel_ids') and res.message_type == 'comment' and res.channel_ids:
                    users = self.env['res.users'].sudo().search([('pushover_user_key', '!=', False),
                                                                 ('pushover_messages', '=', True)])
                    if not users:
                        return res
                    partner_ids = [u.partner_id.id for u in users]
                    for channel in res.channel_ids:
                        if set(pushover_ids) == set(partner_ids):
                            break
                        if channel.channel_type not in ['chat', 'channel']:
                            continue
                        if not channel.channel_partner_ids:
                            continue
                        for id in partner_ids:
                            if res.author_id and res.author_id.id == id:
                                continue
                            if id in channel.channel_partner_ids.ids:
                                pushover_ids.append(id)
                elif res.message_type == 'comment':
                    users = self.env['res.users'].sudo().search([('pushover_user_key', '!=', False),
                                                                 ('pushover_messages', '=', True)])
                    if not users:
                        return res
                    partner_ids = [u.partner_id.id for u in users]
                    notify = self.env['mail.notification'].sudo().search([('mail_message_id', '=', res.id)])
                    partner_notify_ids = [n.res_partner_id.id for n in notify]
                    for id in partner_ids:
                        if id in partner_notify_ids:
                            pushover_ids.append(id)
                pushover_ids = list(set(pushover_ids))
                if pushover_ids:
                    self.pushover_push_message(pushover_ids, res)
            except:
                if res:
                    _logger.info('Error on checking pushover for message with id %s', res.id)

        return res