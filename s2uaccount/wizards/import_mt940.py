# -*- coding: utf-8 -*-

import base64
import time
import datetime
import re
import string
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ImportMT940(models.TransientModel):
    _name = "wizard.import.mt940"
    _description = "Import MT940"

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    mt940_data = fields.Binary(string='Content', required=True)
    mt940_fname = fields.Char(string='Filename')

    def optimize_data(self, tag_regex):
        """Deze routine zorgt ervoor dat de inhoud van een tag verdeeld
        over meerdere regels, 1 regel wordt. Dit maakt het makkelijker
        om de data te analyseren."""

        data = StringIO(base64.b64decode(self.mt940_data))
        header = True
        optimized = []
        line_opt = False
        for line in data:
            if header:
                if line and line[0] != ':':
                    continue
                else:
                    header = False
            m = re.match(tag_regex, line)
            if m:
                if line_opt:
                    optimized.append(line_opt.replace('\r', '').replace('\n', ''))
                    line_opt = False
                tag = m.group(0).strip(':')
                if tag == '62F':
                    optimized.append(line.replace('\r', '').replace('\n', ''))
                    header = True
                else:
                    line_opt = line
            elif line_opt:
                line_opt += line
            else:
                line_opt = line
        return optimized

    def match_bank_account(self):

        account_model = self.env['s2u.account.account']

        tag_regex = '^:[0-9]{2}[A-Z]*:'
        optimized = self.optimize_data(tag_regex)
        for line in optimized:
            m = re.match(tag_regex, line)
            try:
                tag = m.group(0).strip(':')
            except:
                continue

            if tag != '25':
                continue

            content = line[m.end():].strip()

            if ' ' in content:
                content = content.split(' ')
                content = content[0]

            all = string.maketrans('', '')
            nodigs = all.translate(all, string.digits)
            content = content.translate(all, nodigs)
            accounts = account_model.search([('company_id', '=', self.company_id.id),
                                             ('type', '=', 'bank')])
            for account in accounts:
                if not account.bank_account:
                    continue
                check_number = str(account.bank_account)
                check_number = check_number.translate(all, nodigs)
                if content in check_number:
                    return account

        return False

    def get_regex_tag61(self, account):

        if account.mt940_format in ['abnamro', 'abnamro2']:
            return '^(?P<date>\d{6})(?P<date2>\d{4})(?P<sign>[CD])' + \
                   '(?P<amount>\d+,\d{0,2})N(?P<type>\d{3})' + \
                   '(?P<reference>\w{1,16})'
        elif account.mt940_format == 'rabo':
            return '^(?P<date>\d{6})(?P<sign>[CD])' + \
                   '(?P<amount>\d+,\d{0,2})N(?P<type>\w{3})' + \
                   '(?P<reference>.{1,16})' + \
                   '(?P<remote_account>.{0,16})'
        elif account.mt940_format == 'ing':
            return '^(?P<date>\d{6})(?P<sign>[CD])' + \
                   '(?P<amount>\d+,\d{0,2})N(?P<type>\w{2})' + \
                   ' (?P<reference>\w{1,16})'
        elif account.mt940_format == 'ing2':
            return '^(?P<date>\d{6})(?P<date2>\d{4})(?P<sign>[CD])' + \
                   '(?P<amount>\d+,\d{0,2})N(?P<type>\w{2})' + \
                   '(?P<reference>.*)'
        else:
            return False

    def get_60F_saldo(self, content):
        try:
            amount = content[10:]
            amount = abs(float(amount.replace(',', '.')))
            if content[0] == 'D':
                amount *= -1.0
            return amount
        except:
            return False

    def get_60F_date(self, content):
        try:
            date = content[1:7]
            date = datetime.datetime.strptime(date, '%y%m%d')
            date = date.strftime('%Y-%m-%d')
            return date
        except:
            return False

    # Deze routine verwerkt de ':86:' regel uit het mt940 bestand.
    def parse_close_tag(self, content):

        keywords = ['ORDP', 'NAME', 'REMI', 'ISDT', 'TRTP', 'IBAN', 'BIC', 'EREF', 'ID', 'CNTP', 'MARF']
        translations = {'ORDP': 'ORDP',
                        'NAME': 'remote_owner',
                        'REMI': 'message',
                        'ISDT': 'ISDT',
                        'TRTP': 'TRTP',
                        'IBAN': 'remote_account',
                        'BIC': 'remote_bank_bic',
                        'EREF': 'EREF',
                        'ID': 'ID',
                        'CNTP': 'CNTP',
                        'MARF': 'MARF'}
        parsed = {}
        words = content.split('/')
        keymatch = False
        for w in words:
            if w in keywords:
                keymatch = w
            elif keymatch:
                translate = translations[keymatch]
                if translate in parsed:
                    parsed[translate] = '%s/%s' % (parsed[translate], w)
                else:
                    parsed[translate] = w

                    # ING specific
        if parsed.get('CNTP', False):
            words = parsed['CNTP'].split('/')
            labels = ['remote_account', 'remote_bank_bic', 'remote_owner']
            for idx, value in enumerate(words):
                try:
                    parsed[labels[idx]] = value
                except:
                    pass

        if not parsed:
            return {'message': content}
        else:
            if not 'message' in parsed:
                parsed['message'] = content
            return parsed

    def parse_close_tag_abn2(self, content):

        keywords = ['IBAN:', 'INCASSANT:', 'NAAM:', 'MACHTIGING:', 'OMSCHRIJVING:', 'BIC:', 'KENMERK:']

        translations = {'ORDP': 'ORDP',
                        'NAAM:': 'remote_owner',
                        'OMSCHRIJVING:': 'message',
                        'ISDT': 'ISDT',
                        'TRTP': 'TRTP',
                        'IBAN:': 'remote_account',
                        'INCASSANT:': 'remote_account',
                        'BIC:': 'remote_bank_bic',
                        'KENMERK:': 'EREF',
                        'MACHTIGING:': 'ID',
                        'CNTP': 'CNTP'}

        # SEPA OVERBOEKING                 IBAN: NL46RABO0342352288BIC: RABONL2U                    NAAM: M. TIMMERMAN EOOMSCHRIJVING: LIDMAATSCHAP 2016,  M. TIMMERMAN, DE LIJNBAAN 4KENMERK: NOTPROVIDED
        i = 0
        data = False
        key = False
        parsed = {}
        while i < len(content):
            for k in keywords:
                if content[i:].startswith(k):
                    if key and data:
                        parsed[translations[key]] = data.strip()
                    elif data:
                        parsed['EREF'] = data.strip()
                    data = False
                    key = k
                    i += len(k)
                    break
            if i < content:
                if data:
                    data += content[i]
                else:
                    data = content[i]
                i += 1
        if key and data:
            parsed[translations[key]] = data.strip()
        elif data:
            parsed['EREF'] = data.strip()

        if not parsed:
            return {'message': content}
        else:
            if not 'message' in parsed:
                parsed['message'] = content
            return parsed

    def parse_transaction(self, mt940_format, tag_61_regex, tag, content, record):

        if tag == '28':
            record['descript'] = content
        if tag == '60F':
            # beginsaldo
            # C140605EUR116,36
            record['startsaldo'] = self.get_60F_saldo(content)
            record['entry_date'] = self.get_60F_date(content)
        if tag == '61':
            parsed_data = tag_61_regex.match(content).groupdict()
            if not 'tag61' in record:
                record['tag61'] = []
                record['tag86'] = []
            if parsed_data.get('reference', False):
                parsed_data['reference'] = parsed_data['reference'].strip()
            if parsed_data.get('remote_account', False):
                parsed_data['remote_account'] = parsed_data['remote_account'].strip()
            record['tag61'].append(parsed_data)
            record['tag86'].append(False)
        if tag == '86':
            if mt940_format == 'abn2':
                record['tag86'][-1] = self.parse_close_tag_abn2(content)
            else:
                record['tag86'][-1] = self.parse_close_tag(content)
        return record

    def get_tag61_amount(self, content):
        try:
            amount = content['amount']
            amount = abs(float(amount.replace(',', '.')))
            if content['sign'] == 'D':
                amount *= -1.0
            return amount
        except:
            return False

    def get_tag61_date(self, content):
        try:
            date = content['date']
            date = datetime.datetime.strptime(date, '%y%m%d')
            date = date.strftime('%Y-%m-%d')
            return date
        except:
            return False

    @api.multi
    def do_import_mt940(self):
        self.ensure_one()

        bank_model = self.env['s2u.account.bank']
        bank_line_model = self.env['s2u.account.bank.line']

        bank_account = self.match_bank_account()
        if not bank_account:
            raise ValueError(_("Bank not defined in your accounts."))
        if not bank_account.mt940_format:
            raise ValueError(_("No MT940 format defined for account %s" % bank_account.bank_account))

        tag61_regex = self.get_regex_tag61(bank_account)
        if not tag61_regex:
            raise ValueError(_("This MT940 format is not supported"))
        tag_61_regex = re.compile(tag61_regex)

        tag_regex = '^:[0-9]{2}[A-Z]*:'
        optimized = self.optimize_data(tag_regex)
        record = {}
        records = []
        for line in optimized:
            m = re.match(tag_regex, line)
            try:
                tag = m.group(0).strip(':')
            except:
                continue

            # deze is al verwerkt om de juiste bank (match_bank_account) te vinden
            if tag == '25':
                continue

            content = line[m.end():].strip()
            record = self.parse_transaction(bank_account.mt940_format, tag_61_regex, tag, content, record)
            if tag == '62F':
                if not record.get('tag61', False):
                    record = {}
                    continue

                records.append(record)
                record = {}

        bank_statement = bank_model.create({
            'name': self.mt940_fname,
            'account_id': bank_account.id,
            'start_saldo': bank_account.saldo_per_date(False)
        })

        for record in records:
            for i, tag61 in enumerate(record['tag61']):
                try:
                    if record['tag86'][i].get('remote_account', False):
                        acc_number = record['tag86'][i].get('remote_account')
                    elif record['tag61'][i].get('remote_account', False):
                        acc_number = record['tag61'][i].get('remote_account')
                    else:
                        acc_number = False
                except:
                    acc_number = False

                line_vals = {
                    'bank_id': bank_statement.id,
                    'gross_amount': self.get_tag61_amount(tag61),
                    'net_amount': self.get_tag61_amount(tag61),
                    'vat_amount': 0.0,
                    'date_trans': self.get_tag61_date(tag61),
                    'descript': record['tag86'][i].get('message', False),
                    'mt940_bank_number': acc_number,
                    'mt940_bank_owner': record['tag86'][i].get('remote_owner', False),
                    'mt940_eref': record['tag86'][i].get('EREF', False),
                }
                bank_line_model.create(line_vals)

        action_rec = self.env['ir.model.data'].xmlid_to_object('s2uaccount.bank_form')
        if action_rec:
            return {
                'type': 'ir.actions.act_window',
                'name': _(''),
                'res_model': 's2u.account.bank',
                'res_id': bank_statement.id,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': action_rec.id,
                'target': 'current',
                'nodestroy': True,
            }

