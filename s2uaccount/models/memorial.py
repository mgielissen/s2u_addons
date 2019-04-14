# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class AccountMemorialLineInvoiceSO(models.Model):
    _name = "s2u.account.memorial.line.invoice.so"
    _description = "Invoices SO"

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.trans_amount = self.invoice_id.amount_open

    @api.one
    @api.depends('trans_amount')
    def _compute_open(self):
        if self.invoice_id:
            if self._context.get('register_payment', False):
                self.open_amount = self.invoice_id.amount_open
            else:
                self.open_amount = self.invoice_id.amount_open - self.trans_amount

    mline_id = fields.Many2one('s2u.account.memorial.line', string='Transaction', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  related='mline_id.currency_id', store=True)
    trans_amount = fields.Monetary(string='Amount', currency_field='currency_id')
    open_amount = fields.Monetary(string='Open', currency_field='currency_id',
                                  store=True, readonly=True, compute='_compute_open')
    type = fields.Selection([
        ('keep', 'Keep open'),
        ('diff', 'Book as payment difference'),
        ('disc', 'Book as payment discount'),
    ], required=True, default='keep', string='Difference amount')
    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='restrict')


class AccountMemorialLineInvoicePO(models.Model):
    _name = "s2u.account.memorial.line.invoice.po"
    _description = "Invoices PO"

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.trans_amount = self.invoice_id.amount_open * -1.0

    @api.one
    @api.depends('trans_amount')
    def _compute_open(self):
        if self.invoice_id:
            self.open_amount = self.invoice_id.amount_open * -1.0

    mline_id = fields.Many2one('s2u.account.memorial.line', string='Transaction', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  related='mline_id.currency_id', store=True)
    trans_amount = fields.Monetary(string='Amount', currency_field='currency_id')
    open_amount = fields.Monetary(string='Open', currency_field='currency_id',
                                  store=True, readonly=True, compute='_compute_open')
    type = fields.Selection([
        ('keep', 'Keep open'),
        ('diff', 'Book as payment difference'),
        ('disc', 'Book as payment discount'),
    ], required=True, default='keep', string='Difference amount')
    invoice_id = fields.Many2one('s2u.account.invoice.po', string='Invoice', required=True, ondelete='restrict')


class AccountMemorialLine(models.Model):
    _name = "s2u.account.memorial.line"
    _description = "Memorial line"

    @api.one
    @api.depends('gross_amount', 'vat_amount')
    def _compute_net_amount(self):
        if self.vat_id:
            self.net_amount = self.vat_id.calc_netto_amount(self.gross_amount, self.vat_amount)
        else:
            self.net_amount = self.gross_amount

    @api.one
    @api.depends('type', 'gross_amount', 'so_ids.trans_amount', 'po_ids.trans_amount',
                 'vat_amount', 'vat_id', 'account_id')
    def _compute_amount(self):
        if self.type == 'nor':
            self.trans_amount = self.gross_amount
        elif self.type == 'deb':
            amount = 0.0
            for so in self.so_ids:
                amount += so.trans_amount
            self.trans_amount = amount
        elif self.type == 'cre':
            amount = 0.0
            for po in self.po_ids:
                amount += po.trans_amount
            self.trans_amount = amount
        else:
            # TODO: batch payments
            self.trans_amount = 0.0

    @api.onchange('gross_amount')
    def _onchange_gross_amount(self):
        if not self.vat_id:
            self.net_amount = self.gross_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_gross_amount(self.gross_amount)
        self.net_amount = self.vat_id.calc_netto_amount(self.gross_amount, self.vat_amount)

        return False

    @api.onchange('vat_id')
    def _onchange_vat_id(self):
        if not self.vat_id:
            self.net_amount = self.gross_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_gross_amount(self.gross_amount)
        self.net_amount = self.vat_id.calc_netto_amount(self.gross_amount, self.vat_amount)

        return False

    @api.onchange('vat_amount')
    def _onchange_vat_amount(self):
        if not self.vat_id:
            self.net_amount = self.gross_amount
            self.vat_amount = 0.0
            return False

        self.net_amount = self.vat_id.calc_netto_amount(self.gross_amount, self.vat_amount)

        return False

    memorial_id = fields.Many2one('s2u.account.memorial', string='Memorial', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  related='memorial_id.currency_id', store=True)
    gross_amount = fields.Monetary(string='Amount', currency_field='currency_id')
    net_amount = fields.Monetary(string='Net', currency_field='currency_id',
                                 store=True, readonly=True, compute='_compute_net_amount')
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account')
    vat_id = fields.Many2one('s2u.account.vat', string='VAT-Code')
    type = fields.Selection([
        ('nor', 'Normal'),
        ('deb', 'Debitor'),
        ('cre', 'Creditor'),
        ('bat', 'Batch'),
    ], required=True, default='nor', string='Type')
    descript = fields.Text(string='Description')
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor/creditor', index=True)
    so_ids = fields.One2many('s2u.account.memorial.line.invoice.so', 'mline_id', string='Invoices')
    po_ids = fields.One2many('s2u.account.memorial.line.invoice.po', 'mline_id', string='Invoices')
    trans_amount = fields.Monetary(string='Amount', currency_field='currency_id', store=True, readonly=True,
                                   compute='_compute_amount')
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')


