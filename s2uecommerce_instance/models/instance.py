# -*- coding: utf-8 -*-

import logging
import datetime
import uuid
import random
import http.client
import urllib
import html2text
import xmlrpc.client

from odoo.osv import expression
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Instance(models.Model):
    _name = "s2u.instance"
    _description = "Instance"

    @api.multi
    def create_and_send_quotation(self, email):

        self.ensure_one()

        entity_vals = {
            'company_id': self.company_id.id,
            'type': 'b2b',
            'name': email,
            'email': email,
            'c_of_c ': email,
            'entity_code': email,
            'tag_ids': [(6, 0, [self.tag_id.id])]
        }
        entity = self.env['s2u.crm.entity'].sudo().create(entity_vals)

        address_vals = {
            'company_id': self.company_id.id,
            'entity_id': entity.id,
            'address': email,
        }
        address = self.env['s2u.crm.entity.address'].sudo().create(address_vals)

        contact_vals = {
            'company_id': self.company_id.id,
            'entity_id': entity.id,
            'address_id': address.id,
            'name': email,
            'prefix': _('T.a.v. %s' % email),
            'communication': _('Geachte %s,' % email),
            'email': email,
        }
        contact = self.env['s2u.crm.entity.contact'].sudo().create(contact_vals)

        vals = {
            'company_id': self.company_id.id,
            'type': 'b2b',
            'partner_id': entity.id,
            'contact_id': contact.id,
            'address_id': address.id,
            'invoice_is_sale_address': True,
            'delivery_is_sale_address': True,
            'reference': _('Activate instance'),
            'create_instance': True,
            'instance_id': self.id
        }
        quotation = self.env['s2u.sale'].create(vals)
        product = self.env['s2u.baseproduct.item'].sudo().search([('res_model', '=', self.service_id._name),
                                                                  ('res_id', '=', self.service_id.id)], limit=1)

        sale_line = {
            'sale_id': quotation.id,
            'product_id': product.id
        }
        sale_line = self.env['s2u.sale.line'].create(sale_line)

        price_info = self.service_id.get_product_price('1 x', False)

        qty_line = {
            'saleline_id': sale_line.id,
            'qty': '1 x',
            'price': price_info['price'],
            'price_per': price_info['price_per'],
            'for_order': True
        }
        self.env['s2u.sale.line.qty'].create(qty_line)

        self.confirm_template_id.send_mail(quotation.id, force_send=False)

        return True

    @api.multi
    def pushover_alert(self, partner_ids, sale):

        for partner_id in partner_ids:
            user = self.env['res.users'].sudo().search([('partner_id', '=', partner_id)])
            if user and user.pushover_user_key and user.company_id.pushover_app_key:
                try:
                    conn = http.client.HTTPSConnection("api.pushover.net:443")
                    body = 'A new instance is activated for %s' % sale.use_email_address
                    conn.request("POST", "/1/messages.json",
                                 urllib.parse.urlencode({
                                     "token": user.company_id.pushover_app_key,
                                     "user": user.pushover_user_key,
                                     "message": body,
                                     "title": 'New instance for %s' % user.company_id.name
                                 }), {"Content-type": "application/x-www-form-urlencoded"})
                    conn.getresponse()
                except:
                    pass
        return True

    @api.multi
    def activate_instance_and_send_login_info(self, sale):

        urlDB = 'http://%s:%d/xmlrpc/db' % (self.instance_server, self.instance_port)
        urlCommon = 'http://%s:%d/xmlrpc/common' % (self.instance_server, self.instance_port)
        urlObject = 'http://%s:%d/xmlrpc/object' % (self.instance_server, self.instance_port)

        sockCommon = xmlrpc.client.ServerProxy(urlCommon)
        sockObject = xmlrpc.client.ServerProxy(urlObject)

        sockDB = xmlrpc.client.ServerProxy(urlDB)
        new_db = datetime.datetime.now()
        new_db = 'db%s%s' % (new_db.strftime('%Y%m%d%H%M'), uuid.uuid4().hex[:6].upper())

        sockDB.duplicate_database(self.master_password, self.instance_db, new_db)

        s = "abcdefghijklmnopqrstuvwxyz01234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()?"
        passlen = 8
        admin_password = "".join(random.sample(s, passlen))

        uid = sockCommon.login(new_db, self.admin_user, self.admin_password)
        sockObject.execute(new_db, uid, self.admin_password, 'res.users', 'write', 1, {'password': admin_password})

        sale.write({
            'instance_db': new_db,
            'instance_admin_pw': admin_password
        })

        self.activated_template_id.send_mail(sale.id, force_send=False)

        users = self.env['res.users'].sudo().search([('pushover_user_key', '!=', False),
                                                     ('pushover_leads', '=', True)])
        if users:
            partner_ids = [u.partner_id.id for u in users]
            try:
                self.pushover_alert(partner_ids, sale)
            except:
                pass

        return True

    name = fields.Char(string='Instance', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    service_id = fields.Many2one('s2u.subscription.template', string='Service', required=True, ondelete='restrict')
    description = fields.Html(string='Description')
    active = fields.Boolean('Active', default=True)
    instance_server = fields.Char(string='Server', required=True)
    instance_port = fields.Integer(string='Port', required=True)
    instance_db = fields.Char(string='Database', required=True)
    master_password = fields.Char(string='Master PW', default='', invisible=True)
    admin_user = fields.Char(string='Admin user', required=True)
    admin_password = fields.Char(string='Admin PW', default='', invisible=True)
    confirm_template_id = fields.Many2one('mail.template', string='Confirm template', ondelete='restrict',
                                          domain=[('model', '=', 's2u.sale')], required=True)
    activated_template_id = fields.Many2one('mail.template', string='Activated template', ondelete='restrict',
                                            domain=[('model', '=', 's2u.sale')], required=True)
    tag_id = fields.Many2one('s2u.crm.tag', string='CRM tag', required=True, ondelete='restrict')
