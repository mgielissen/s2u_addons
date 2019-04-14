# -*- coding: utf-8 -*-

import time
import math

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class TemplateAccountCategory(models.Model):
    _name = "s2u.template.account.category"
    _description = "Template account category"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='Category', required=True, index=True)
    parent_id = fields.Many2one('s2u.template.account.category', string='Parent', ondelete='restrict')
    type = fields.Selection([
        ('category', 'Main category'),
        ('asset', 'Asset'),  # Activa
        ('liability', 'Liability'),  # Passiva
        ('income', 'Income'),  # Opbrengsten
        ('expense', 'Expense'),  # Kosten
    ], required=True, default='category')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code must be unique !')
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


class TemplateAccountAccount(models.Model):
    _name = "s2u.template.account.account"
    _description = "Template account"
    _order = "code"


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
    category_id = fields.Many2one('s2u.template.account.category', string='Category', required=True)
    vat_id = fields.Many2one('s2u.template.account.vat', string='Default vat')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code of the account must be unique !')
    ]

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        return super(TemplateAccountAccount, self).copy(default)

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


class TemplateAccountVatCategory(models.Model):
    _name = "s2u.template.account.vat.category"
    _description = "Template VAT category"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='Category', required=True, index=True)
    parent_id = fields.Many2one('s2u.template.account.vat.category', string='Parent', ondelete='restrict')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code of the category must be unique !')
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


class TemplateAccountVat(models.Model):
    _name = "s2u.template.account.vat"
    _description = "Template vat"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='VAT', required=True, index=True)
    rule_ids = fields.One2many('s2u.template.account.vat.rule', 'vat_id',
                               string='VAT rules')
    rule_gross = fields.Char(string='Rule for gross amount', required=True)
    rule_net = fields.Char(string='Rule for net amount', required=True)
    rule_vat = fields.Char(string='Rule for VAT amount', required=True)
    type = fields.Selection([
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ], required=True, default='buy', index=True, string='Type')
    vat_report = fields.Selection([
        ('00', 'Group 00'),
        ('01', 'Group 01'),
        ('02', 'Group 02'),
        ('03', 'Group 03'),
        ('04', 'Group 04'),
        ('05', 'Group 05'),
        ('06', 'Group 06'),
        ('07', 'Group 07'),
        ('08', 'Group 08'),
        ('09', 'Group 09'),
        ('10', 'Group 10'),
        ('11', 'Group 11'),
        ('12', 'Group 12'),
        ('13', 'Group 13'),
        ('14', 'Group 14'),
        ('15', 'Group 15'),
        ('16', 'Group 16'),
        ('17', 'Group 17'),
        ('18', 'Group 18'),
        ('19', 'Group 19'),
        ('20', 'Group 20')
    ], required=True, default='00', string='Report')
    tinno_obligatory = fields.Boolean('TIN no. obligatory', default=False)
    category = fields.Selection([
        ('ser', 'Services'),
        ('del', 'Deliveries')
    ], required=True, default='ser', string='Category')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code of the vat must be unique !')
    ]

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(TemplateAccountVat, self).copy(default)

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for vat in self:
            name = vat.code + ' (' + vat.name + ')'
            result.append((vat.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        vats = self.search(domain + args, limit=limit)
        return vats.name_get()


class TemplateAccountVatRule(models.Model):
    _name = "s2u.template.account.vat.rule"
    _description = "Template VAT rule"

    vat_id = fields.Many2one('s2u.template.account.vat', string='Vat', required=True, ondelete='cascade')
    rule_type = fields.Selection([
        ('plus', 'Plus'),
        ('min', 'Minus'),
    ], required=True, default='plus', index=True, string='Rule')
    account_id = fields.Many2one('s2u.template.account.account', string='Account')
    category_id = fields.Many2one('s2u.template.account.vat.category', string='Category', required=True)
