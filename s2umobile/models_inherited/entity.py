# -*- coding: utf-8 -*-

import http.client, urllib
import html2text

from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "s2u.crm.lead"

    def pushover_alert_lead(self, partner_ids, lead):

        for partner_id in partner_ids:
            user = self.env['res.users'].sudo().search([('partner_id', '=', partner_id)])
            if user and user.pushover_user_key and user.company_id.pushover_app_key:
                try:
                    conn = http.client.HTTPSConnection("api.pushover.net:443")
                    body = html2text.html2text(lead.info) if lead.info else 'No additional info.'
                    body = '%s\n================\n%s' % (lead.contact_name if lead.contact_name else lead.company_name,
                                                         body)
                    if lead.phone:
                        body = '%s\n\nphone: %s' % (body, lead.phone)
                    if lead.mobile:
                        body = '%s\n\nmobile: %s' % (body, lead.mobile)
                    if lead.email:
                        body = '%s\n\nemail: %s' % (body, lead.email)
                    conn.request("POST", "/1/messages.json",
                                 urllib.parse.urlencode({
                                     "token": user.company_id.pushover_app_key,
                                     "user": user.pushover_user_key,
                                     "message": body,
                                     "title": 'New lead for %s' % user.company_id.name
                                 }), {"Content-type": "application/x-www-form-urlencoded"})
                    conn.getresponse()
                except:
                    pass
        return True

    @api.model
    def create(self, values):

        res = super(CrmLead, self).create(values)

        if res.company_name or res.contact_name:
            users = self.env['res.users'].sudo().search([('pushover_user_key', '!=', False),
                                                         ('pushover_leads', '=', True)])
            if not users:
                return res

            partner_ids = [u.partner_id.id for u in users]

            self.pushover_alert_lead(partner_ids, res)

        return res
