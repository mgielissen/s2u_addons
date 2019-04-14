# -*- coding: utf-8 -*-

import datetime

from odoo.osv import expression
from odoo import api, fields, models, _

class AccountCategory(models.Model):
    _name = "s2u.account.category"
    _description = "Account category"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='Category', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    parent_id = fields.Many2one('s2u.account.category', string='Parent', ondelete='restrict')
    type = fields.Selection([
        ('category', 'Main category'),
        ('asset', 'Asset'),  # Activa
        ('liability', 'Liability'),  # Passiva
        ('income', 'Income'),  # Opbrengsten
        ('expense', 'Expense'),  # Kosten
    ], required=True, default='category')

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id)', 'The code must be unique !')
    ]

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for category in self:
            name = category.code + ' - ' + category.name
            result.append((category.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        categories = self.search(domain + args, limit=limit)
        return categories.name_get()

class AccountAccount(models.Model):
    _name = "s2u.account.account"
    _description = "Account"
    _order = "code"

    @api.one
    def _compute_end_saldo(self):

        saldo = self.saldo_per_date(datetime.date.today())
        self.end_saldo = saldo

    @api.multi
    def saldo_per_date(self, till_date,
                       result='saldo',
                       from_date=False,
                       skip_openingalance=False,
                       openingbalance_only=False,
                       fiscalyear=False):
        bank_model = self.env['s2u.account.bank.account']
        memorial_model = self.env['s2u.account.memorial.account']
        invoice_so_model = self.env['s2u.account.invoice']
        invoice_so_line_model = self.env['s2u.account.invoice.line']
        invoice_po_model = self.env['s2u.account.invoice.po']
        invoice_po_line_model = self.env['s2u.account.invoice.po.line']
        vat_rule_model = self.env['s2u.account.vat.rule']

        company_currency = self.env.user.company_id.currency_id

        end_saldo = 0.0
        if not till_date or openingbalance_only:
            if not fiscalyear:
                till_date = datetime.date.today()
                from_date = '%d-01-01' % till_date.year
                till_date = '%d-12-31' % till_date.year
            else:
                from_date = '%d-01-01' % fiscalyear
                till_date = '%d-12-31' % fiscalyear
        elif isinstance(till_date, str) and not from_date:
            dt = datetime.datetime.strptime(till_date, '%Y-%m-%d')
            from_date = '%d-01-01' % dt.year
        elif not isinstance(till_date, str):
            if not from_date:
                from_date = '%d-01-01' % till_date.year
            else:
                from_date = from_date.strftime('%Y-%m-%d')
            till_date = till_date.strftime('%Y-%m-%d')

        if openingbalance_only:
            types = ['ope']
        elif skip_openingalance:
            types = ['nor']
        else:
            types = ['ope', 'nor']
        transactions = memorial_model.search([('account_id', '=', self.id),
                                              ('memorial_type', 'in', types),
                                              ('date_trans', '>=', from_date),
                                              ('date_trans', '<=', till_date)])
        for line in transactions:
            if result == 'debit':
                if line.currency_id != company_currency:
                    end_saldo += line.debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.debit
            elif result == 'credit':
                if line.currency_id != company_currency:
                    end_saldo += line.credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.credit
            else:
                if line.currency_id != company_currency:
                    end_saldo += (line.debit - line.credit) * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.debit - line.credit

        if openingbalance_only:
            return end_saldo

        transactions = bank_model.search([('account_id', '=', self.id),
                                          ('date_trans', '>=', from_date),
                                          ('date_trans', '<=', till_date)])
        for t in transactions:
            if result == 'debit':
                if line.currency_id != company_currency:
                    end_saldo += t.debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += t.debit
            elif result == 'credit':
                if line.currency_id != company_currency:
                    end_saldo += t.credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += t.credit
            else:
                if line.currency_id != company_currency:
                    end_saldo += (t.debit - t.credit) * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += t.debit - t.credit

        transactions = invoice_so_model.search([('account_id', '=', self.id),
                                                ('state', '=', 'invoiced'),
                                                ('date_financial', '>=', from_date),
                                                ('date_financial', '<=', till_date)])
        for invoice in transactions:
            if result == 'debit':
                if invoice.amount_gross > 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += invoice.amount_gross * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    else:
                        end_saldo += invoice.amount_gross
            elif result == 'credit':
                if invoice.amount_gross < 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += abs(invoice.amount_gross) * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    else:
                        end_saldo += abs(invoice.amount_gross)
            else:
                if line.currency_id != company_currency:
                    end_saldo += invoice.amount_gross * line.currency_id.with_context({
                        'date': line.date_financial
                    }).rate
                else:
                    end_saldo += invoice.amount_gross

        transactions = invoice_po_model.search([('account_id', '=', self.id),
                                                ('state', '=', 'valid'),
                                                ('date_financial', '>=', from_date),
                                                ('date_financial', '<=', till_date)])
        for invoice in transactions:
            if result == 'debit':
                if invoice.amount_gross < 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += abs(invoice.amount_gross) * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    else:
                        end_saldo += abs(invoice.amount_gross)
            elif result == 'credit':
                if invoice.amount_gross > 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += invoice.amount_gross * line.currency_id.with_context({
                            'date': line.date_financial
                        }).rate
                    else:
                        end_saldo += invoice.amount_gross
            else:
                # het gaat om debit - credit = saldo
                # in deze situatie is de credit > 0 (grb.rek crediteuren van de factuur)
                # vandaar -=
                if line.currency_id != company_currency:
                    end_saldo -= invoice.amount_gross * line.currency_id.with_context({
                        'date': line.date_financial
                    }).rate
                else:
                    end_saldo -= invoice.amount_gross

        used_vats = {}
        rules = vat_rule_model.search([('account_id', '=', self.id)])
        for rule in rules:
            if rule.vat_id.id not in used_vats:
                used_vats[rule.vat_id.id] = {'type': rule.rule_type,
                                             'rule': rule.vat_id.rule_vat}

        transactions = invoice_so_line_model.search([('account_id', '=', self.id),
                                                     ('financial_date', '>=', from_date),
                                                     ('financial_date', '<=', till_date)])
        for line in transactions:
            if line.invoice_id.state != 'invoiced':
                continue

            if result == 'debit':
                if line.net_amount < 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += abs(line.net_amount) * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                    else:
                        end_saldo += abs(line.net_amount)
            elif result == 'credit':
                if line.net_amount > 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += line.net_amount * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                    else:
                        end_saldo += line.net_amount
            else:
                if line.currency_id != company_currency:
                    end_saldo -= line.net_amount * line.currency_id.with_context({
                        'date': line.financial_date
                    }).rate
                else:
                    end_saldo -= line.net_amount

        transactions = invoice_so_line_model.search([('vat_id', 'in', list(used_vats.keys())),
                                                     ('financial_date', '>=', from_date),
                                                     ('financial_date', '<=', till_date)])
        for line in transactions:
            if line.invoice_id.state != 'invoiced':
                continue
            if line.currency_id != company_currency:
                vat_amount = line.vat_amount * line.currency_id.with_context({
                    'date': line.financial_date
                }).rate
            else:
                vat_amount = line.vat_amount
            if used_vats[line.vat_id.id]['type'] == 'plus':
                if result == 'debit':
                    if vat_amount < 0.0:
                        end_saldo += abs(vat_amount)
                elif result == 'credit':
                    if vat_amount > 0.0:
                        end_saldo += vat_amount
                else:
                    end_saldo -= vat_amount
            else:
                if result == 'debit':
                    if vat_amount > 0.0:
                        end_saldo += vat_amount
                elif result == 'credit':
                    if vat_amount < 0.0:
                        end_saldo += abs(vat_amount)
                else:
                    end_saldo += vat_amount

        transactions = invoice_po_line_model.search([('account_id', '=', self.id),
                                                     ('financial_date', '>=', from_date),
                                                     ('financial_date', '<=', till_date)])
        for line in transactions:
            if line.invoice_id.state != 'valid':
                continue
            if result == 'debit':
                if line.net_amount > 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += line.net_amount * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                    else:
                        end_saldo += line.net_amount
            elif result == 'credit':
                if line.net_amount < 0.0:
                    if line.currency_id != company_currency:
                        end_saldo += abs(line.net_amount) * line.currency_id.with_context({
                            'date': line.financial_date
                        }).rate
                    else:
                        end_saldo += abs(line.net_amount)
            else:
                if line.currency_id != company_currency:
                    end_saldo += line.net_amount * line.currency_id.with_context({
                        'date': line.financial_date
                    }).rate
                else:
                    end_saldo += line.net_amount

        transactions = invoice_po_line_model.search([('vat_id', 'in', list(used_vats.keys())),
                                                     ('financial_date', '>=', from_date),
                                                     ('financial_date', '<=', till_date)])
        for line in transactions:
            if line.invoice_id.state != 'valid':
                continue
            if line.currency_id != company_currency:
                vat_amount = line.vat_amount * line.currency_id.with_context({
                    'date': line.financial_date
                }).rate
            else:
                vat_amount = line.vat_amount
            if used_vats[line.vat_id.id]['type'] == 'plus':
                if result == 'debit':
                    if vat_amount > 0.0:
                        end_saldo += vat_amount
                elif result == 'credit':
                    if vat_amount < 0.0:
                        end_saldo += abs(vat_amount)
                else:
                    end_saldo += vat_amount
            else:
                if result == 'debit':
                    if vat_amount < 0.0:
                        end_saldo += abs(vat_amount)
                elif result == 'credit':
                    if vat_amount > 0.0:
                        end_saldo += vat_amount
                else:
                    end_saldo -= vat_amount

        transactions = self.env['s2u.account.move'].search([('account_id', '=', self.id),
                                                            ('date_trans', '>=', from_date),
                                                            ('date_trans', '<=', till_date)])
        for line in transactions:
            if result == 'debit':
                if line.currency_id != company_currency:
                    end_saldo += line.debit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.debit
            elif result == 'credit':
                if line.currency_id != company_currency:
                    end_saldo += line.credit * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.credit
            else:
                if line.currency_id != company_currency:
                    end_saldo += (line.debit - line.credit) * line.currency_id.with_context({
                        'date': line.date_trans
                    }).rate
                else:
                    end_saldo += line.debit - line.credit

        return end_saldo

    @api.onchange('type')
    def onchange_type(self):
        if self.type == 'income':
            domain = [('type', '=', 'sell')]
        elif self.type == 'expense':
            domain = [('type', '=', 'buy')]
        else:
            return False

        return {'domain': {'vat_id': domain}}

    name = fields.Char(required=True, index=True)
    currency_id = fields.Many2one('res.currency', string='Account Currency')
    code = fields.Char(size=64, required=True, index=True)
    type = fields.Selection([
        ('other', 'Other'),            # Overige
        ('receivable', 'Receivable'),  # Debiteuren
        ('payable', 'Payable'),        # Crediteuren
        ('tax', 'Tax'),                # BTW
        ('bank', 'Bank'),              # Bank
        ('cash', 'Cash'),              # Kas
        ('check', 'Check'),            # Cheque
        ('asset', 'Asset'),            # Activa
        ('liability', 'Liability'),    # Passiva
        ('income', 'Income'),          # Opbrengsten
        ('expense', 'Expense'),        # Kosten
        ('equity', 'Equity'),          # Vermogen
        ('stock', 'Stock')             # Voorraad
    ], required=True, default='other',
        help="The 'Type' is used for features available on " \
             "different types of accounts: liquidity type is for cash or bank accounts" \
             ", payable/receivable is for vendor/customer accounts.")
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    category_id = fields.Many2one('s2u.account.category', string='Category', required=True)
    end_saldo = fields.Monetary(string='End saldo',
                                store=False, readonly=True, compute='_compute_end_saldo')
    vat_id = fields.Many2one('s2u.account.vat', string='Default vat')
    bank_account = fields.Char(string='Bank account', index=True)
    mt940_format = fields.Selection([('abnamro', 'ABNAMRO')], string='MT940 format')

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id)', 'The code of the account must be unique per administration !')
    ]

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        return super(AccountAccount, self).copy(default)

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for account in self:
            name = account.code + ' ' + account.name
            result.append((account.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        if args and len(args) == 1:
            if args[0][0] == 'name' and args[0][1] == 'ilike':
                val = args[0][2]
                args = ['|', ('name', 'ilike', val),
                             ('code', 'ilike', val)]

        return super(AccountAccount, self).search(args, offset, limit, order, count=count)


class AccountAnalytic(models.Model):
    _name = "s2u.account.analytic"
    _description = "analytic Account"
    _order = "name"

    @api.one
    def _compute_saldo(self):
        invoice_so_line_model = self.env['s2u.account.invoice.line']
        invoice_po_line_model = self.env['s2u.account.invoice.po.line']
        memorial_line_model = self.env['s2u.account.memorial.line']
        bank_line_model = self.env['s2u.account.bank.line']

        saldo = 0.0
        debit = 0.0
        credit = 0.0

        so_lines = invoice_so_line_model.search([('analytic_id', '=', self.id)])
        for line in so_lines:
            if line.invoice_id.state != 'invoiced':
                continue
            if line.net_amount > 0.0:
                debit += line.net_amount
            elif line.net_amount < 0.0:
                credit += abs(line.net_amount)
            saldo += line.net_amount

        po_lines = invoice_po_line_model.search([('analytic_id', '=', self.id)])
        for line in po_lines:
            if line.invoice_id.state != 'valid':
                continue
            if line.net_amount > 0.0:
                credit += line.net_amount
            elif line.net_amount < 0.0:
                debit += abs(line.net_amount)
            saldo -= line.net_amount

        mem_lines = memorial_line_model.search([('analytic_id', '=', self.id)])
        for line in mem_lines:
            if line.type != 'nor':
                continue
            if line.net_amount > 0.0:
                debit += line.net_amount
            elif line.net_amount < 0.0:
                credit += abs(line.net_amount)
            saldo += line.net_amount

        bank_lines = bank_line_model.search([('analytic_id', '=', self.id)])
        for line in bank_lines:
            if line.type != 'nor':
                continue
            if line.net_amount > 0.0:
                debit += line.net_amount
            elif line.net_amount < 0.0:
                credit += abs(line.net_amount)
            saldo += line.net_amount

        self.saldo = saldo
        self.debit = debit
        self.credit = credit

    name = fields.Char(required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    saldo = fields.Monetary(string='Saldo', readonly=True, compute='_compute_saldo')
    debit = fields.Monetary(string='Debit', readonly=True, compute='_compute_saldo')
    credit = fields.Monetary(string='Credit', readonly=True, compute='_compute_saldo')
    currency_id = fields.Many2one('res.currency', string='Account Currency')


class AccountPaymentTerm(models.Model):
    _name = "s2u.account.payment.term"
    _description = "Account payment term"
    _order = "name"

    name = fields.Char(string='Payment terms (text)', required=True, index=True,
                       default='30 dagen netto')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    payment_terms = fields.Integer(string='Payment terms (days)', default=30, required=True)
