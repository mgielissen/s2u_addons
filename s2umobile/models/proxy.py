# -*- coding: utf-8 -*-

import datetime

import html2text
from odoo.addons.web_editor.models.ir_qweb import html_to_text
from odoo import api, fields, models, _


def float_to_time(value):
    ivalue = int(value)
    return "%02d:%02d" % (ivalue, (value - ivalue) * 60)

class MobileProxy(models.Model):
    _name = "s2u.mobile.proxy"

    def _make_number_callable(self, number):

        if not number:
            return False

        res = ''
        skip = False
        for n in number:
            if n == '(':
                skip = True
                continue
            if n == ')':
                skip = False
                continue
            if skip:
                continue
            res += n

        return res

    def fetch_messages(self, res_model, res_id):

        res = []

        messages = self.env['mail.message'].sudo().search([('model', '=', res_model),
                                                           ('res_id', '=', res_id)], limit=25)
        for m in messages:
            body = html2text.html2text(m.body)
            if body and len(body) > 20:
                short_body = '%s ...' % body[:20]
            else:
                short_body = body
            res.append({
                'msg_id': m.id,
                'author': m.author_id.name if m.author_id else m.email_from,
                'date': m.date,
                'body': body,
                'short_body': short_body
            })
        return res

    def _prepare_contact_dict(self, res_model, contact):

        if res_model == 's2u.crm.entity':
            vals = {
                'id': 'entity:%d' % contact.id,
                'res_id': contact.id,
                'res_model': res_model,
                'name': contact.name,
                'company': contact.name,
                'phone': contact.phone,
                'phone_callable': self._make_number_callable(contact.phone),
                'mobile': contact.mobile,
                'mobile_callable': self._make_number_callable(contact.mobile),
                'email': contact.email,
                'favorite': contact.is_favorite,
                'type': 'c' if contact.type == 'b2b' else 'p',
                'messages': [],
            }
        else:
            vals = {
                'id': 'contact:%d' % contact.id,
                'res_id': contact.id,
                'res_model': res_model,
                'name': contact.name,
                'company': contact.entity_id.name,
                'phone': contact.phone,
                'phone_callable': self._make_number_callable(contact.phone),
                'mobile': contact.mobile,
                'mobile_callable': self._make_number_callable(contact.mobile),
                'email': contact.email,
                'favorite': contact.is_favorite,
                'type': 'p',
                'messages': [],
            }

        vals['messages'] = self.fetch_messages(res_model, contact.id)

        return vals

    @api.multi
    def fetch_favorites(self):

        favorites = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id)])
        res = []
        for fav in favorites:
            if fav.res_model == 's2u.crm.entity':
                entity = self.env['s2u.crm.entity'].browse(fav.res_id)
                res.append(self._prepare_contact_dict(fav.res_model, entity))
            if fav.res_model == 's2u.crm.entity.contact':
                contact = self.env['s2u.crm.entity.contact'].browse(fav.res_id)
                res.append(self._prepare_contact_dict(fav.res_model, contact))
        return res

    @api.multi
    def search_contacts(self, name):

        enities = self.env['s2u.crm.entity'].search([('name', 'ilike', name)], limit=25)
        contacts = self.env['s2u.crm.entity.contact'].search([('name', 'ilike', name)], limit=25)

        res = []
        for entity in enities:
            res.append(self._prepare_contact_dict('s2u.crm.entity', entity))

        for contact in contacts:
            res.append(self._prepare_contact_dict('s2u.crm.entity.contact', contact))

        return res

    @api.multi
    def fetch_leads(self):

        # we take max. 25 leads and always the latest on top
        leads = self.env['s2u.crm.lead'].search([('state', '=', 'new')], limit=25, order='date_lead desc')
        res = []
        for lead in leads:
            res.append({
                'id': 'lead:%d' % lead.id,
                'company_name': lead.company_name,
                'contact_name': lead.contact_name,
                'phone': lead.phone,
                'phone_callable': self._make_number_callable(lead.phone),
                'mobile': lead.mobile,
                'mobile_callable': self._make_number_callable(lead.mobile),
                'email': lead.email,
                'info': lead.info
            })

        return res

    @api.multi
    def _cockpit_prepare_channel(self, channel):

        preview = ''
        res = channel.channel_fetch_preview()
        if res and res[0]['last_message']:
            res = res[0]['last_message']
            author = res['author_id'][1] if res.get('author_id', False) else ''
            m = html2text.html2text(res['body'])
            if m and len(m) > 20:
                m = '%s ...' % m[:20]
            if author:
                preview = '%s: %s' % (author, m)
            else:
                preview = m

        c = {
            'name': channel.name,
            'type': 'channel',
            'channel_id': channel.id,
            'new_messages': channel.message_unread_counter,
            'preview': preview,
            'messages': []
        }

        messages = channel.channel_fetch_message(limit=25)
        for m in messages:
            c['messages'].append({
                'msg_id': m['id'],
                'author': m['author_id'][1] if m.get('author_id', False) else '',
                'date': m['date'],
                'body': html2text.html2text(m['body'])
            })

        return c

    @api.multi
    def _cockpit_prepare_inbox(self):

        c = {
            'name': 'Inbox',
            'type': 'mail',
            'new_messages': self.env['res.partner'].get_needaction_count(),
            'preview': '',
            'messages': []
        }

        notifications = self.env['mail.notification'].sudo().search([
            ('res_partner_id', '=', self.env.user.partner_id.id)], order='mail_message_id desc')
        if notifications:
            m = html2text.html2text(notifications[0].mail_message_id.body)
            if m and len(m) > 20:
                m = '%s ...' % m[:20]
            if notifications[0].mail_message_id.author_id:
                preview = '%s: %s' % (notifications[0].mail_message_id.author_id.name, m)
            elif notifications[0].mail_message_id.email_from:
                preview = '%s: %s' % (notifications[0].mail_message_id.email_from, m)
            else:
                preview = m
            c['preview'] = preview
            for n in notifications:
                body = html2text.html2text(n.mail_message_id.body)
                if body and len(body) > 20:
                    short_body = '%s ...' % body[:20]
                else:
                    short_body = body
                c['messages'].append({
                    'msg_id': n.mail_message_id.id,
                    'author': n.mail_message_id.author_id.name if n.mail_message_id.author_id else n.mail_message_id.email_from,
                    'date': n.mail_message_id.date,
                    'body': body,
                    'short_body': short_body
                })

        return c

    @api.multi
    def fetch_cockpit(self):

        PRIORITIES = {
            '30': 'Low',
            '20': 'Normal',
            '10': 'High'
        }

        cockpit = {
            'tasks': {
                'open_tasks': 0,
                'hours_written': '0:00',
                'tasks': []
            },
            'messages': {
                'new_messages': 0,
                'channels': []
            },
        }

        domain = [('responsible_id', '=', self.env.user.id), ('state', '=', 'open')]
        tasks = self.env['s2u.project.task'].search(domain)
        cockpit['tasks']['open_tasks'] = len(tasks)
        for task in tasks:
            cockpit['tasks']['tasks'].append({
                'task_id': task.id,
                'name': task.name,
                'project': task.project_id.name,
                'role': task.rate_id.name,
                'responsible': task.responsible_id.name,
                'priority': PRIORITIES[task.priority],
                'descript': task.descript,
                'descript_short': task.descript_short,
                'written': float_to_time(task.hours_written),
                'forecast': float_to_time(task.task_forecast),
                'tot_open': float_to_time(task.hours_to_spend),
                'tot_forecast': float_to_time(task.rolling_forecast),
                'messages': self.fetch_messages('s2u.project.task', task.id)
            })

        # filter hours for current month
        tillm = datetime.date.today().month
        tilly = datetime.date.today().year
        date_from = datetime.date(tilly, tillm, 1)
        if tillm < 12:
            tillm += 1
        else:
            tillm = 1
            tilly += 1
        date_till = datetime.date(tilly, tillm, 1) - datetime.timedelta(days=1)

        domain = [('user_id', '=', self.env.user.id),
                  ('date', '>=', date_from),
                  ('date', '<=', date_till)]
        hours = self.env['s2u.project.hour'].search(domain)
        hours_written = sum(h.hours for h in hours)
        cockpit['tasks']['hours_written'] = float_to_time(hours_written)

        if self.env['res.partner'].get_needaction_count():
            cockpit['messages']['new_messages'] += self.env['res.partner'].get_needaction_count()
            channel = self._cockpit_prepare_inbox()
            cockpit['messages']['channels'].append(channel)

        domain = [('partner_id', '=', self.env.user.partner_id.id)]
        channels = self.env['mail.channel.partner'].search(domain)
        for channel_partner in channels:
            if channel_partner.channel_id.channel_type in ['chat', 'channel']:
                if channel_partner.channel_id.message_unread:
                    cockpit['messages']['new_messages'] += channel_partner.channel_id.message_unread_counter
                cockpit['messages']['channels'].append(self._cockpit_prepare_channel(channel_partner.channel_id))
        return cockpit

    @api.multi
    def contact_favorite(self, contact_id, fav):

        id = contact_id.split(':')
        if id[0] == 'entity':
            contact = self.env['s2u.crm.entity'].browse(int(id[1]))
        elif id[0] == 'contact':
            contact = self.env['s2u.crm.entity.contact'].browse(int(id[1]))
        else:
            contact = False

        if contact:
            if fav:
                return contact.action_make_favorite()
            else:
                return contact.action_undo_favorite()

        return False

    @api.multi
    def send_channel_message(self, channel_id, message):

        channel = self.env['mail.channel'].browse(channel_id)
        res = channel.message_post(body=message, message_type="comment", subtype="mail.mt_comment")
        if res:
            return res.id
        else:
            return False

    @api.multi
    def send_inbox_message(self, msg_id, msg_type, message):

        mail_message = self.env['mail.message'].browse(msg_id)
        obj = self.env[mail_message.model].browse(mail_message.res_id)
        if msg_type == 'note':
            res = obj.message_post(body=message)
            return res.id
        elif msg_type == 'reply':
            res = obj.message_post(body=message, message_type="comment", subtype="mail.mt_comment")
            return res.id
        else:
            return False

    @api.multi
    def set_message_done(self, msg_id):

        mail_message = self.env['mail.message'].browse(msg_id)
        mail_message.set_message_done()
        return True

    @api.multi
    def fetch_channel(self, channel_id):

        channel = self.env['mail.channel'].browse(channel_id)
        if channel:
            channel.channel_seen()
            channel = self._cockpit_prepare_channel(channel)
            return channel

        return False

    @api.multi
    def fetch_inbox(self):

        inbox = self._cockpit_prepare_inbox()
        return inbox

    @api.multi
    def channel_seen(self, channel_id):

        channel = self.env['mail.channel'].browse(channel_id)
        if channel:
            channel.channel_seen()
            return True

        return False

    @api.multi
    def send_message(self, res_model, res_id, msg_type, message):

        obj = self.env[res_model].browse(res_id)
        if msg_type == 'note':
            res = obj.message_post(body=message)
            return self.fetch_messages(res_model, res_id)
        elif msg_type == 'message':
            res = obj.message_post(body=message, message_type="comment", subtype="mail.mt_comment")
            return self.fetch_messages(res_model, res_id)
        else:
            return []

    @api.multi
    def task_write_hours(self, task_id, task_data):

        def time_to_float(t):
            try:
                if ':' not in t:
                    t = '%s:00' % t
                t = t.split(':')
                hours = int(t[0])
                min = int(t[1])
                return float(hours) + min / 60.0
            except:
                return False

        task = self.env['s2u.project.task'].browse(task_id)
        projectrate = self.env['s2u.project.stage.role'].search([('project_id', '=', task.project_id.id),
                                                                 ('stage_id', '=', task.stage_id.id),
                                                                 ('rate_id', '=', task.rate_id.id)], limit=1)

        if task_data['fld_zone'] == 'After hours':
            zone = 'zone2'
        elif task_data['fld_zone'] == 'Sat. and Sun.':
            zone = 'zone3'
        elif task_data['fld_zone'] == 'Holidays':
            zone = 'zone4'
        else:
            zone = 'zone1'

        hours = time_to_float(task_data['fld_hours'])
        if not hours:
            return False, 'Invalid value for hours.'

        hours_vals = {
            'project_id': task.project_id.id,
            'projectrate_id': projectrate.id,
            'name': task_data['fld_descript'],
            'hours': hours,
            'zone': zone,
            'task_id': task.id,
            'task_state': 'open' if task_data['fld_task_open'] else 'closed'
        }

        if task_data['fld_forecast']:
            forecast = time_to_float(task_data['fld_forecast'])
            if not forecast:
                return False, 'Invalid value for forecast.'
            hours_vals['task_forecast'] = forecast

        self.env['s2u.project.hour'].create(hours_vals)

        return_data = {
            'written': float_to_time(task.hours_written),
            'forecast': float_to_time(task.task_forecast),
            'tot_open': float_to_time(task.hours_to_spend),
            'tot_forecast': float_to_time(task.rolling_forecast),
            'messages': self.fetch_messages('s2u.project.task', task.id)
        }
        return return_data, 'ok'