class AccountMemorialAccount(models.Model):
    _name = "s2u.account.memorial.account"
    _description = "Memorial line accounting data - automatically build on create/write"

    memorial_id = fields.Many2one('s2u.account.memorial', string='Memorial', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Invoice Currency',
                                  related='memorial_id.currency_id', store=True)
    debit = fields.Monetary(string='Debit', currency_field='currency_id')
    credit = fields.Monetary(string='Credit', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account', index=True)
    date_trans = fields.Date(string='Date', index=True)
    so_invoice_id = fields.Many2one('s2u.account.invoice', string='Account', index=True)
    po_invoice_id = fields.Many2one('s2u.account.invoice.po', string='Account', index=True)
    memorial_type = fields.Selection([
        ('nor', 'Normal'),
        ('ope', 'Opening balance'),
    ], index=True, related='memorial_id.memorial_type', string='Type')
    type = fields.Selection([
        ('nor', 'Normal'),
        ('diff', 'Book as payment difference'),
        ('disc', 'Book as payment discount'),
    ], required=True, default='nor', string='Type')
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id')
    vat_id = fields.Many2one('s2u.account.vat', string='VAT-Code')
    descript = fields.Text(string='Description')


class AccountMemorial(models.Model):
    _name = "s2u.account.memorial"
    _description = "Memorial"
    _order = "date_trans desc"

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.multi
    def assert_saldo_is_zero(self):
        if not self.ids:
            return True

        self.env.cr.execute("""\
                    SELECT      memorial_id, sum(trans_amount)                    
                    FROM        s2u_account_memorial_line
                    WHERE       memorial_id in %s
                    GROUP BY    memorial_id
                    HAVING      sum(trans_amount) <> 0.0
                    """, (tuple(self.ids),))
        res = self.env.cr.fetchall()
        if len(res) != 0:
            raise UserError(_("Saldo for memorial booking must be zero."))
        return True

    @api.multi
    def compute_accounts(self):
        account_memorial_account = self.env['s2u.account.memorial.account']
        for memorial in self:
            self._cr.execute("DELETE FROM s2u_account_memorial_account WHERE memorial_id=%s", (memorial.id,))
            self.invalidate_cache()

            for line in memorial.line_ids:
                if line.type == 'deb':
                    for so in line.so_ids:
                        debit = 0.0
                        credit = 0.0
                        if so.trans_amount > 0.0:
                            credit = so.trans_amount
                        else:
                            debit = abs(so.trans_amount)
                        vals = {
                            'memorial_id': memorial.id,
                            'date_trans': memorial.date_trans,
                            'account_id': so.invoice_id.account_id.id,
                            'so_invoice_id': so.invoice_id.id,
                            'debit': debit,
                            'credit': credit
                        }
                        account_memorial_account.create(vals)
                        vals = {
                            'memorial_id': memorial.id,
                            'date_trans': memorial.date_trans,
                            'account_id': line.account_id.id,
                            'debit': credit,
                            'credit': debit,
                            'descript': line.descript
                        }
                        account_memorial_account.create(vals)
                        if so.type in ['diff', 'disc']:
                            if so.open_amount:
                                debit = 0.0
                                credit = 0.0
                                if so.open_amount > 0.0:
                                    debit = so.open_amount
                                else:
                                    credit = abs(so.open_amount)
                                if so.type == 'disc':
                                    account_id = memorial.account_so_difference_id.id
                                else:
                                    account_id = memorial.account_accepted_id.id
                                vals = {
                                    'memorial_id': memorial.id,
                                    'date_trans': memorial.date_trans,
                                    'account_id': account_id,
                                    'debit': debit,
                                    'credit': credit
                                }
                                account_memorial_account.create(vals)
                                vals = {
                                    'memorial_id': memorial.id,
                                    'date_trans': memorial.date_trans,
                                    'account_id': so.invoice_id.account_id.id,
                                    'so_invoice_id': so.invoice_id.id,
                                    'debit': credit,
                                    'credit': debit,
                                    'type': so.type
                                }
                                account_memorial_account.create(vals)
                elif line.type == 'cre':
                    for po in line.po_ids:
                        debit = 0.0
                        credit = 0.0
                        if po.trans_amount < 0.0:
                            debit = abs(po.trans_amount)
                        else:
                            credit = po.trans_amount
                        vals = {
                            'memorial_id': memorial.id,
                            'date_trans': memorial.date_trans,
                            'account_id': po.invoice_id.account_id.id,
                            'po_invoice_id': po.invoice_id.id,
                            'debit': debit,
                            'credit': credit
                        }
                        account_memorial_account.create(vals)
                        vals = {
                            'memorial_id': memorial.id,
                            'date_trans': memorial.date_trans,
                            'account_id': line.account_id.id,
                            'debit': credit,
                            'credit': debit,
                            'descript': line.descript
                        }
                        account_memorial_account.create(vals)
                        if po.type in ['diff', 'disc']:
                            if po.open_amount:
                                debit = 0.0
                                credit = 0.0
                                if po.open_amount > 0.0:
                                    debit = po.open_amount
                                else:
                                    credit = abs(po.open_amount)
                                if po.type == 'disc':
                                    account_id = memorial.account_so_difference_id.id
                                else:
                                    account_id = memorial.account_accepted_id.id
                                vals = {
                                    'memorial_id': memorial.id,
                                    'date_trans': memorial.date_trans,
                                    'account_id': account_id,
                                    'debit': debit,
                                    'credit': credit
                                }
                                account_memorial_account.create(vals)
                                vals = {
                                    'memorial_id': memorial.id,
                                    'date_trans': memorial.date_trans,
                                    'account_id': po.invoice_id.account_id.id,
                                    'po_invoice_id': po.invoice_id.id,
                                    'debit': credit,
                                    'credit': debit,
                                    'type': po.type
                                }
                                account_memorial_account.create(vals)
                else:
                    debit = 0.0
                    credit = 0.0
                    if line.vat_id:
                        if line.net_amount > 0.0:
                            credit = line.net_amount
                        else:
                            debit = abs(line.net_amount)
                    else:
                        if line.gross_amount > 0.0:
                            credit = line.gross_amount
                        else:
                            debit = abs(line.gross_amount)
                    vals = {
                        'memorial_id': memorial.id,
                        'date_trans': memorial.date_trans,
                        'account_id': line.account_id.id,
                        'debit': debit,
                        'credit': credit,
                        'descript': line.descript
                    }
                    if line.vat_id:
                        vals['vat_id'] = line.vat_id.id
                        vals['vat_amount'] = line.vat_amount
                    account_memorial_account.create(vals)
                    if line.vat_id:
                        for rule in line.vat_id.rule_ids:
                            if rule.rule_type == 'plus':
                                if line.vat_amount > 0.0:
                                    credit = line.vat_amount
                                    debit = 0.0
                                else:
                                    debit = abs(line.vat_amount)
                                    credit = 0.0
                            else:
                                if line.vat_amount > 0.0:
                                    debit = line.vat_amount
                                    credit = 0.0
                                else:
                                    credit = abs(line.vat_amount)
                                    debit = 0.0
                            vals = {
                                'memorial_id': memorial.id,
                                'date_trans': memorial.date_trans,
                                'account_id': rule.account_id.id,
                                'debit': debit,
                                'credit': credit
                            }
                            account_memorial_account.create(vals)

    @api.model
    def create(self, vals):

        invoices_so = self.env['s2u.account.invoice']
        invoices_po = self.env['s2u.account.invoice.po']

        memorial = super(AccountMemorial, self).create(vals)
        memorial.assert_saldo_is_zero()
        memorial.compute_accounts()

        for line in memorial.line_ids:
            for so in line.so_ids:
                invoices_so += so.invoice_id
            for po in line.po_ids:
                invoices_po += po.invoice_id

        invoices_so.sync_open()
        invoices_po.sync_open()

        return memorial

    @api.multi
    def write(self, vals):

        invoices_so = self.env['s2u.account.invoice']
        invoices_po = self.env['s2u.account.invoice.po']
        for bank in self:
            for line in bank.line_ids:
                for so in line.so_ids:
                    invoices_so += so.invoice_id
                for po in line.po_ids:
                    invoices_po += po.invoice_id

        res = super(AccountMemorial, self).write(vals)
        self.assert_saldo_is_zero()
        for memorial in self:
            memorial.compute_accounts()

        invoices_so.sync_open()
        invoices_po.sync_open()

        return res

    @api.one
    def unlink(self):

        invoices_so = self.env['s2u.account.invoice']
        invoices_po = self.env['s2u.account.invoice.po']
        for bank in self:
            for line in bank.line_ids:
                for so in line.so_ids:
                    invoices_so += so.invoice_id
                for po in line.po_ids:
                    invoices_po += po.invoice_id

        res = super(AccountMemorial, self).unlink()

        invoices_so.sync_open()
        invoices_po.sync_open()

        return res

    name = fields.Char(string='Descript', index=True, required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency)
    line_ids = fields.One2many('s2u.account.memorial.line', 'memorial_id',
                               string='Lines')
    account_accepted_id = fields.Many2one('s2u.account.account', string='Accepted difference',
                                          domain=[('type', 'in', ['expense'])])
    account_so_difference_id = fields.Many2one('s2u.account.account', string='Debitor difference',
                                               domain=[('type', 'in', ['income'])])
    account_po_difference_id = fields.Many2one('s2u.account.account', string='Creditor difference',
                                               domain=[('type', 'in', ['expense'])])
    account_ids = fields.One2many('s2u.account.memorial.account', 'memorial_id',
                                  string='Accounts')
    date_trans = fields.Date(string='Date', index=True, copy=False,
                             default=lambda self: fields.Date.context_today(self))
    memorial_type = fields.Selection([
        ('nor', 'Normal'),
        ('ope', 'Opening balance'),
    ], required=True, default='nor', string='Type')


