import datetime
from odoo import api, fields, models

class PrintReportLedger(models.AbstractModel):
    _name = 'report.s2uaccount.report_ledger'

    @api.model
    def get_report_values(self, docids, data=None):

        account_model = self.env['s2u.account.account']
        bank_model = self.env['s2u.account.bank.account']
        memorial_model = self.env['s2u.account.memorial.account']
        invoice_so_model = self.env['s2u.account.invoice']
        invoice_so_line_model = self.env['s2u.account.invoice.line']
        invoice_po_model = self.env['s2u.account.invoice.po']
        invoice_po_line_model = self.env['s2u.account.invoice.po.line']
        vat_rule_model = self.env['s2u.account.vat.rule']

        company_currency = self.env.user.company_id.currency_id

        date_obj = datetime.datetime.strptime(data['form']['ledger_till'], '%Y-%m-%d')
        lang = self.env['res.lang'].search([('code', '=', self.env.user.lang)])
        date_ledger_till = date_obj.strftime(lang.date_format)

        ledger_from = '%d-01-01' % date_obj.year
        ledger_till = data['form']['ledger_till']

        ledger_accounts = []
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for account in account_model.search([]):
            ledger_account = {
                'code': account.code,
                'name': account.name,
                'transactions': []
            }

            transactions = memorial_model.search([('account_id', '=', account.id),
                                                  ('date_trans', '>=', ledger_from),
                                                  ('date_trans', '<=', ledger_till)])
            for line in transactions:
                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.memorial' % (base_url, line.memorial_id.id)
                debit = round(line.debit, 2)
                credit = round(line.credit, 2)
                vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                if line.currency_id != company_currency:
                    debit = debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                    credit = credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                    if vat_amount:
                        vat_amount = vat_amount * line.currency_id.with_context({
                            'date': line.date_trans
                        }).rate
                trans = {
                    'trans_date': line.date_trans,
                    'description': line.descript if line.descript else account.name,
                    'debit': debit,
                    'credit': credit,
                    'vat_code': line.vat_id.name if line.vat_id else '',
                    'vat_amount': vat_amount,
                    'document': line.memorial_id.name,
                    'document_link': document_link
                }
                ledger_account['transactions'].append(trans)

            transactions = bank_model.search([('account_id', '=', account.id),
                                              ('date_trans', '>=', ledger_from),
                                              ('date_trans', '<=', ledger_till)])
            for line in transactions:
                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.bank' % (base_url, line.bank_id.id)
                debit = round(line.debit, 2)
                credit = round(line.credit, 2)
                vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                if line.currency_id != company_currency:
                    debit = debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                    credit = credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                    if vat_amount:
                        vat_amount = vat_amount * line.currency_id.with_context({
                            'date': line.date_trans
                        }).rate

                trans = {
                    'trans_date': line.date_trans,
                    'description': line.descript if line.descript else account.name,
                    'debit': debit,
                    'credit': credit,
                    'vat_code': line.vat_id.name if line.vat_id else '',
                    'vat_amount': vat_amount,
                    'document': line.bank_id.name,
                    'document_link': document_link
                }
                ledger_account['transactions'].append(trans)

            transactions = invoice_so_model.search([('account_id', '=', account.id),
                                                    ('state', '=', 'invoiced'),
                                                    ('date_financial', '>=', ledger_from),
                                                    ('date_financial', '<=', ledger_till)])
            for line in transactions:
                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.invoice' % (base_url, line.id)
                if line.amount_gross > 0.0:
                    debit = round(line.amount_gross, 2)
                    if line.currency_id != company_currency:
                        debit = debit * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    trans = {
                        'trans_date': line.date_financial,
                        'description': line.reference if line.reference else account.name,
                        'debit': debit,
                        'credit': 0.0,
                        'vat_code': '',
                        'vat_amount': '',
                        'document': line.name,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)
                elif line.amount_gross < 0.0:
                    credit = round(abs(line.amount_gross), 2)
                    if line.currency_id != company_currency:
                        credit = credit * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    trans = {
                        'trans_date': line.date_financial,
                        'description': line.reference if line.reference else account.name,
                        'debit': 0.0,
                        'credit': credit,
                        'vat_code': '',
                        'vat_amount': '',
                        'document': line.name,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)

            transactions = invoice_po_model.search([('account_id', '=', account.id),
                                                    ('state', '=', 'valid'),
                                                    ('date_financial', '>=', ledger_from),
                                                    ('date_financial', '<=', ledger_till)])
            for line in transactions:
                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.invoice.po' % (base_url, line.id)
                if line.name and line.reference:
                    document = '%s / %s' % (line.name, line.reference)
                elif line.name:
                    document = line.name
                elif line.reference:
                    document = line.reference
                else:
                    document = 'PO#%d' % line.id

                if line.amount_gross < 0.0:
                    debit = round(abs(line.amount_gross), 2)
                    if line.currency_id != company_currency:
                        debit = debit * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    trans = {
                        'trans_date': line.date_financial,
                        'description': line.reference if line.reference else account.name,
                        'debit': debit,
                        'credit': 0.0,
                        'vat_code': '',
                        'vat_amount': '',
                        'document': document,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)
                elif line.amount_gross > 0.0:
                    credit = round(line.amount_gross, 2)
                    if line.currency_id != company_currency:
                        credit = credit * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    trans = {
                        'trans_date': line.date_financial,
                        'description': line.reference if line.reference else account.name,
                        'debit': 0.0,
                        'credit': credit,
                        'vat_code': '',
                        'vat_amount': '',
                        'document': document,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)

            used_vats = {}
            rules = vat_rule_model.search([('account_id', '=', account.id)])
            for rule in rules:
                if rule.vat_id.id not in used_vats:
                    used_vats[rule.vat_id.id] = {'type': rule.rule_type,
                                                 'rule': rule.vat_id.rule_vat}

            transactions = invoice_so_line_model.search([('account_id', '=', account.id),
                                                         ('financial_date', '>=', ledger_from),
                                                         ('financial_date', '<=', ledger_till)])
            for line in transactions:
                if line.invoice_id.state != 'invoiced':
                    continue

                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.invoice' % (base_url, line.invoice_id.id)
                if line.net_amount < 0.0:
                    debit = round(abs(line.net_amount), 2)
                    vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                    if line.currency_id != company_currency:
                        debit = debit * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                        if vat_amount:
                            vat_amount = vat_amount * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                    trans = {
                        'trans_date': line.financial_date,
                        'description': line.descript,
                        'debit': debit,
                        'credit': 0.0,
                        'vat_code': line.vat_id.name if line.vat_id else '',
                        'vat_amount': vat_amount,
                        'document': line.invoice_id.name,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)
                elif line.net_amount > 0.0:
                    credit = round(line.net_amount, 2)
                    vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                    if line.currency_id != company_currency:
                        credit = credit * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                        vat_amount = vat_amount * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                    trans = {
                        'trans_date': line.financial_date,
                        'description': line.descript,
                        'debit': 0.0,
                        'credit': credit,
                        'vat_code': line.vat_id.name if line.vat_id else '',
                        'vat_amount': vat_amount,
                        'document': line.invoice_id.name,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)

            transactions = invoice_so_line_model.search([('vat_id', 'in', list(used_vats.keys())),
                                                         ('financial_date', '>=', ledger_from),
                                                         ('financial_date', '<=', ledger_till)])
            for line in transactions:
                if line.invoice_id.state != 'invoiced':
                    continue
                vat_amount = line.vat_amount
                if used_vats[line.vat_id.id]['type'] == 'plus':
                    if vat_amount < 0.0:
                        debit = round(abs(vat_amount), 2)
                        if line.currency_id != company_currency:
                            debit = debit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': debit,
                            'credit': 0.0,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': line.invoice_id.name,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                    elif vat_amount > 0.0:
                        credit = round(vat_amount, 2)
                        if line.currency_id != company_currency:
                            credit = credit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': 0.0,
                            'credit': credit,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': line.invoice_id.name,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                else:
                    if vat_amount > 0.0:
                        debit = round(vat_amount, 2)
                        if line.currency_id != company_currency:
                            debit = debit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': debit,
                            'credit': 0.0,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': line.invoice_id.name,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                    elif vat_amount < 0.0:
                        credit = round(abs(vat_amount), 2)
                        if line.currency_id != company_currency:
                            credit = credit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': 0.0,
                            'credit': credit,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': line.invoice_id.name,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)

            transactions = invoice_po_line_model.search([('account_id', '=', account.id),
                                                         ('financial_date', '>=', ledger_from),
                                                         ('financial_date', '<=', ledger_till)])
            for line in transactions:
                if line.invoice_id.state != 'valid':
                    continue

                if line.invoice_id.name and line.invoice_id.reference:
                    document = '%s / %s' % (line.invoice_id.name, line.invoice_id.reference)
                elif line.invoice_id.name:
                    document = line.invoice_id.name
                elif line.invoice_id.reference:
                    document = line.invoice_id.reference
                else:
                    document = 'PO#%d' % line.invoice_id.id

                document_link = '%s/web#id=%d&view_type=form&model=s2u.account.invoice' % (base_url, line.invoice_id.id)
                if line.net_amount > 0.0:
                    debit = round(line.net_amount, 2)
                    vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                    if line.currency_id != company_currency:
                        debit = debit * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                        if vat_amount:
                            vat_amount = vat_amount * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                    trans = {
                        'trans_date': line.financial_date,
                        'description': line.descript,
                        'debit': debit,
                        'credit': 0.0,
                        'vat_code': line.vat_id.name if line.vat_id else '',
                        'vat_amount': vat_amount,
                        'document': document,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)
                elif line.net_amount < 0.0:
                    credit = round(abs(line.net_amount), 2)
                    vat_amount = round(line.vat_amount, 2) if line.vat_id else ''
                    if line.currency_id != company_currency:
                        credit = credit * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                        if vat_amount:
                            vat_amount = vat_amount * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                    trans = {
                        'trans_date': line.financial_date,
                        'description': line.descript,
                        'debit': 0.0,
                        'credit': credit,
                        'vat_code': line.vat_id.name if line.vat_id else '',
                        'vat_amount': vat_amount,
                        'document': document,
                        'document_link': document_link
                    }
                    ledger_account['transactions'].append(trans)

            transactions = invoice_po_line_model.search([('vat_id', 'in', list(used_vats.keys())),
                                                         ('financial_date', '>=', ledger_from),
                                                         ('financial_date', '<=', ledger_till)])
            for line in transactions:
                if line.invoice_id.state != 'valid':
                    continue
                if line.invoice_id.name and line.invoice_id.reference:
                    document = '%s / %s' % (line.invoice_id.name, line.invoice_id.reference)
                elif line.invoice_id.name:
                    document = line.invoice_id.name
                elif line.invoice_id.reference:
                    document = line.invoice_id.reference
                else:
                    document = 'PO#%d' % line.invoice_id.id
                vat_amount = line.vat_amount
                if used_vats[line.vat_id.id]['type'] == 'plus':
                    if vat_amount > 0.0:
                        debit = round(vat_amount, 2)
                        if line.currency_id != company_currency:
                            debit = debit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': debit,
                            'credit': 0.0,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': document,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                    elif vat_amount < 0.0:
                        credit = round(abs(vat_amount), 2)
                        if line.currency_id != company_currency:
                            credit = credit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': 0.0,
                            'credit': credit,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': document,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                else:
                    if vat_amount < 0.0:
                        debit = round(abs(vat_amount), 2)
                        if line.currency_id != company_currency:
                            debit = debit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': debit,
                            'credit': 0.0,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': document,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)
                    elif vat_amount > 0.0:
                        credit = round(vat_amount, 2)
                        if line.currency_id != company_currency:
                            credit = credit * line.currency_id.with_context({
                                'date': line.financial_date
                            }).rate
                        trans = {
                            'trans_date': line.financial_date,
                            'description': line.descript,
                            'debit': 0.0,
                            'credit': credit,
                            'vat_code': '',
                            'vat_amount': '',
                            'document': document,
                            'document_link': document_link
                        }
                        ledger_account['transactions'].append(trans)

            transactions = self.env['s2u.account.move'].search([('account_id', '=', account.id),
                                                                ('date_trans', '>=', ledger_from),
                                                                ('date_trans', '<=', ledger_till)])
            for line in transactions:
                document = self.env[line.res_model].browse(line.res_id)
                try:
                    document_link = '%s/web#id=%d&view_type=form&model=%s' % (base_url, document.source_id, document.source_model)
                except:
                    document_link = '%s/web#id=%d&view_type=form&model=%s' % (base_url, line.res_id, line.res_model)
                debit = round(line.debit, 2)
                credit = round(line.credit, 2)
                if line.currency_id != company_currency:
                    debit = debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                    credit = credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                trans = {
                    'trans_date': line.date_trans,
                    'description': line.name,
                    'debit': debit,
                    'credit': credit,
                    'vat_code': '',
                    'vat_amount': '',
                    'document': document,
                    'document_link': document_link
                }
                ledger_account['transactions'].append(trans)

            ledger_accounts.append(ledger_account)

        return {
            'date_ledger_till': date_ledger_till,
            'ledger_accounts': ledger_accounts
        }


